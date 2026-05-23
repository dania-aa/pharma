"""Unit tests for feature engineering."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
import pytest
from features import engineer_features, features_from_dict, FEATURE_COLUMNS


def make_trial(**overrides):
    base = {
        "phase": "PHASE3",
        "sponsor_class": "INDUSTRY",
        "intervention_types": ["DRUG"],
        "therapeutic_area": "Oncology",
        "enrollment": 300,
        "duration_days": 730,
        "number_of_arms": 2,
        "locations_count": 20,
        "countries": ["United States", "Germany"],
        "eligibility_min_age": 18,
        "eligibility_max_age": 75,
    }
    base.update(overrides)
    return base


def test_feature_columns_complete():
    trial = make_trial()
    X = features_from_dict(trial)
    assert list(X.columns) == FEATURE_COLUMNS
    assert len(X) == 1


def test_no_nan_in_features():
    trial = make_trial()
    X = features_from_dict(trial)
    assert not X.isnull().any().any(), "Features should not contain NaN"


def test_missing_values_handled():
    """Trials with missing enrollment, duration, age should not raise."""
    trial = make_trial(enrollment=None, duration_days=None, eligibility_min_age=None)
    X = features_from_dict(trial)
    assert not X.isnull().any().any()


def test_is_industry_sponsored():
    industry_trial = make_trial(sponsor_class="INDUSTRY")
    nih_trial = make_trial(sponsor_class="NIH")
    X_ind = features_from_dict(industry_trial)
    X_nih = features_from_dict(nih_trial)
    assert X_ind["is_industry_sponsored"].iloc[0] == 1
    assert X_nih["is_industry_sponsored"].iloc[0] == 0


def test_is_international():
    multi = make_trial(countries=["US", "UK", "Germany"])
    single = make_trial(countries=["United States"])
    assert features_from_dict(multi)["is_international"].iloc[0] == 1
    assert features_from_dict(single)["is_international"].iloc[0] == 0


def test_phase_encoding():
    p3 = features_from_dict(make_trial(phase="PHASE3"))
    p1 = features_from_dict(make_trial(phase="PHASE1"))
    assert p3["phase_numeric"].iloc[0] > p1["phase_numeric"].iloc[0]


def test_enrollment_log_transform():
    large = features_from_dict(make_trial(enrollment=10000))
    small = features_from_dict(make_trial(enrollment=10))
    assert large["enrollment_log"].iloc[0] > small["enrollment_log"].iloc[0]


def test_batch_features():
    trials = [make_trial(enrollment=i * 100) for i in range(1, 6)]
    df = pd.DataFrame(trials)
    X = engineer_features(df)
    assert len(X) == 5
    assert list(X.columns) == FEATURE_COLUMNS
