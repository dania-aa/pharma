"""
Model training script.
Run: python train.py

Trains an XGBoost classifier on completed/terminated trials,
saves the model and preprocessing artifacts, logs metrics to the DB.
"""
import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import shap
from loguru import logger
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sqlalchemy import create_engine, text
from xgboost import XGBClassifier

from config import settings
from features import FEATURE_COLUMNS, engineer_features

os.makedirs(settings.model_dir, exist_ok=True)


def load_training_data(engine) -> pd.DataFrame:
    query = """
        SELECT
            nct_id, phase, sponsor_class, intervention_types, therapeutic_area,
            enrollment, enrollment_type, duration_days, number_of_arms,
            locations_count, countries, eligibility_min_age, eligibility_max_age,
            eligibility_gender, outcome_success, outcome_confidence
        FROM trials
        WHERE outcome_success IS NOT NULL
          AND outcome_confidence >= 0.6
        ORDER BY RANDOM()
    """
    df = pd.read_sql(query, engine)
    logger.info("Loaded {} labelled training samples", len(df))
    return df


def train():
    engine = create_engine(settings.database_url)

    df = load_training_data(engine)

    if len(df) < 100:
        logger.error("Not enough training data (need >= 100 labelled rows, got {})", len(df))
        sys.exit(1)

    X = engineer_features(df)
    y = df["outcome_success"].astype(int)

    logger.info("Class distribution: success={}, failure={}", y.sum(), (1 - y).sum())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=42
    )

    scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )

    logger.info("Training XGBoost model...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=50,
    )

    # ── Evaluation ──────────────────────────────────────────────────────────
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_proba)

    logger.success(
        "Test metrics | acc={:.3f}  prec={:.3f}  rec={:.3f}  f1={:.3f}  auc={:.3f}",
        acc, prec, rec, f1, auc,
    )
    logger.info("\n{}", classification_report(y_test, y_pred, target_names=["failure", "success"]))
    logger.info("Confusion matrix:\n{}", confusion_matrix(y_test, y_pred))

    # ── Cross-validation ────────────────────────────────────────────────────
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc", n_jobs=-1)
    logger.info("5-fold CV AUC: {:.3f} ± {:.3f}", cv_scores.mean(), cv_scores.std())

    # ── SHAP feature importance ──────────────────────────────────────────────
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test[:200])
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    feature_importance = {
        col: float(val)
        for col, val in sorted(zip(FEATURE_COLUMNS, mean_abs_shap), key=lambda x: -x[1])
    }
    logger.info("Top features: {}", list(feature_importance.items())[:5])

    # ── Save artefacts ───────────────────────────────────────────────────────
    model_path = os.path.join(settings.model_dir, f"xgb_{settings.model_version}.joblib")
    joblib.dump(model, model_path)
    logger.info("Model saved to {}", model_path)

    meta = {
        "model_version": settings.model_version,
        "feature_columns": FEATURE_COLUMNS,
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "auc_roc": auc,
        "cv_auc_mean": float(cv_scores.mean()),
        "cv_auc_std": float(cv_scores.std()),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "feature_importance": feature_importance,
    }
    meta_path = os.path.join(settings.model_dir, f"meta_{settings.model_version}.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("Metadata saved to {}", meta_path)

    # ── Persist metrics to DB ────────────────────────────────────────────────
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO model_metrics
                    (model_version, accuracy, precision_score, recall_score, f1_score,
                     auc_roc, n_train, n_test, feature_importance)
                VALUES
                    (:version, :acc, :prec, :rec, :f1, :auc, :n_train, :n_test, :fi::jsonb)
            """),
            {
                "version": settings.model_version,
                "acc": acc, "prec": prec, "rec": rec, "f1": f1, "auc": auc,
                "n_train": len(X_train), "n_test": len(X_test),
                "fi": json.dumps(feature_importance),
            },
        )
        conn.commit()
    logger.success("Metrics logged to database")

    # ── Store predictions on test set ────────────────────────────────────────
    test_nct_ids = df.iloc[y_test.index]["nct_id"].tolist()
    rows = []
    for nct_id, proba, pred, actual in zip(test_nct_ids, y_proba, y_pred, y_test):
        rows.append({
            "nct_id": nct_id,
            "model_version": settings.model_version,
            "features_json": json.dumps({}),
            "predicted_proba": float(proba),
            "predicted_label": bool(pred),
            "actual_label": bool(actual),
            "correct": bool(pred) == bool(actual),
        })
    if rows:
        pred_df = pd.DataFrame(rows)
        pred_df.to_sql(
            "predictions", engine,
            if_exists="append", index=False, method="multi", chunksize=500,
        )
        logger.info("Stored {} prediction records", len(rows))

    return meta


if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    train()
