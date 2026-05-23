"""
LangChain tool wrappers around the TrialMind MCP server tools.
These are called directly via HTTP to the MCP server process via subprocess,
but wrapped as LangChain StructuredTools for use in the LangGraph agent.
"""
import json
from typing import Any, Optional

import httpx
from langchain_core.tools import StructuredTool, tool
from loguru import logger
from pydantic import BaseModel, Field

from config import settings

MCP_TIMEOUT = 30.0


# ─── Pydantic schemas for tool inputs ────────────────────────────────────────

class SearchTrialsInput(BaseModel):
    query: Optional[str] = Field(None, description="Free-text search in trial title or conditions")
    phase: Optional[str] = Field(None, description="Trial phase, e.g. PHASE3")
    therapeutic_area: Optional[str] = Field(None, description="e.g. Oncology, Cardiology")
    sponsor_class: Optional[str] = Field(None, description="INDUSTRY, NIH, OTHER_GOV")
    status: Optional[str] = Field(None, description="COMPLETED, TERMINATED, WITHDRAWN")
    outcome_success: Optional[bool] = Field(None, description="Filter by outcome")
    limit: int = Field(20, description="Max results")


class TrialDetailsInput(BaseModel):
    nct_id: str = Field(..., description="The NCT ID, e.g. NCT01234567")


class StatisticsInput(BaseModel):
    group_by: str = Field(..., description="Dimension: phase, therapeutic_area, sponsor_class, overall_status")
    filter_therapeutic_area: Optional[str] = None
    filter_phase: Optional[str] = None
    filter_sponsor_class: Optional[str] = None


class CompareGroupsInput(BaseModel):
    dimension: str = Field(..., description="sponsor_class, phase, or therapeutic_area")
    group_a: str = Field(..., description="Value for group A")
    group_b: str = Field(..., description="Value for group B")
    filter_therapeutic_area: Optional[str] = None


class PredictInput(BaseModel):
    nct_id: Optional[str] = None
    phase: Optional[str] = None
    sponsor_class: Optional[str] = None
    intervention_types: Optional[list[str]] = None
    therapeutic_area: Optional[str] = None
    enrollment: Optional[int] = None
    duration_days: Optional[int] = None
    number_of_arms: Optional[int] = None
    locations_count: Optional[int] = None
    countries: Optional[list[str]] = None


class ChartDataInput(BaseModel):
    chart_type: str = Field(
        ...,
        description=(
            "One of: success_rate_by_phase, success_rate_by_area, "
            "enrollment_distribution, trial_volume_over_time, "
            "sponsor_comparison, duration_vs_success"
        ),
    )
    filter_therapeutic_area: Optional[str] = None
    filter_phase: Optional[str] = None


class TopSponsorsInput(BaseModel):
    limit: int = 10
    filter_therapeutic_area: Optional[str] = None
    filter_phase: Optional[str] = None


# ─── HTTP client to the MCP server's companion REST adapter ──────────────────
# We expose the MCP tools via a thin HTTP adapter in the agent service itself
# (direct DB calls), since LangGraph uses Python tool functions.

from sqlalchemy import create_engine, text
import pandas as pd

_engine = create_engine(settings.database_url)


def _db_search_trials(
    query=None, phase=None, therapeutic_area=None, sponsor_class=None,
    status=None, outcome_success=None, limit=20
) -> str:
    conditions = ["1=1"]
    params: dict = {"limit": min(limit, 100)}
    if query:
        conditions.append("(title ILIKE :query)")
        params["query"] = f"%{query}%"
    if phase:
        conditions.append("phase = :phase")
        params["phase"] = phase.upper()
    if therapeutic_area:
        conditions.append("therapeutic_area ILIKE :area")
        params["area"] = f"%{therapeutic_area}%"
    if sponsor_class:
        conditions.append("sponsor_class = :sc")
        params["sc"] = sponsor_class.upper()
    if status:
        conditions.append("overall_status = :status")
        params["status"] = status.upper()
    if outcome_success is not None:
        conditions.append("outcome_success = :os")
        params["os"] = outcome_success

    sql = f"""
        SELECT nct_id, title, overall_status, phase, therapeutic_area,
               sponsor_name, enrollment, duration_days, outcome_success
        FROM trials
        WHERE {' AND '.join(conditions)}
        ORDER BY completion_date DESC NULLS LAST
        LIMIT :limit
    """
    with _engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().fetchall()
    result = {"count": len(rows), "trials": [dict(r) for r in rows]}
    return json.dumps(result, default=str)


def _db_get_trial_details(nct_id: str) -> str:
    with _engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM trials WHERE nct_id = :id"),
            {"id": nct_id.upper()},
        ).mappings().fetchone()
    if not row:
        return json.dumps({"error": f"Trial {nct_id} not found"})
    d = dict(row)
    d.pop("raw_json", None)
    return json.dumps(d, default=str)


