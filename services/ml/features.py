"""
Feature engineering for the trial-success prediction model.
All transformations are deterministic and reproducible.
"""
import pandas as pd
import numpy as np
from typing import Optional

PHASE_ORDER = {
    "EARLY_PHASE1": 0,
    "PHASE1": 1,
    "PHASE1/PHASE2": 1.5,
    "PHASE2": 2,
    "PHASE2/PHASE3": 2.5,
    "PHASE3": 3,
    "PHASE4": 4,
    "NA": -1,
    None: -1,
}

SPONSOR_CLASS_MAP = {
    "INDUSTRY": 0,
    "NIH": 1,
    "OTHER_GOV": 2,
    "FED": 2,
    "INDIVIDUAL": 3,
    "NETWORK": 4,
    "AMBIG": 5,
    "UNKNOWN": 5,
    None: 5,
}

INTERVENTION_TYPE_MAP = {
    "DRUG": 0,
    "BIOLOGICAL": 1,
    "DEVICE": 2,
    "PROCEDURE": 3,
    "BEHAVIORAL": 4,
    "DIAGNOSTIC_TEST": 5,
    "DIETARY_SUPPLEMENT": 6,
    "GENETIC": 7,
    "COMBINATION_PRODUCT": 8,
    "OTHER": 9,
    None: 9,
}

THERAPEUTIC_AREA_MAP = {
    "Oncology": 0,
    "Cardiology": 1,
    "Neurology": 2,
    "Psychiatry": 3,
    "Endocrinology": 4,
    "Infectious Disease": 5,
    "Respiratory": 6,
    "Rheumatology": 7,
    "Nephrology": 8,
    "Hepatology": 9,
    "Other": 10,
}

FEATURE_COLUMNS = [
    "phase_numeric",
    "sponsor_class_encoded",
    "intervention_type_encoded",
    "therapeutic_area_encoded",
    "enrollment_log",
    "duration_days_log",
    "number_of_arms",
    "locations_count_log",
    "n_countries",
    "eligibility_min_age",
    "eligibility_max_age",
    "is_industry_sponsored",
    "is_multicenter",
    "is_international",
    "has_drug_intervention",
    "enrollment_missing",
    "duration_missing",
]


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Transform raw trial DataFrame into model-ready feature matrix."""
    out = pd.DataFrame(index=df.index)

    out["phase_numeric"] = df["phase"].map(PHASE_ORDER).fillna(-1)

    out["sponsor_class_encoded"] = (
        df["sponsor_class"].str.upper().map(SPONSOR_CLASS_MAP).fillna(5)
    )

    def _primary_intervention_type(types_list):
        if not isinstance(types_list, list) or not types_list:
            return None
        for t in types_list:
            if t and t.upper() in INTERVENTION_TYPE_MAP:
                return t.upper()
        return None

    out["intervention_type_encoded"] = (
        df["intervention_types"]
        .apply(_primary_intervention_type)
        .map(INTERVENTION_TYPE_MAP)
        .fillna(9)
    )

    out["therapeutic_area_encoded"] = (
        df["therapeutic_area"].map(THERAPEUTIC_AREA_MAP).fillna(10)
    )

    # Log-scale continuous features to reduce skew
    enrollment = pd.to_numeric(df["enrollment"], errors="coerce")
    out["enrollment_missing"] = enrollment.isna().astype(int)
    out["enrollment_log"] = np.log1p(enrollment.fillna(0))

    duration = pd.to_numeric(df["duration_days"], errors="coerce")
    out["duration_missing"] = duration.isna().astype(int)
    out["duration_days_log"] = np.log1p(duration.fillna(0))

    arms = pd.to_numeric(df["number_of_arms"], errors="coerce").fillna(1)
    out["number_of_arms"] = arms.clip(1, 20)

    locs = pd.to_numeric(df["locations_count"], errors="coerce").fillna(1)
    out["locations_count_log"] = np.log1p(locs)

    def _n_countries(x):
        if isinstance(x, list):
            return len(x)
        return 1

    out["n_countries"] = df["countries"].apply(_n_countries)

    out["eligibility_min_age"] = pd.to_numeric(df["eligibility_min_age"], errors="coerce").fillna(18)
    out["eligibility_max_age"] = pd.to_numeric(df["eligibility_max_age"], errors="coerce").fillna(65)

    # Binary flag features
    out["is_industry_sponsored"] = (
        df["sponsor_class"].str.upper().eq("INDUSTRY").astype(int)
    )
    out["is_multicenter"] = (locs > 1).astype(int)
    out["is_international"] = (out["n_countries"] > 1).astype(int)
    out["has_drug_intervention"] = df["intervention_types"].apply(
        lambda x: int("DRUG" in [t.upper() for t in x] if isinstance(x, list) else False)
    )

    return out[FEATURE_COLUMNS].astype(float)


def features_from_dict(trial: dict) -> pd.DataFrame:
    """Build a single-row feature DataFrame from a trial dict (for prediction API)."""
    row = {
        "phase": trial.get("phase"),
        "sponsor_class": trial.get("sponsor_class", ""),
        "intervention_types": trial.get("intervention_types", []),
        "therapeutic_area": trial.get("therapeutic_area", "Other"),
        "enrollment": trial.get("enrollment"),
        "duration_days": trial.get("duration_days"),
        "number_of_arms": trial.get("number_of_arms", 1),
        "locations_count": trial.get("locations_count", 1),
        "countries": trial.get("countries", []),
        "eligibility_min_age": trial.get("eligibility_min_age", 18),
        "eligibility_max_age": trial.get("eligibility_max_age", 65),
    }
    return engineer_features(pd.DataFrame([row]))
