"""
TrialMind MCP Server.

Exposes clinical trial data as structured tools that the LangGraph agent can call.
Tools:
  - search_trials          Search trials by keyword, phase, area, status
  - get_trial_details      Fetch full detail for a single trial by NCT ID
  - get_statistics         Aggregate statistics (success rates, phase breakdown, etc.)
  - compare_groups         Compare two groups of trials (e.g. industry vs NIH)
  - predict_trial_success  Call the ML service for a success probability
  - generate_chart_data    Return data formatted for chart rendering
  - get_top_sponsors       List top sponsors by trial volume and success rate
  - get_phase_breakdown    Success/failure counts broken down by phase
"""
import json
import os
import sys
from typing import Any, Optional

import httpx
import pandas as pd
from loguru import logger
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, text


# ─── Config ───────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    database_url: str = "postgresql://trialmind:trialmind@localhost:5432/trialmind"
    ml_service_url: str = "http://localhost:8001"
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
engine = create_engine(settings.database_url)

# ─── MCP Server setup ─────────────────────────────────────────────────────────

server = Server("trialmind")


# ─── Tool definitions ─────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_trials",
            description=(
                "Search the TrialMind database for clinical trials. "
                "Returns a list of matching trials with key fields. "
                "Use this to find trials by condition, phase, sponsor, or keyword."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Free-text search in title/conditions"},
                    "phase": {"type": "string", "description": "Trial phase, e.g. PHASE3, PHASE2"},
                    "therapeutic_area": {"type": "string", "description": "e.g. Oncology, Cardiology"},
                    "sponsor_class": {"type": "string", "description": "INDUSTRY, NIH, OTHER_GOV"},
                    "status": {"type": "string", "description": "COMPLETED, TERMINATED, WITHDRAWN"},
                    "outcome_success": {"type": "boolean", "description": "Filter by known outcome"},
                    "limit": {"type": "integer", "default": 20, "description": "Max results (max 100)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_trial_details",
            description="Get full details for a specific clinical trial by its NCT ID (e.g. NCT01234567).",
            inputSchema={
                "type": "object",
                "properties": {
                    "nct_id": {"type": "string", "description": "The NCT ID of the trial"},
                },
                "required": ["nct_id"],
            },
        ),
        Tool(
            name="get_statistics",
            description=(
                "Get aggregate statistics from the trial database. "
                "Returns success rates, trial counts, and distributions. "
                "Use this to answer questions like 'what percentage of Phase 3 trials succeed?'"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "group_by": {
                        "type": "string",
                        "enum": ["phase", "therapeutic_area", "sponsor_class", "overall_status"],
                        "description": "Dimension to group statistics by",
                    },
                    "filter_therapeutic_area": {"type": "string"},
                    "filter_phase": {"type": "string"},
                    "filter_sponsor_class": {"type": "string"},
                },
                "required": ["group_by"],
            },
        ),
        Tool(
            name="compare_groups",
            description=(
                "Compare two groups of trials and return success rates, enrollment stats, "
                "and duration metrics for each. "
                "Example: compare industry vs NIH sponsored trials in oncology."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "dimension": {
                        "type": "string",
                        "enum": ["sponsor_class", "phase", "therapeutic_area"],
                        "description": "The dimension to split groups on",
                    },
                    "group_a": {"type": "string", "description": "Value for group A"},
                    "group_b": {"type": "string", "description": "Value for group B"},
                    "filter_therapeutic_area": {"type": "string", "description": "Optional area filter"},
                },
                "required": ["dimension", "group_a", "group_b"],
            },
        ),
        Tool(
            name="predict_trial_success",
            description=(
                "Predict the probability of success for a clinical trial based on its design parameters. "
                "Returns a probability score, label, and the top contributing factors."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "nct_id": {"type": "string", "description": "NCT ID to look up and predict"},
                    "phase": {"type": "string"},
                    "sponsor_class": {"type": "string"},
                    "intervention_types": {"type": "array", "items": {"type": "string"}},
                    "therapeutic_area": {"type": "string"},
                    "enrollment": {"type": "integer"},
                    "duration_days": {"type": "integer"},
                    "number_of_arms": {"type": "integer"},
                    "locations_count": {"type": "integer"},
                    "countries": {"type": "array", "items": {"type": "string"}},
                },
                "required": [],
            },
        ),
        Tool(
            name="generate_chart_data",
            description=(
                "Generate chart-ready data for the frontend dashboard. "
                "Returns structured JSON that maps directly to chart components. "
                "Use this when the user asks for a chart, graph, or visualisation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": [
                            "success_rate_by_phase",
                            "success_rate_by_area",
                            "enrollment_distribution",
                            "trial_volume_over_time",
                            "sponsor_comparison",
                            "duration_vs_success",
                        ],
                        "description": "The type of chart to generate data for",
                    },
                    "filter_therapeutic_area": {"type": "string"},
                    "filter_phase": {"type": "string"},
                },
                "required": ["chart_type"],
            },
        ),
        Tool(
            name="get_top_sponsors",
            description="List the top pharmaceutical sponsors by trial volume and success rate.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                    "filter_therapeutic_area": {"type": "string"},
                    "filter_phase": {"type": "string"},
                },
                "required": [],
            },
        ),
        Tool(
            name="get_model_accuracy",
            description=(
                "Return the ML model's accuracy metrics on historical held-out trials. "
                "Use this when the user asks how accurate the predictions are, "
                "or wants to understand model performance."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


# ─── Tool implementations ─────────────────────────────────────────────────────

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        result = await _dispatch(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, default=str, indent=2))]
    except Exception as e:
        logger.exception("Tool {} failed", name)
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict) -> Any:
    if name == "search_trials":
        return _search_trials(**args)
    if name == "get_trial_details":
        return _get_trial_details(**args)
    if name == "get_statistics":
        return _get_statistics(**args)
    if name == "compare_groups":
        return _compare_groups(**args)
    if name == "predict_trial_success":
        return await _predict_trial_success(**args)
    if name == "generate_chart_data":
        return _generate_chart_data(**args)
    if name == "get_top_sponsors":
        return _get_top_sponsors(**args)
    if name == "get_model_accuracy":
        return await _get_model_accuracy()
    raise ValueError(f"Unknown tool: {name}")