def _db_get_statistics(group_by, filter_therapeutic_area=None, filter_phase=None, filter_sponsor_class=None) -> str:
    conditions = ["outcome_success IS NOT NULL"]
    params = {}
    if filter_therapeutic_area:
        conditions.append("therapeutic_area ILIKE :area")
        params["area"] = f"%{filter_therapeutic_area}%"
    if filter_phase:
        conditions.append("phase = :phase")
        params["phase"] = filter_phase.upper()
    if filter_sponsor_class:
        conditions.append("sponsor_class = :sc")
        params["sc"] = filter_sponsor_class.upper()
    where = " AND ".join(conditions)
    sql = f"""
        SELECT {group_by} as group_name,
               COUNT(*) as total,
               SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes,
               ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate_pct,
               ROUND(AVG(enrollment)::numeric,0) as avg_enrollment
        FROM trials WHERE {where}
        GROUP BY {group_by} ORDER BY total DESC
    """
    with _engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().fetchall()
    return json.dumps({"group_by": group_by, "data": [dict(r) for r in rows]}, default=str)


def _db_compare_groups(dimension, group_a, group_b, filter_therapeutic_area=None) -> str:
    area_filter = ""
    base_params: dict = {}
    if filter_therapeutic_area:
        area_filter = "AND therapeutic_area ILIKE :area"
        base_params["area"] = f"%{filter_therapeutic_area}%"

    def _q(val):
        with _engine.connect() as conn:
            row = conn.execute(text(f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes,
                       ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate_pct,
                       ROUND(AVG(enrollment)::numeric,0) as avg_enrollment,
                       ROUND(AVG(duration_days)::numeric,0) as avg_duration_days
                FROM trials
                WHERE {dimension} = :val AND outcome_success IS NOT NULL {area_filter}
            """), {"val": val, **base_params}).mappings().fetchone()
        return dict(row) if row else {}

    return json.dumps({
        "dimension": dimension,
        "group_a": {"name": group_a, "stats": _q(group_a)},
        "group_b": {"name": group_b, "stats": _q(group_b)},
    }, default=str)


def _http_predict(payload: dict) -> str:
    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            if payload.get("nct_id"):
                resp = client.get(f"{settings.ml_service_url}/predict/{payload['nct_id'].upper()}")
            else:
                resp = client.post(f"{settings.ml_service_url}/predict", json=payload)
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        return json.dumps({"error": f"ML service error: {e}"})


def _db_chart_data(chart_type, filter_therapeutic_area=None, filter_phase=None) -> str:
    conditions = ["outcome_success IS NOT NULL"]
    params = {}
    if filter_therapeutic_area:
        conditions.append("therapeutic_area ILIKE :area")
        params["area"] = f"%{filter_therapeutic_area}%"
    if filter_phase:
        conditions.append("phase = :phase")
        params["phase"] = filter_phase.upper()
    where = " AND ".join(conditions)

    with _engine.connect() as conn:
        if chart_type == "success_rate_by_phase":
            rows = conn.execute(text(f"SELECT phase as name, ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate, COUNT(*) as total FROM trials WHERE {where} AND phase IS NOT NULL GROUP BY phase ORDER BY phase"), params).mappings().fetchall()
        elif chart_type == "success_rate_by_area":
            rows = conn.execute(text(f"SELECT therapeutic_area as name, ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate, COUNT(*) as total FROM trials WHERE {where} AND therapeutic_area IS NOT NULL GROUP BY therapeutic_area ORDER BY success_rate DESC"), params).mappings().fetchall()
        elif chart_type == "sponsor_comparison":
            rows = conn.execute(text(f"SELECT sponsor_class as name, COUNT(*) as total, ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate FROM trials WHERE {where} AND sponsor_class IS NOT NULL GROUP BY sponsor_class ORDER BY total DESC LIMIT 6"), params).mappings().fetchall()
        elif chart_type == "enrollment_distribution":
            rows = conn.execute(text(f"SELECT CASE WHEN enrollment<50 THEN '<50' WHEN enrollment<200 THEN '50-200' WHEN enrollment<500 THEN '200-500' WHEN enrollment<1000 THEN '500-1K' ELSE '>1K' END as bucket, COUNT(*) as total, ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate FROM trials WHERE {where} AND enrollment IS NOT NULL GROUP BY 1 ORDER BY MIN(enrollment)"), params).mappings().fetchall()
        elif chart_type == "trial_volume_over_time":
            rows = conn.execute(text(f"SELECT DATE_TRUNC('year', start_date) as year, COUNT(*) as total FROM trials WHERE start_date IS NOT NULL AND {where} GROUP BY 1 ORDER BY 1"), params).mappings().fetchall()
        elif chart_type == "duration_vs_success":
            rows = conn.execute(text(f"SELECT CASE WHEN duration_days<180 THEN '<6mo' WHEN duration_days<365 THEN '6-12mo' WHEN duration_days<730 THEN '1-2yr' ELSE '>2yr' END as bucket, COUNT(*) as total, ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate FROM trials WHERE {where} AND duration_days IS NOT NULL GROUP BY 1 ORDER BY MIN(duration_days)"), params).mappings().fetchall()
        else:
            return json.dumps({"error": f"Unknown chart_type: {chart_type}"})

    return json.dumps({"chart_type": chart_type, "data": [dict(r) for r in rows]}, default=str)


def _db_top_sponsors(limit=10, filter_therapeutic_area=None, filter_phase=None) -> str:
    conditions = ["outcome_success IS NOT NULL", "sponsor_name IS NOT NULL"]
    params: dict = {"limit": min(limit, 50)}
    if filter_therapeutic_area:
        conditions.append("therapeutic_area ILIKE :area")
        params["area"] = f"%{filter_therapeutic_area}%"
    if filter_phase:
        conditions.append("phase = :phase")
        params["phase"] = filter_phase.upper()
    where = " AND ".join(conditions)
    sql = f"""
        SELECT sponsor_name, sponsor_class, COUNT(*) as total_trials,
               ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate_pct
        FROM trials WHERE {where}
        GROUP BY sponsor_name, sponsor_class HAVING COUNT(*) >= 3
        ORDER BY total_trials DESC LIMIT :limit
    """
    with _engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().fetchall()
    return json.dumps({"sponsors": [dict(r) for r in rows]}, default=str)


def _http_model_accuracy() -> str:
    try:
        with httpx.Client(timeout=MCP_TIMEOUT) as client:
            resp = client.get(f"{settings.ml_service_url}/benchmark")
            resp.raise_for_status()
            return resp.text
    except Exception as e:
        return json.dumps({"error": f"ML service unavailable: {e}"})


# ─── LangChain StructuredTools ────────────────────────────────────────────────

search_trials_tool = StructuredTool.from_function(
    func=lambda **kwargs: _db_search_trials(**kwargs),
    name="search_trials",
    description="Search clinical trials by keyword, phase, therapeutic area, sponsor, or status.",
    args_schema=SearchTrialsInput,
)

get_trial_details_tool = StructuredTool.from_function(
    func=lambda **kwargs: _db_get_trial_details(**kwargs),
    name="get_trial_details",
    description="Get full details for a clinical trial given its NCT ID.",
    args_schema=TrialDetailsInput,
)

get_statistics_tool = StructuredTool.from_function(
    func=lambda **kwargs: _db_get_statistics(**kwargs),
    name="get_statistics",
    description="Get aggregate success rates and stats grouped by phase, area, or sponsor type.",
    args_schema=StatisticsInput,
)

compare_groups_tool = StructuredTool.from_function(
    func=lambda **kwargs: _db_compare_groups(**kwargs),
    name="compare_groups",
    description="Compare two groups of trials (e.g., INDUSTRY vs NIH) across success rate, enrollment, and duration.",
    args_schema=CompareGroupsInput,
)

predict_tool = StructuredTool.from_function(
    func=lambda **kwargs: _http_predict(kwargs),
    name="predict_trial_success",
    description="Predict success probability for a trial by NCT ID or by providing design parameters.",
    args_schema=PredictInput,
)

chart_data_tool = StructuredTool.from_function(
    func=lambda **kwargs: _db_chart_data(**kwargs),
    name="generate_chart_data",
    description="Generate structured data for charts. Returns JSON ready for the frontend to render.",
    args_schema=ChartDataInput,
)

top_sponsors_tool = StructuredTool.from_function(
    func=lambda **kwargs: _db_top_sponsors(**kwargs),
    name="get_top_sponsors",
    description="List top pharmaceutical sponsors ranked by trial volume and success rate.",
    args_schema=TopSponsorsInput,
)

model_accuracy_tool = StructuredTool.from_function(
    func=lambda **kwargs: _http_model_accuracy(),
    name="get_model_accuracy",
    description="Return the ML model's accuracy metrics, confusion matrix, and AUC-ROC on held-out trials.",
    args_schema=type("Empty", (BaseModel,), {"__annotations__": {}}),
)

ALL_TOOLS = [
    search_trials_tool,
    get_trial_details_tool,
    get_statistics_tool,
    compare_groups_tool,
    predict_tool,
    chart_data_tool,
    top_sponsors_tool,
    model_accuracy_tool,
]
