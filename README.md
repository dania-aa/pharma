# TrialMind — Clinical Trial Intelligence Platform

An agentic AI platform that ingests real clinical trial data from ClinicalTrials.gov, predicts trial success using machine learning, and lets researchers interrogate the data through a conversational AI agent with automatic chart generation.

---

## What It Does

1. **Ingests real data** — pulls hundreds of thousands of trials from the ClinicalTrials.gov public API into PostgreSQL
2. **Predicts trial success** — an XGBoost classifier trained on historical outcomes predicts the probability a given trial design will succeed, with SHAP-based feature explanations
3. **Conversational AI agent** — a LangGraph/Claude agent you can ask natural language questions: *"What is the success rate of Phase 3 oncology trials?"*, *"Compare industry vs NIH-sponsored trials"*, *"Show me a chart of trial volume over time"*
4. **Automatic chart generation** — the agent calls chart tools and the frontend renders them inline in the conversation
5. **Accuracy benchmarking** — a dedicated dashboard shows model accuracy, confusion matrix, AUC-ROC, and per-phase/per-area breakdowns measured against held-out historical trials

---

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────────┐
│   Browser   │────▶│            React.js Frontend (Vite)              │
└─────────────┘     │  Chat · Benchmark · Predict · Charts (Recharts)  │
                    └─────────────────┬────────────────────────────────┘
                                      │ HTTP
                    ┌─────────────────▼────────────────────────────────┐
                    │         Node.js API Gateway (Express)            │
                    │    Rate limiting · CORS · Auth · Routing         │
                    └──────┬───────────────────────┬───────────────────┘
                           │                       │
              ┌────────────▼──────┐   ┌────────────▼──────────────┐
              │  Agent Service    │   │     ML Service            │
              │  Python FastAPI   │   │     Python FastAPI        │
              │  LangGraph agent  │   │     XGBoost predictor     │
              │  Claude via       │   │     /predict              │
              │  AWS Bedrock      │   │     /benchmark            │
              └──────┬────────────┘   └─────────┬─────────────────┘
                     │ SQL                       │ SQL
              ┌──────▼────────────────────────────▼─────────────────┐
              │              PostgreSQL (RDS)                        │
              │   trials · predictions · model_metrics · convos      │
              └──────────────────────────────────────────────────────┘
                     │
              ┌──────▼──────────────┐
              │  DynamoDB           │
              │  conversation logs  │
              │  event audit trail  │
              └─────────────────────┘
