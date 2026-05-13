"""
TrialMind ML Service — FastAPI
Exposes prediction, model metadata, and accuracy benchmarking endpoints.
"""
import json
import sys
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text

from config import settings
from predict import load_meta, load_model, predict_trial

app = FastAPI(
    title="TrialMind ML Service",
    description="Trial success prediction and benchmarking API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = create_engine(settings.database_url)


# ─── Request/Response models ──────────────────────────────────────────────────

class TrialInput(BaseModel):
    nct_id: Optional[str] = None
    phase: Optional[str] = Field(None, example="PHASE3")
    sponsor_class: Optional[str] = Field(None, example="INDUSTRY")
    intervention_types: Optional[list[str]] = Field(default_factory=list)
    therapeutic_area: Optional[str] = Field(None, example="Oncology")
    enrollment: Optional[int] = None
    duration_days: Optional[int] = None
    number_of_arms: Optional[int] = 2
    locations_count: Optional[int] = 10
    countries: Optional[list[str]] = Field(default_factory=list)
    eligibility_min_age: Optional[int] = 18
    eligibility_max_age: Optional[int] = 65


class PredictionResponse(BaseModel):
    predicted_success: bool
    success_probability: float
    failure_probability: float
    confidence: str
    top_contributing_features: list[dict]
    model_version: str


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "ml"}


@app.post("/predict", response_model=PredictionResponse)
def predict(trial: TrialInput):
    """Predict success probability for a given trial design."""
    try:
        result = predict_trial(trial.model_dump())
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("Prediction error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/predict/{nct_id}", response_model=PredictionResponse)
def predict_by_nct_id(nct_id: str):
    """Look up a trial from the DB and predict its success probability."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM trials WHERE nct_id = :id"),
            {"id": nct_id.upper()},
        ).mappings().fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Trial {nct_id} not found")
    try:
        result = predict_trial(dict(row))
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/model/info")
def model_info():
    """Return current model metadata and performance metrics."""
    try:
        meta = load_meta()
        return meta
    except Exception:
        raise HTTPException(status_code=503, detail="Model metadata unavailable")


@app.get("/benchmark")
def benchmark(
    limit: int = Query(default=500, le=5000),
    therapeutic_area: Optional[str] = None,
    phase: Optional[str] = None,
):
    """
    Run predictions on held-out test set predictions stored in DB and
    return accuracy metrics and a confusion matrix for the dashboard.
    """
    query = """
        SELECT predicted_label, actual_label, predicted_proba, correct
        FROM predictions
        WHERE model_version = :version
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text(query),
            {"version": settings.model_version, "limit": limit},
        ).mappings().fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="No prediction records found. Run train.py first.")

    df = pd.DataFrame([dict(r) for r in rows])

    tp = int(((df["predicted_label"] == True) & (df["actual_label"] == True)).sum())
    tn = int(((df["predicted_label"] == False) & (df["actual_label"] == False)).sum())
    fp = int(((df["predicted_label"] == True) & (df["actual_label"] == False)).sum())
    fn = int(((df["predicted_label"] == False) & (df["actual_label"] == True)).sum())

    acc = round(df["correct"].mean(), 4)

    proba_bins = pd.cut(df["predicted_proba"], bins=10)
    calibration = (
        df.groupby(proba_bins, observed=True)["actual_label"]
        .agg(["mean", "count"])
        .reset_index()
        .rename(columns={"mean": "actual_rate", "count": "n"})
    )
    calibration["bin"] = calibration["predicted_proba"].astype(str)

    return {
        "accuracy": acc,
        "n_samples": len(df),
        "confusion_matrix": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "calibration": calibration[["bin", "actual_rate", "n"]].to_dict(orient="records"),
        "model_version": settings.model_version,
    }


@app.get("/benchmark/by-phase")
def benchmark_by_phase():
    """Return accuracy breakdown by trial phase."""
    query = """
        SELECT p.predicted_label, p.actual_label, p.correct, t.phase
        FROM predictions p
        JOIN trials t ON t.nct_id = p.nct_id
        WHERE p.model_version = :version
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"version": settings.model_version}).mappings().fetchall()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        raise HTTPException(status_code=404, detail="No data")

    grouped = df.groupby("phase")["correct"].agg(["mean", "count"]).reset_index()
    grouped.columns = ["phase", "accuracy", "n"]
    return grouped.to_dict(orient="records")


@app.get("/benchmark/by-therapeutic-area")
def benchmark_by_area():
    """Return accuracy breakdown by therapeutic area."""
    query = """
        SELECT p.correct, t.therapeutic_area
        FROM predictions p
        JOIN trials t ON t.nct_id = p.nct_id
        WHERE p.model_version = :version
    """
    with engine.connect() as conn:
        rows = conn.execute(text(query), {"version": settings.model_version}).mappings().fetchall()

    df = pd.DataFrame([dict(r) for r in rows])
    if df.empty:
        raise HTTPException(status_code=404, detail="No data")

    grouped = df.groupby("therapeutic_area")["correct"].agg(["mean", "count"]).reset_index()
    grouped.columns = ["area", "accuracy", "n"]
    return grouped.to_dict(orient="records")


if __name__ == "__main__":
    import uvicorn
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True)
