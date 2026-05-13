-- TrialMind Database Schema
-- PostgreSQL with pgvector extension for embeddings

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ─────────────────────────────────────────────
-- Core clinical trials table
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trials (
    id                      SERIAL PRIMARY KEY,
    nct_id                  VARCHAR(20) UNIQUE NOT NULL,
    title                   TEXT NOT NULL,
    brief_summary           TEXT,
    overall_status          VARCHAR(50),
    phase                   VARCHAR(20),
    study_type              VARCHAR(50),
    conditions              TEXT[],
    therapeutic_area        VARCHAR(100),
    intervention_types      TEXT[],
    intervention_names      TEXT[],
    sponsor_name            TEXT,
    sponsor_class           VARCHAR(50),     -- INDUSTRY, NIH, OTHER_GOV, INDIVIDUAL, etc.
    enrollment              INTEGER,
    enrollment_type         VARCHAR(20),     -- Actual, Anticipated
    number_of_arms          INTEGER,
    number_of_groups        INTEGER,
    start_date              DATE,
    primary_completion_date DATE,
    completion_date         DATE,
    duration_days           INTEGER,
    has_results             BOOLEAN DEFAULT FALSE,
    primary_outcome_measure TEXT,
    primary_outcome_timeframe VARCHAR(200),
    locations_count         INTEGER,
    countries               TEXT[],
    eligibility_min_age     INTEGER,
    eligibility_max_age     INTEGER,
    eligibility_gender      VARCHAR(10),
    outcome_success         BOOLEAN,         -- derived label for ML
    outcome_confidence      FLOAT,           -- 0-1 confidence in the label
    raw_json                JSONB,
    ingested_at             TIMESTAMP DEFAULT NOW(),
    updated_at              TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trials_nct_id ON trials(nct_id);
CREATE INDEX IF NOT EXISTS idx_trials_status ON trials(overall_status);
CREATE INDEX IF NOT EXISTS idx_trials_phase ON trials(phase);
CREATE INDEX IF NOT EXISTS idx_trials_therapeutic_area ON trials(therapeutic_area);
CREATE INDEX IF NOT EXISTS idx_trials_sponsor_class ON trials(sponsor_class);
CREATE INDEX IF NOT EXISTS idx_trials_has_results ON trials(has_results);
CREATE INDEX IF NOT EXISTS idx_trials_outcome_success ON trials(outcome_success);
CREATE INDEX IF NOT EXISTS idx_trials_conditions ON trials USING GIN(conditions);
CREATE INDEX IF NOT EXISTS idx_trials_title_trgm ON trials USING GIN(title gin_trgm_ops);

-- ─────────────────────────────────────────────
-- ML model predictions log
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    nct_id          VARCHAR(20),
    model_version   VARCHAR(50),
    features_json   JSONB,
    predicted_proba FLOAT,
    predicted_label BOOLEAN,
    actual_label    BOOLEAN,
    correct         BOOLEAN,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_nct_id ON predictions(nct_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model_version ON predictions(model_version);

-- ─────────────────────────────────────────────
-- Model performance snapshots
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_metrics (
    id              SERIAL PRIMARY KEY,
    model_version   VARCHAR(50),
    accuracy        FLOAT,
    precision_score FLOAT,
    recall_score    FLOAT,
    f1_score        FLOAT,
    auc_roc         FLOAT,
    n_train         INTEGER,
    n_test          INTEGER,
    feature_importance JSONB,
    trained_at      TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Agent conversation history (also mirrored in DynamoDB)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              VARCHAR(36) PRIMARY KEY DEFAULT uuid_generate_v4()::text,
    title           TEXT,
    messages        JSONB DEFAULT '[]',
    charts          JSONB DEFAULT '[]',
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Saved analysis results / charts
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS saved_analyses (
    id              SERIAL PRIMARY KEY,
    conversation_id VARCHAR(36),
    query           TEXT,
    chart_type      VARCHAR(50),
    chart_data      JSONB,
    insight_text    TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- Ingestion job tracking
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              SERIAL PRIMARY KEY,
    job_type        VARCHAR(50),
    status          VARCHAR(20),    -- running, completed, failed
    records_fetched INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated  INTEGER DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMP DEFAULT NOW(),
    finished_at     TIMESTAMP
);