```

### Microservices

| Service | Language | Port | Responsibility |
|---|---|---|---|
| `ingestion` | Python | — | One-shot: pulls ClinicalTrials.gov → PostgreSQL |
| `ml` | Python / FastAPI | 8001 | XGBoost prediction, model training, benchmarking |
| `agent` | Python / FastAPI | 8002 | LangGraph agent (Claude via AWS Bedrock) |
| `gateway` | Node.js / Express | 3000 | API gateway, rate limiting, routing |
| `frontend` | React.js / Vite | 80/5173 | Dashboard, chat, charts |
| `mcp-server` | Python / MCP SDK | stdio | MCP server exposing trial tools to agents |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | AWS Bedrock — Claude 3.5 Sonnet |
| **Agent framework** | LangChain + LangGraph (ReAct multi-step agent) |
| **MCP server** | Anthropic MCP SDK (Python) |
| **ML model** | XGBoost + scikit-learn + SHAP |
| **Backend** | Python FastAPI (ML, Agent), Node.js Express (Gateway) |
| **Frontend** | React.js + Vite + Tailwind CSS + Recharts |
| **SQL database** | PostgreSQL 16 (RDS in prod) |
| **NoSQL database** | DynamoDB (conversation history, events) |
| **Cloud** | AWS (Bedrock, ECS Fargate, RDS, DynamoDB, S3, ECR, CloudWatch) |
| **IaC** | AWS CDK (Python) |
| **CI/CD** | GitHub Actions |
| **Containers** | Docker + Docker Compose |
| **Data source** | ClinicalTrials.gov v2 API (public, no key required) |

---

## Project Structure

```
trialmind/
├── services/
│   ├── ingestion/          # ClinicalTrials.gov → PostgreSQL pipeline
│   │   ├── fetcher.py      # API client, pagination, normalisation
│   │   ├── main.py         # CLI: --init-db, --max-trials, --query
│   │   └── database.py
│   ├── ml/                 # Trial success prediction
│   │   ├── features.py     # Feature engineering (17 features)
│   │   ├── train.py        # XGBoost training + SHAP + DB metrics logging
│   │   ├── predict.py      # Inference helpers
│   │   └── main.py         # FastAPI: /predict, /benchmark, /model/info
│   ├── mcp-server/         # MCP server (8 tools)
│   │   └── server.py
│   ├── agent/              # LangGraph conversational agent
│   │   ├── agent.py        # Graph definition (ReAct loop)
│   │   ├── tools.py        # LangChain tool wrappers (DB + ML)
│   │   └── main.py         # FastAPI: /chat, /conversations
│   └── gateway/            # Node.js API gateway
│       └── src/
│           ├── index.js
│           └── routes/
├── frontend/               # React.js dashboard
│   └── src/
│       ├── pages/          # ChatPage, BenchmarkPage, PredictPage
│       ├── components/     # ChartRenderer, MessageBubble, Sidebar
│       ├── hooks/          # useChat
│       └── api/            # client.js
├── database/
│   └── schema.sql          # Full PostgreSQL schema
├── infra/                  # AWS CDK (Python)
│   └── stacks/             # StorageStack, DatabaseStack, ComputeStack, MonitoringStack
├── .github/workflows/
│   ├── ci.yml              # Lint, test, build on every push/PR
│   └── deploy.yml          # Build → ECR → CDK deploy → migrate
└── docker-compose.yml      # Full local stack
```

---

## Quick Start (Local)

### Prerequisites
- Docker & Docker Compose
- AWS credentials (for the Bedrock-powered agent; optional if you want to test without it)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and add your AWS credentials if you want the agent to work
```

### 2. Start the stack

```bash
docker compose up -d
```

This starts: PostgreSQL, ML service, Agent service, Gateway, Frontend.

### 3. Ingest clinical trial data

```bash
# Ingest 10,000 completed/terminated trials (takes ~5 minutes)
docker compose --profile ingest run ingestion --max-trials 10000

# Or target a specific area
docker compose --profile ingest run ingestion --query "oncology" --max-trials 5000
```

### 4. Train the ML model

```bash
docker compose --profile train run train
```

This trains an XGBoost classifier on the ingested data, runs 5-fold CV, computes SHAP values, and stores metrics in the database.

### 5. Open the dashboard

- **Frontend**: http://localhost (port 80)
- **Gateway API**: http://localhost:3000
- **ML service**: http://localhost:8001/docs
- **Agent service**: http://localhost:8002/docs

---

## The ML Model

### Features (17 total)

| Feature | Description |
|---|---|
| `phase_numeric` | Trial phase encoded as 0–4 |
| `sponsor_class_encoded` | INDUSTRY=0, NIH=1, OTHER_GOV=2, etc. |
| `therapeutic_area_encoded` | Oncology, Cardiology, Neurology, etc. |
| `enrollment_log` | Log-scaled enrollment count |
| `duration_days_log` | Log-scaled trial duration |
| `number_of_arms` | Number of study arms |
| `is_industry_sponsored` | Binary: industry vs academic |
| `is_multicenter` | Binary: multiple sites |
| `is_international` | Binary: multiple countries |
| `has_drug_intervention` | Binary: drug vs other intervention |
| ... and more | See `services/ml/features.py` |

### Outcome Labels

- **Success (1)**: Status = COMPLETED and has posted results → confidence 0.85
- **Success (1)**: Status = COMPLETED, no results → confidence 0.60
- **Failure (0)**: Status = TERMINATED / WITHDRAWN / SUSPENDED → confidence 0.90

Only trials with confidence ≥ 0.60 are used for training.

### Accuracy Testing

