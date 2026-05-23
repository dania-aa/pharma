"""
Seed the database with a small sample of synthetic trial data for local testing
without needing to run the full ingestion pipeline.
Run: python scripts/seed_sample_data.py
"""
import json
import os
import sys
import random
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../services/ingestion"))
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trialmind:trialmind_secret@localhost:5432/trialmind")

PHASES = ["PHASE1", "PHASE2", "PHASE3", "PHASE4"]
STATUSES_WEIGHTS = [("COMPLETED", 0.55), ("TERMINATED", 0.25), ("WITHDRAWN", 0.10), ("SUSPENDED", 0.10)]
AREAS = ["Oncology", "Cardiology", "Neurology", "Endocrinology", "Infectious Disease", "Respiratory", "Rheumatology", "Other"]
SPONSORS = ["Pfizer Inc.", "Novartis AG", "Roche AG", "Merck KGaA", "AstraZeneca", "National Cancer Institute", "NIH NHLBI"]
SPONSOR_CLASSES = {"Pfizer Inc.": "INDUSTRY", "Novartis AG": "INDUSTRY", "Roche AG": "INDUSTRY",
                   "Merck KGaA": "INDUSTRY", "AstraZeneca": "INDUSTRY",
                   "National Cancer Institute": "NIH", "NIH NHLBI": "NIH"}
INTERVENTIONS = ["DRUG", "BIOLOGICAL", "DEVICE", "BEHAVIORAL"]

rng = random.Random(42)


def random_date(start_year=2005, end_year=2020):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    return start + timedelta(days=rng.randint(0, (end - start).days))


def derive_outcome(status: str, has_results: bool):
    if status == "COMPLETED" and has_results:
        return True, 0.85
    if status == "COMPLETED":
        return True, 0.60
    if status in ("TERMINATED", "WITHDRAWN", "SUSPENDED"):
        return False, 0.90
    return None, 0.0


def generate_trials(n: int = 500):
    trials = []
    for i in range(n):
        phase = rng.choice(PHASES)
        status = rng.choices([s for s, _ in STATUSES_WEIGHTS], [w for _, w in STATUSES_WEIGHTS])[0]
        sponsor = rng.choice(SPONSORS)
        area = rng.choice(AREAS)
        start = random_date()
        duration = rng.randint(180, 2000)
        end = start + timedelta(days=duration)
        has_results = status == "COMPLETED" and rng.random() > 0.3
        outcome, confidence = derive_outcome(status, has_results)
        enrollment = max(10, int(rng.lognormvariate(5, 1.2)))
        trials.append({
            "nct_id": f"NCT{90000000 + i:08d}",
            "title": f"A Study of Drug X in {area} - {phase} ({i})",
            "brief_summary": f"This is a {phase} trial studying Drug X for {area}.",
            "overall_status": status,
            "phase": phase,
            "study_type": "INTERVENTIONAL",
            "conditions": [area],
            "therapeutic_area": area,
            "intervention_types": [rng.choice(INTERVENTIONS)],
            "intervention_names": ["Drug X"],
            "sponsor_name": sponsor,
            "sponsor_class": SPONSOR_CLASSES.get(sponsor, "INDUSTRY"),
            "enrollment": enrollment,
            "enrollment_type": "Actual",
            "number_of_arms": rng.choice([1, 2, 2, 3]),
            "number_of_groups": None,
            "start_date": str(start),
            "primary_completion_date": str(end),
            "completion_date": str(end),
            "duration_days": duration,
            "has_results": has_results,
            "primary_outcome_measure": "Overall Survival",
            "primary_outcome_timeframe": "24 months",
            "locations_count": rng.randint(1, 100),
            "countries": rng.sample(["United States", "Germany", "United Kingdom", "Japan", "France"], k=rng.randint(1, 3)),
            "eligibility_min_age": 18,
            "eligibility_max_age": rng.choice([65, 75, 99]),
            "eligibility_gender": "ALL",
            "outcome_success": outcome,
            "outcome_confidence": confidence,
            "raw_json": json.dumps({"seed": True}),
        })
    return trials


def seed():
    engine = create_engine(DATABASE_URL)
    trials = generate_trials(500)
    inserted = 0
    with engine.connect() as conn:
        for t in trials:
            try:
                conn.execute(text("""
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
                        :eligibility_gender, :outcome_success, :outcome_confidence, :raw_json::jsonb
                    ) ON CONFLICT (nct_id) DO NOTHING
                """), t)
                inserted += 1
            except Exception as e:
                print(f"Error inserting {t['nct_id']}: {e}")
        conn.commit()
    print(f"Seeded {inserted} sample trials")


if __name__ == "__main__":
    seed()
