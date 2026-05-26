"""
ClinicalTrials.gov v2 API fetcher.
Pulls trial records and normalises them into a flat dictionary
ready for insertion into the trials table.
"""
import time
from datetime import datetime
from typing import Iterator, Optional

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


COMPLETED_STATUSES = {"COMPLETED"}
FAILED_STATUSES = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}

THERAPEUTIC_AREA_MAP = {
    "neoplasm": "Oncology",
    "cancer": "Oncology",
    "carcinoma": "Oncology",
    "leukemia": "Oncology",
    "lymphoma": "Oncology",
    "tumor": "Oncology",
    "diabetes": "Endocrinology",
    "insulin": "Endocrinology",
    "cardiovascular": "Cardiology",
    "heart": "Cardiology",
    "cardiac": "Cardiology",
    "hypertension": "Cardiology",
    "alzheimer": "Neurology",
    "parkinson": "Neurology",
    "depression": "Psychiatry",
    "schizophrenia": "Psychiatry",
    "anxiety": "Psychiatry",
    "infection": "Infectious Disease",
    "hiv": "Infectious Disease",
    "covid": "Infectious Disease",
    "pneumonia": "Infectious Disease",
    "asthma": "Respiratory",
    "copd": "Respiratory",
    "pulmonary": "Respiratory",
    "arthritis": "Rheumatology",
    "lupus": "Rheumatology",
    "kidney": "Nephrology",
    "renal": "Nephrology",
    "liver": "Hepatology",
    "hepat": "Hepatology",
}


def infer_therapeutic_area(conditions: list[str]) -> str:
    combined = " ".join(conditions).lower()
    for keyword, area in THERAPEUTIC_AREA_MAP.items():
        if keyword in combined:
            return area
    return "Other"