The `/benchmark` endpoint runs predictions on the held-out test set and returns:
- Overall accuracy, precision, recall, F1, AUC-ROC
- Confusion matrix (TP, TN, FP, FN)
- Calibration curve
- Breakdowns by phase and therapeutic area

This directly answers: *"How accurate is the AI at predicting historical trial outcomes?"*

---

## The Agent

The LangGraph agent uses a ReAct (Reason + Act) loop:

```
User question
     │
     ▼
[Agent] → decide which tool(s) to call
     │
     ▼
[Tools] → search_trials | get_statistics | compare_groups |
          predict_trial_success | generate_chart_data |
          get_top_sponsors | get_model_accuracy
     │
     ▼
[Agent] → synthesise results, decide if more tool calls needed
     │
     ▼
[Agent] → formulate final answer with charts embedded
```

### Example questions the agent handles

- *"What percentage of Phase 3 oncology trials succeed?"*
- *"Show me a bar chart of success rates by therapeutic area"*
- *"Compare the success rates of industry-sponsored vs NIH trials in cardiology"*
- *"List the top 10 sponsors by volume and success rate"*
- *"Given a Phase 2 drug trial with 200 patients and 2 arms, what is the predicted success probability?"*
- *"How accurate is the prediction model on historical data? Show the confusion matrix"*

---

## MCP Server

The MCP server (`services/mcp-server/server.py`) exposes 8 tools via the Model Context Protocol:

| Tool | Description |
|---|---|
| `search_trials` | Search by keyword, phase, area, status |
| `get_trial_details` | Full record for a given NCT ID |
| `get_statistics` | Aggregate stats grouped by any dimension |
| `compare_groups` | Head-to-head comparison of two groups |
| `predict_trial_success` | ML success probability |
| `generate_chart_data` | Chart-ready JSON for 6 chart types |
| `get_top_sponsors` | Ranked sponsor list |
| `get_model_accuracy` | Benchmark metrics from ML service |

The MCP server can be connected to any MCP-compatible client (Claude Desktop, Cursor, etc.) for interactive analysis.

---

## AWS Deployment

### CDK Stacks

| Stack | Resources |
|---|---|
| `StorageStack` | VPC, S3 (model artefacts), ECR repositories |
| `DatabaseStack` | RDS PostgreSQL 16, DynamoDB (conversations + events) |
| `ComputeStack` | ECS Fargate cluster, ALB per service, IAM roles (Bedrock access) |
| `MonitoringStack` | CloudWatch dashboard, 5xx alarms, SNS alerts |

### Deploy

```bash
cd infra
pip install -r requirements.txt
npm install -g aws-cdk
cdk bootstrap aws://ACCOUNT/us-east-1
cdk deploy --all -c stage=dev
```

---

## CI/CD (GitHub Actions)

### `ci.yml` — runs on every push and PR

1. Python lint + syntax check (all services)
2. Node.js test suite (gateway)
3. Frontend production build
4. Docker build check for all images

### `deploy.yml` — runs on merge to main

1. Build and push all Docker images to ECR
2. CDK deploy infrastructure
3. Run DB schema migration via ECS task

---

## Key Design Decisions

- **Outcome labels are derived, not ground truth** — ClinicalTrials.gov does not publish a simple pass/fail. We use a proxy: Completed + has results = likely success; Terminated/Withdrawn = failure. Confidence scores filter out ambiguous cases. This is documented clearly to users.
- **XGBoost over deep learning** — interpretable, fast to train, works well on tabular data with moderate size, supports SHAP natively.
- **LangGraph ReAct loop** — allows multi-step reasoning (agent can call multiple tools in sequence, backtrack, and synthesise) rather than a single-shot tool call.
- **MCP server alongside LangChain tools** — the MCP server makes the same tools available to any MCP-compatible client (Claude Desktop, Cursor IDE) without code changes.
- **Chart data separate from text** — the agent returns chart JSON in a structured field alongside the text response, so the frontend can render interactive Recharts components rather than static images.

---

## Data Privacy & Disclaimer

All data is sourced from publicly available ClinicalTrials.gov records. No patient-level data is used. Predictions are for **research purposes only** and should not inform clinical or regulatory decisions.