# ─── Tool logic ───────────────────────────────────────────────────────────────

def _search_trials(
    query: str = None,
    phase: str = None,
    therapeutic_area: str = None,
    sponsor_class: str = None,
    status: str = None,
    outcome_success: bool = None,
    limit: int = 20,
) -> dict:
    conditions = ["1=1"]
    params: dict = {"limit": min(limit, 100)}

    if query:
        conditions.append("(title ILIKE :query OR :query2 = ANY(conditions))")
        params["query"] = f"%{query}%"
        params["query2"] = query
    if phase:
        conditions.append("phase = :phase")
        params["phase"] = phase.upper()
    if therapeutic_area:
        conditions.append("therapeutic_area ILIKE :area")
        params["area"] = f"%{therapeutic_area}%"
    if sponsor_class:
        conditions.append("sponsor_class = :sponsor_class")
        params["sponsor_class"] = sponsor_class.upper()
    if status:
        conditions.append("overall_status = :status")
        params["status"] = status.upper()
    if outcome_success is not None:
        conditions.append("outcome_success = :outcome_success")
        params["outcome_success"] = outcome_success

    sql = f"""
        SELECT nct_id, title, overall_status, phase, therapeutic_area,
               sponsor_name, sponsor_class, enrollment, duration_days,
               has_results, outcome_success, start_date, completion_date
        FROM trials
        WHERE {' AND '.join(conditions)}
        ORDER BY completion_date DESC NULLS LAST
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().fetchall()

    trials = [dict(r) for r in rows]
    return {"count": len(trials), "trials": trials}


def _get_trial_details(nct_id: str) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT nct_id, title, brief_summary, overall_status, phase,
                       study_type, conditions, therapeutic_area, intervention_types,
                       intervention_names, sponsor_name, sponsor_class, enrollment,
                       number_of_arms, start_date, primary_completion_date,
                       completion_date, duration_days, has_results,
                       primary_outcome_measure, primary_outcome_timeframe,
                       locations_count, countries, eligibility_min_age,
                       eligibility_max_age, eligibility_gender,
                       outcome_success, outcome_confidence
                FROM trials WHERE nct_id = :id
            """),
            {"id": nct_id.upper()},
        ).mappings().fetchone()

    if not row:
        return {"error": f"Trial {nct_id} not found in database"}
    return dict(row)