def parse_age_to_years(age_str: Optional[str]) -> Optional[int]:
    if not age_str:
        return None
    age_str = age_str.strip().lower()
    try:
        if "year" in age_str:
            return int(age_str.split()[0])
        if "month" in age_str:
            return max(1, int(age_str.split()[0]) // 12)
        if "week" in age_str:
            return max(1, int(age_str.split()[0]) // 52)
        return int(age_str.split()[0])
    except (ValueError, IndexError):
        return None


def parse_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%B %Y", "%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def derive_outcome(status: str, has_results: bool) -> tuple[Optional[bool], float]:
    """Return (outcome_success, confidence) based on status and result availability."""
    s = status.upper() if status else ""
    if s == "COMPLETED" and has_results:
        return True, 0.85
    if s == "COMPLETED" and not has_results:
        return True, 0.60
    if s in FAILED_STATUSES:
        return False, 0.90
    return None, 0.0


def normalise_trial(study: dict) -> dict:
    proto = study.get("protocolSection", {})
    id_module = proto.get("identificationModule", {})
    status_module = proto.get("statusModule", {})
    desc_module = proto.get("descriptionModule", {})
    design_module = proto.get("designModule", {})
    arms_module = proto.get("armsInterventionsModule", {})
    sponsor_module = proto.get("sponsorCollaboratorsModule", {})
    outcomes_module = proto.get("outcomesModule", {})
    eligibility_module = proto.get("eligibilityModule", {})
    contacts_module = proto.get("contactsLocationsModule", {})
    results_section = study.get("resultsSection", {})

    nct_id = id_module.get("nctId", "")
    title = id_module.get("briefTitle", "")
    summary = desc_module.get("briefSummary", "")
    status = status_module.get("overallStatus", "")
    phase_list = design_module.get("phases", [])
    phase = phase_list[0] if phase_list else None
    study_type = design_module.get("studyType", "")

    conditions = proto.get("conditionsModule", {}).get("conditions", [])
    therapeutic_area = infer_therapeutic_area(conditions)

    interventions = arms_module.get("interventions", [])
    intervention_types = list({i.get("type", "") for i in interventions if i.get("type")})
    intervention_names = [i.get("name", "") for i in interventions if i.get("name")][:5]

    lead_sponsor = sponsor_module.get("leadSponsor", {})
    sponsor_name = lead_sponsor.get("name", "")
    sponsor_class = lead_sponsor.get("class", "")

    enrollment_info = design_module.get("enrollmentInfo", {})
    enrollment = enrollment_info.get("count")
    enrollment_type = enrollment_info.get("type", "")

    arms = design_module.get("armGroups", [])
    n_arms = len(arms) if arms else design_module.get("numberArms")

    start_raw = status_module.get("startDateStruct", {}).get("date")
    primary_completion_raw = status_module.get("primaryCompletionDateStruct", {}).get("date")
    completion_raw = status_module.get("completionDateStruct", {}).get("date")

    start_date = parse_date(start_raw)
    primary_completion_date = parse_date(primary_completion_raw)
    completion_date = parse_date(completion_raw)

    duration_days = None
    if start_date and (completion_date or primary_completion_date):
        end = completion_date or primary_completion_date
        try:
            d1 = datetime.strptime(start_date, "%Y-%m-%d")
            d2 = datetime.strptime(end, "%Y-%m-%d")
            duration_days = max(0, (d2 - d1).days)
        except ValueError:
            pass

    has_results = bool(results_section) or study.get("hasResults", False)

    primary_outcomes = outcomes_module.get("primaryOutcomes", [])
    primary_measure = primary_outcomes[0].get("measure", "") if primary_outcomes else ""
    primary_timeframe = primary_outcomes[0].get("timeFrame", "") if primary_outcomes else ""

    locations = contacts_module.get("locations", [])
    countries = list({loc.get("country", "") for loc in locations if loc.get("country")})

    outcome_success, outcome_confidence = derive_outcome(status, has_results)

    return {
        "nct_id": nct_id,
        "title": title,
        "brief_summary": summary[:2000] if summary else None,
        "overall_status": status,
        "phase": phase,
        "study_type": study_type,
        "conditions": conditions,
        "therapeutic_area": therapeutic_area,
        "intervention_types": intervention_types,
        "intervention_names": intervention_names,
        "sponsor_name": sponsor_name,
        "sponsor_class": sponsor_class,
        "enrollment": enrollment,
        "enrollment_type": enrollment_type,
        "number_of_arms": n_arms,
        "number_of_groups": None,
        "start_date": start_date,
        "primary_completion_date": primary_completion_date,
        "completion_date": completion_date,
        "duration_days": duration_days,
        "has_results": has_results,
        "primary_outcome_measure": primary_measure[:500] if primary_measure else None,
        "primary_outcome_timeframe": primary_timeframe[:200] if primary_timeframe else None,
        "locations_count": len(locations),
        "countries": countries,
        "eligibility_min_age": parse_age_to_years(eligibility_module.get("minimumAge")),
        "eligibility_max_age": parse_age_to_years(eligibility_module.get("maximumAge")),
        "eligibility_gender": eligibility_module.get("sex", "ALL"),
        "outcome_success": outcome_success,
        "outcome_confidence": outcome_confidence,
        "raw_json": study,
    }


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=2, max=30))
def fetch_page(params: dict) -> dict:
    resp = requests.get(f"{settings.ct_api_base}/studies", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def stream_trials(
    query: Optional[str] = None,
    status_filter: Optional[list[str]] = None,
    max_records: int = 10000,
) -> Iterator[dict]:
    """
    Generator that yields normalised trial dicts from ClinicalTrials.gov.
    Handles pagination transparently.
    """
    params = {
        "format": "json",
        "pageSize": min(settings.batch_size, 100),
    }
    if query:
        params["query.term"] = query
    if status_filter:
        params["filter.overallStatus"] = "|".join(status_filter)

    fetched = 0
    next_token = None

    while fetched < max_records:
        if next_token:
            params["pageToken"] = next_token
        elif "pageToken" in params:
            del params["pageToken"]

        try:
            data = fetch_page(params)
        except Exception as e:
            logger.error("Failed to fetch page: {}", e)
            break

        studies = data.get("studies", [])
        if not studies:
            break

        for study in studies:
            if fetched >= max_records:
                return
            try:
                yield normalise_trial(study)
                fetched += 1
            except Exception as e:
                logger.warning("Failed to normalise trial: {}", e)

        next_token = data.get("nextPageToken")
        if not next_token:
            break

        logger.debug("Fetched {} trials so far, next_token={}", fetched, next_token[:20])
        time.sleep(0.2)  # gentle rate-limiting
