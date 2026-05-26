"""
TrialMind data ingestion CLI.
Usage:
    python main.py --max-trials 10000
    python main.py --query "oncology phase 3" --max-trials 5000
    python main.py --init-db
"""
import argparse
import json
import sys
from datetime import datetime

from loguru import logger
from sqlalchemy import text
from tqdm import tqdm

from config import settings
from database import SessionLocal, init_db
from fetcher import COMPLETED_STATUSES, FAILED_STATUSES, stream_trials


def upsert_trial(conn, trial: dict) -> str:
    """Insert or update a single trial. Returns 'inserted' | 'updated' | 'skipped'."""
    # Check existence
    existing = conn.execute(
        text("SELECT id, updated_at FROM trials WHERE nct_id = :nct_id"),
        {"nct_id": trial["nct_id"]},
    ).fetchone()

    # Serialise list/dict fields for psycopg2
    for key in ("conditions", "intervention_types", "intervention_names", "countries"):
        if isinstance(trial.get(key), list):
            trial[key] = trial[key] or []

    trial["raw_json"] = json.dumps(trial["raw_json"]) if trial.get("raw_json") else None

    if existing:
        conn.execute(
            text("""
                UPDATE trials SET
                    title = :title,
                    brief_summary = :brief_summary,
                    overall_status = :overall_status,
                    phase = :phase,
                    study_type = :study_type,
                    conditions = :conditions,
                    therapeutic_area = :therapeutic_area,
                    intervention_types = :intervention_types,
                    intervention_names = :intervention_names,
                    sponsor_name = :sponsor_name,
                    sponsor_class = :sponsor_class,
                    enrollment = :enrollment,
                    enrollment_type = :enrollment_type,
                    number_of_arms = :number_of_arms,
                    start_date = :start_date,
                    primary_completion_date = :primary_completion_date,
                    completion_date = :completion_date,
                    duration_days = :duration_days,
                    has_results = :has_results,
                    primary_outcome_measure = :primary_outcome_measure,
                    primary_outcome_timeframe = :primary_outcome_timeframe,
                    locations_count = :locations_count,
                    countries = :countries,
                    eligibility_min_age = :eligibility_min_age,
                    eligibility_max_age = :eligibility_max_age,
                    eligibility_gender = :eligibility_gender,
                    outcome_success = :outcome_success,
                    outcome_confidence = :outcome_confidence,
                    raw_json = CAST(:raw_json AS JSONB),
                    updated_at = NOW()
                WHERE nct_id = :nct_id
            """),
            trial,
        )
        return "updated"
    else:
        conn.execute(
            text("""
                INSERT INTO trials (
                    nct_id, title, brief_summary, overall_status, phase, study_type,
                    conditions, therapeutic_area, intervention_types, intervention_names,
                    sponsor_name, sponsor_class, enrollment, enrollment_type, number_of_arms,
                    start_date, primary_completion_date, completion_date, duration_days,
                    has_results, primary_outcome_measure, primary_outcome_timeframe,
                    locations_count, countries, eligibility_min_age, eligibility_max_age,
                    eligibility_gender, outcome_success, outcome_confidence, raw_json
                ) VALUES (
                    :nct_id, :title, :brief_summary, :overall_status, :phase, :study_type,
                    :conditions, :therapeutic_area, :intervention_types, :intervention_names,
                    :sponsor_name, :sponsor_class, :enrollment, :enrollment_type, :number_of_arms,
                    :start_date, :primary_completion_date, :completion_date, :duration_days,
                    :has_results, :primary_outcome_measure, :primary_outcome_timeframe,
                    :locations_count, :countries, :eligibility_min_age, :eligibility_max_age,
                    :eligibility_gender, :outcome_success, :outcome_confidence, CAST(:raw_json AS JSONB)
                )
            """),
            trial,
        )
        return "inserted"


def run_ingestion(query: str | None, max_trials: int, status_filter: list[str] | None):
    db = SessionLocal()
    inserted = updated = errors = 0

    # Log job start
    job_id = db.execute(
        text("""
            INSERT INTO ingestion_jobs (job_type, status)
            VALUES ('full_ingest', 'running')
            RETURNING id
        """)
    ).scalar()
    db.commit()

    logger.info("Starting ingestion | max_trials={} query={}", max_trials, query)

    try:
        stream = stream_trials(
            query=query,
            status_filter=status_filter,
            max_records=max_trials,
        )
        with tqdm(total=max_trials, unit="trials") as pbar:
            for trial in stream:
                try:
                    result = upsert_trial(db, trial)
                    if result == "inserted":
                        inserted += 1
                    else:
                        updated += 1
                    db.commit()
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.warning("Error upserting {}: {}", trial.get("nct_id"), e)
                pbar.update(1)
                pbar.set_postfix(inserted=inserted, updated=updated, errors=errors)

        db.execute(
            text("""
                UPDATE ingestion_jobs SET
                    status = 'completed',
                    records_fetched = :fetched,
                    records_inserted = :inserted,
                    records_updated = :updated,
                    finished_at = NOW()
                WHERE id = :id
            """),
            {"fetched": inserted + updated, "inserted": inserted, "updated": updated, "id": job_id},
        )
        db.commit()
        logger.success(
            "Ingestion complete: {} inserted, {} updated, {} errors",
            inserted, updated, errors,
        )

    except Exception as e:
        db.execute(
            text("UPDATE ingestion_jobs SET status='failed', error_message=:err, finished_at=NOW() WHERE id=:id"),
            {"err": str(e), "id": job_id},
        )
        db.commit()
        logger.error("Ingestion failed: {}", e)
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="TrialMind data ingestion")
    parser.add_argument("--init-db", action="store_true", help="Initialise database schema and exit")
    parser.add_argument("--query", default=None, help="Free-text query filter for trials")
    parser.add_argument("--max-trials", type=int, default=10000, help="Maximum trials to ingest")
    parser.add_argument(
        "--status",
        nargs="+",
        default=["COMPLETED", "TERMINATED", "WITHDRAWN"],
        help="Trial statuses to include",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    if args.init_db:
        logger.info("Initialising database schema...")
        init_db()
        return

    run_ingestion(
        query=args.query,
        max_trials=args.max_trials,
        status_filter=args.status,
    )


if __name__ == "__main__":
    main()
