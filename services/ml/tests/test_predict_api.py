"""Integration tests for the ML FastAPI endpoints (no model required for basic routes)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with patch("main.engine"):
        from main import app
        return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_predict_missing_model(client):
    with patch("main.predict_trial", side_effect=FileNotFoundError("No model")):
        resp = client.post("/predict", json={"phase": "PHASE3"})
        assert resp.status_code == 503


def test_predict_success(client):
    mock_result = {
        "predicted_success": True,
        "success_probability": 0.72,
        "failure_probability": 0.28,
        "confidence": "High",
        "top_contributing_features": [{"feature": "phase_numeric", "importance": 0.3}],
        "model_version": "v1",
    }
    with patch("main.predict_trial", return_value=mock_result):
        resp = client.post("/predict", json={"phase": "PHASE3", "sponsor_class": "INDUSTRY"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["predicted_success"] is True
        assert 0 <= data["success_probability"] <= 1
