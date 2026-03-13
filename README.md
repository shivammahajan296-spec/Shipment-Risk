# Shipment Delay Risk Assessment and Prediction Platform

Consulting-grade enterprise web app for logistics risk intelligence, predictive shipment delay scoring, external disruption monitoring, and multi-agent operational recommendations.

## What is included

- FastAPI backend with modular service architecture
- Synthetic logistics dataset generator for 50,000 shipment records across 6 months
- Predictive ML pipeline with baseline and champion models
- Shipment-level delay probability scoring and risk bands
- Mock external signal adapter layer for weather, traffic, closures, strikes, and disruption scenarios
- Straive Gemini 2.5 Pro-compatible LLM abstraction with retries, timeouts, fallback, and structured logging
- Multi-agent orchestration layer:
  - Data Understanding Agent
  - Signal Discovery Agent
  - ML Risk Scoring Agent
  - External Risk Agent
  - Operational Recommendation Agent
  - Executive Summary Agent
- Premium HTML/CSS/JS control-tower frontend with:
  - mock authentication
  - role-aware navigation
  - executive overview
  - data readiness
  - signal discovery
  - predictive prototype
  - shipment risk scoring
  - external disruption center
  - agent collaboration timeline
  - value to operations
  - scenario simulator

## Architecture

```text
Frontend (HTML/CSS/JS control tower)
  -> FastAPI API layer
    -> Platform service
      -> Synthetic data generator
      -> ML risk service
      -> External signal provider
      -> Straive Gemini 2.5 Pro service abstraction
      -> Agent orchestrator
```

## Project structure

```text
app/
  config.py
  main.py
  models.py
  services/
    agent_service.py
    data_generator.py
    external_signals.py
    llm_service.py
    ml_service.py
    platform_service.py
static/
  index.html
  styles.css
  app.js
.env.example
requirements.txt
README.md
```

## Run locally

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy the environment template:

```bash
cp .env.example .env
```

3. Start the app:

```bash
uvicorn app.main:app --reload
```

4. Open [http://localhost:8000](http://localhost:8000)

## Straive LLM configuration

The LLM integration is intentionally abstracted behind [`app/services/llm_service.py`](/Users/shivammahajan/Documents/RISK MODEL/app/services/llm_service.py). It is configured only for Straive Gemini 2.5 Pro-compatible routing.

Environment variables:

- `STRAIVE_GEMINI_BASE_URL`
- `STRAIVE_GEMINI_API_KEY`
- `STRAIVE_GEMINI_MODEL`
- `STRAIVE_GEMINI_TIMEOUT_SECONDS`
- `STRAIVE_GEMINI_MAX_RETRIES`
- `USE_MOCK_LLM`

If credentials are missing or the endpoint fails, the app falls back to grounded mock summaries so the demo remains usable.

## Key API endpoints

- `GET /api/overview`
- `GET /api/agents`
- `GET /api/shipments`
- `POST /api/simulate`
- `POST /api/demo/reset`
- `POST /api/upload`
- `GET /api/export/shipments`

## Demo data

On first startup the app generates a synthetic dataset and stores it in `data/synthetic_shipments.csv`. It includes:

- shipment history
- warehouse operations
- carrier performance
- external risk features

The scoring output is written to `data/scored_shipments.csv`.

## Notes

- External APIs are mocked behind an adapter-style provider so weather, traffic, strike, and closure feeds can be replaced later without changing the UI contract.
- The current ML pipeline uses `LogisticRegression` as a baseline and `RandomForestClassifier` as the champion model to keep the demo lightweight and stable.
- The frontend uses Plotly via CDN for premium interactive visualizations.
- The login and role views are mock enterprise UX, not production authentication.
