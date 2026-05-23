"""Model loading and inference helpers."""
import json
import os
from functools import lru_cache
from typing import Optional

import joblib
import numpy as np
from loguru import logger

from config import settings
from features import features_from_dict, FEATURE_COLUMNS


@lru_cache(maxsize=4)
def load_model(version: str = None):
    v = version or settings.model_version
    path = os.path.join(settings.model_dir, f"xgb_{v}.joblib")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found: {path}. Run train.py first.")
    model = joblib.load(path)
    logger.info("Loaded model version={} from {}", v, path)
    return model


@lru_cache(maxsize=4)
def load_meta(version: str = None) -> dict:
    v = version or settings.model_version
    path = os.path.join(settings.model_dir, f"meta_{v}.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def predict_trial(trial: dict, version: str = None) -> dict:
    """
    Given a trial dict, return prediction with probability and top contributing features.
    """
    model = load_model(version)
    X = features_from_dict(trial)

    proba = float(model.predict_proba(X)[0, 1])
    label = proba >= 0.5

    # Feature contributions via raw XGBoost scores
    raw_scores = dict(zip(FEATURE_COLUMNS, model.feature_importances_))
    top_factors = sorted(raw_scores.items(), key=lambda x: -x[1])[:5]
    top_factors = [{"feature": k, "importance": round(float(v), 4)} for k, v in top_factors]

    confidence_label = (
        "High" if abs(proba - 0.5) > 0.25
        else "Medium" if abs(proba - 0.5) > 0.1
        else "Low"
    )

    return {
        "predicted_success": label,
        "success_probability": round(proba, 4),
        "failure_probability": round(1 - proba, 4),
        "confidence": confidence_label,
        "top_contributing_features": top_factors,
        "model_version": version or settings.model_version,
    }