def _get_statistics(
    group_by: str,
    filter_therapeutic_area: str = None,
    filter_phase: str = None,
    filter_sponsor_class: str = None,
) -> dict:
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
        SELECT
            {group_by} as group_name,
            COUNT(*) as total,
            SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes,
            ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END) * 100, 1) as success_rate_pct,
            ROUND(AVG(enrollment)::numeric, 0) as avg_enrollment,
            ROUND(AVG(duration_days)::numeric, 0) as avg_duration_days
        FROM trials
        WHERE {where}
        GROUP BY {group_by}
        ORDER BY total DESC
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().fetchall()

    return {"group_by": group_by, "data": [dict(r) for r in rows]}


def _compare_groups(
    dimension: str,
    group_a: str,
    group_b: str,
    filter_therapeutic_area: str = None,
) -> dict:
    area_filter = ""
    params_a = {"val": group_a}
    params_b = {"val": group_b}
    if filter_therapeutic_area:
        area_filter = "AND therapeutic_area ILIKE :area"
        params_a["area"] = params_b["area"] = f"%{filter_therapeutic_area}%"

    def _query(val):
        sql = f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes,
                ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate_pct,
                ROUND(AVG(enrollment)::numeric,0) as avg_enrollment,
                ROUND(AVG(duration_days)::numeric,0) as avg_duration_days,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY enrollment) as median_enrollment
            FROM trials
            WHERE {dimension} = :val
              AND outcome_success IS NOT NULL
              {area_filter}
        """
        with engine.connect() as conn:
            row = conn.execute(text(sql), {"val": val, **({} if not filter_therapeutic_area else {"area": f"%{filter_therapeutic_area}%"})}).mappings().fetchone()
        return dict(row) if row else {}

    return {
        "dimension": dimension,
        "group_a": {"name": group_a, "stats": _query(group_a)},
        "group_b": {"name": group_b, "stats": _query(group_b)},
    }


async def _predict_trial_success(**kwargs) -> dict:
    nct_id = kwargs.get("nct_id")
    if nct_id:
        url = f"{settings.ml_service_url}/predict/{nct_id.upper()}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    else:
        url = f"{settings.ml_service_url}/predict"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=kwargs)
            resp.raise_for_status()
            return resp.json()


def _generate_chart_data(
    chart_type: str,
    filter_therapeutic_area: str = None,
    filter_phase: str = None,
) -> dict:
    conditions = ["outcome_success IS NOT NULL"]
    params = {}
    if filter_therapeutic_area:
        conditions.append("therapeutic_area ILIKE :area")
        params["area"] = f"%{filter_therapeutic_area}%"
    if filter_phase:
        conditions.append("phase = :phase")
        params["phase"] = filter_phase.upper()
    where = " AND ".join(conditions)

    with engine.connect() as conn:
        if chart_type == "success_rate_by_phase":
            rows = conn.execute(text(f"""
                SELECT phase as name,
                       ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate,
                       COUNT(*) as total
                FROM trials WHERE {where} AND phase IS NOT NULL
                GROUP BY phase ORDER BY phase
            """), params).mappings().fetchall()
            return {"chart_type": chart_type, "data": [dict(r) for r in rows]}

        if chart_type == "success_rate_by_area":
            rows = conn.execute(text(f"""
                SELECT therapeutic_area as name,
                       ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate,
                       COUNT(*) as total
                FROM trials WHERE {where} AND therapeutic_area IS NOT NULL
                GROUP BY therapeutic_area ORDER BY success_rate DESC
            """), params).mappings().fetchall()
            return {"chart_type": chart_type, "data": [dict(r) for r in rows]}

        if chart_type == "enrollment_distribution":
            rows = conn.execute(text(f"""
                SELECT
                    CASE
                        WHEN enrollment < 50 THEN '<50'
                        WHEN enrollment < 200 THEN '50-200'
                        WHEN enrollment < 500 THEN '200-500'
                        WHEN enrollment < 1000 THEN '500-1K'
                        WHEN enrollment < 5000 THEN '1K-5K'
                        ELSE '>5K'
                    END as bucket,
                    COUNT(*) as total,
                    ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate
                FROM trials WHERE {where} AND enrollment IS NOT NULL
                GROUP BY 1 ORDER BY MIN(enrollment)
            """), params).mappings().fetchall()
            return {"chart_type": chart_type, "data": [dict(r) for r in rows]}

        if chart_type == "trial_volume_over_time":
            rows = conn.execute(text(f"""
                SELECT
                    DATE_TRUNC('year', start_date) as year,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes
                FROM trials
                WHERE start_date IS NOT NULL AND {where}
                GROUP BY 1 ORDER BY 1
            """), params).mappings().fetchall()
            return {"chart_type": chart_type, "data": [dict(r) for r in rows]}

        if chart_type == "sponsor_comparison":
            rows = conn.execute(text(f"""
                SELECT sponsor_class as name,
                       COUNT(*) as total,
                       ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate,
                       ROUND(AVG(enrollment)::numeric,0) as avg_enrollment
                FROM trials WHERE {where} AND sponsor_class IS NOT NULL
                GROUP BY sponsor_class ORDER BY total DESC LIMIT 6
            """), params).mappings().fetchall()
            return {"chart_type": chart_type, "data": [dict(r) for r in rows]}

        if chart_type == "duration_vs_success":
            rows = conn.execute(text(f"""
                SELECT
                    CASE
                        WHEN duration_days < 180 THEN '<6 months'
                        WHEN duration_days < 365 THEN '6-12 months'
                        WHEN duration_days < 730 THEN '1-2 years'
                        WHEN duration_days < 1825 THEN '2-5 years'
                        ELSE '>5 years'
                    END as duration_bucket,
                    COUNT(*) as total,
                    ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate
                FROM trials WHERE {where} AND duration_days IS NOT NULL
                GROUP BY 1 ORDER BY MIN(duration_days)
            """), params).mappings().fetchall()
            return {"chart_type": chart_type, "data": [dict(r) for r in rows]}

    return {"error": f"Unknown chart type: {chart_type}"}


def _get_top_sponsors(
    limit: int = 10,
    filter_therapeutic_area: str = None,
    filter_phase: str = None,
) -> dict:
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
        SELECT sponsor_name, sponsor_class,
               COUNT(*) as total_trials,
               SUM(CASE WHEN outcome_success THEN 1 ELSE 0 END) as successes,
               ROUND(AVG(CASE WHEN outcome_success THEN 1.0 ELSE 0.0 END)*100,1) as success_rate_pct,
               ROUND(AVG(enrollment)::numeric,0) as avg_enrollment
        FROM trials
        WHERE {where}
        GROUP BY sponsor_name, sponsor_class
        HAVING COUNT(*) >= 3
        ORDER BY total_trials DESC
        LIMIT :limit
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().fetchall()
    return {"sponsors": [dict(r) for r in rows]}


async def _get_model_accuracy() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{settings.ml_service_url}/benchmark")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {"error": f"ML service unavailable: {e}"}


# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
