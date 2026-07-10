# SheetSleuth

SheetSleuth audits Excel workbooks by turning formulas into a dependency graph,
detecting suspicious spreadsheet patterns, and verifying selected findings by
recomputing the workbook.

The app is built around a simple workflow:

1. Upload an `.xlsx` workbook or run the included demo model.
2. Parse formulas, values, sheets, and cell references.
3. Load the workbook into Neo4j as a graph of cells and dependencies.
4. Run detectors for risky spreadsheet patterns.
5. Inspect findings, critical cells, and downstream blast radius in the UI.
6. Verify deterministic fixes by re-executing the workbook and recording impact.

## Features

- Excel `.xlsx` upload and demo workbook ingestion.
- Neo4j-backed dependency graph for sheets, cells, formulas, and references.
- Interactive frontend graph explorer with cell inspection.
- Finding list for suspicious spreadsheet patterns.
- Critical-cell ranking for load-bearing assumptions and formulas.
- Blast-radius analysis for downstream impact.
- Deterministic verification flow for supported findings.
- Optional semantic audit through the Butterbase LLM gateway.
- Optional ask-agent flow through RocketRide, with local fallback.
- Optional Butterbase auth and checkout proxy routes.

## Repository Structure

```text
backend/   FastAPI API, workflows, graph loading, detectors, integrations
frontend/  Vite/React UI
demo/      Demo workbook and demo-generation helpers
tests/     Unit, workflow, and optional Neo4j integration tests
```

Key backend modules:

- `backend/app/main.py`: FastAPI app factory.
- `backend/app/config.py`: environment parsing and runtime settings.
- `backend/app/http/`: API routes and error handling.
- `backend/app/workflows/`: ingestion, query, verification, and ask workflows.
- `backend/app/graph/`: Neo4j schema, loading, and graph queries.
- `backend/app/parser/`: `.xlsx` extraction.
- `backend/app/audit/`: detectors, fix proposals, and semantic audit helpers.
- `backend/app/verification/`: verification job packaging and runners.
- `backend/app/integrations/`: optional external-service adapters.

## Prerequisites

- Python 3.12
- Node.js 18+
- Neo4j database, local or Aura

The core upload and graph workflow requires Neo4j. Optional integrations are
only needed for semantic audit, hosted agent calls, checkout, or external
mirrors.

## Environment Setup

Create a local environment file:

```bash
cp .env.example .env
```

Required variables:

```bash
NEO4J_URI=neo4j+s://<aura-instance>.databases.neo4j.io
NEO4J_USER=<neo4j-user>
NEO4J_PASSWORD=<neo4j-password>
NEO4J_DATABASE=<neo4j-database>
```

Useful local flags:

```bash
SHEETSLEUTH_SKIP_SEMANTIC=1
SHEETSLEUTH_DATA_DIR=backend/data
SHEETSLEUTH_ALLOW_LOCAL_AGENT=1
SHEETSLEUTH_ALLOW_LOCAL_VERIFICATION=1
SHEETSLEUTH_BUTTERBASE_ENABLED=0
```

Optional integrations:

```bash
DAYTONA_API_KEY=<daytona-api-key>
BUTTERBASE_API_KEY=<butterbase-api-key>
BUTTERBASE_APP_ID=<butterbase-app-id>
ROCKETRIDE_APIKEY=<rocketride-api-key>
COGNEE_NEO4J_URI=<cognee-neo4j-uri>
COGNEE_NEO4J_USER=<cognee-neo4j-user>
COGNEE_NEO4J_PASSWORD=<cognee-neo4j-password>
```

Notes:

- The backend reads `.env` at startup. Restart uvicorn after changing env vars.
- `SHEETSLEUTH_SKIP_SEMANTIC=1` disables LLM semantic audit during ingestion.
- `SHEETSLEUTH_BUTTERBASE_ENABLED=0` keeps optional workbook and ask-history
  mirrors disabled. Enable it only if the Butterbase tables match the app
  payloads.

## Install

Install backend dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm ci
cd ..
```

## Run Locally

Start the backend:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8788
```

Start the frontend in a second terminal:

```bash
cd frontend
npm run dev
```

Open the Vite URL printed by the dev server. The frontend expects the backend at
`http://localhost:8788`.

## Serve The Built Frontend

Build the frontend:

```bash
cd frontend
npm run build
cd ..
```

Start the backend:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8788
```

When `frontend/dist` exists, FastAPI serves the built UI at:

```text
http://127.0.0.1:8788/
```

## Health Check

```bash
curl http://127.0.0.1:8788/api/health
```

Expected response:

```json
{"ok": true, "neo4j": true}
```

If `neo4j` is `false`, the API is running but the configured Neo4j database is
not reachable.

## API Routes

- `POST /api/workbooks/upload`: upload an `.xlsx` workbook.
- `POST /api/demo`: ingest the bundled demo workbook.
- `GET /api/workbooks/{workbook_id}/graph`: return graph nodes and edges.
- `GET /api/workbooks/{workbook_id}/findings`: return findings and verification
  runs.
- `GET /api/workbooks/{workbook_id}/critical`: return load-bearing cells.
- `GET /api/workbooks/{workbook_id}/blast/{sheet}/{address}`: return downstream
  blast radius.
- `POST /api/findings/{finding_id}/verify`: verify a deterministic finding.
- `POST /api/workbooks/{workbook_id}/ask`: ask the workbook agent.
- `POST /api/auth/{signup|login}`: proxy Butterbase auth requests.
- `POST /api/billing/purchase`: proxy Butterbase checkout requests.
- `GET /api/health`: report API and Neo4j health.

## Tests

Run backend tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

Tests that require Neo4j skip automatically when no reachable `NEO4J_URI` is
configured. Unit and workflow tests do not require network services.

Build the frontend:

```bash
cd frontend
npm run build
```

## Troubleshooting

### Environment Changes Are Not Detected

Restart the backend after editing `.env`. The FastAPI process reads environment
variables during app startup.

### Neo4j Health Is False

Check that `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, and `NEO4J_DATABASE` are
set correctly in `.env`. Then restart the backend and call `/api/health`.

### Neo4j Aura Certificate Error On macOS

If Aura connections fail with certificate verification errors on macOS, run:

```bash
/Applications/Python\ 3.12/Install\ Certificates.command
```

Then restart the backend.

### Neo4j Transaction Memory Error

If upload logs mention `MemoryPoolOutOfMemoryError`, Neo4j ran out of
transaction memory while replacing workbook graph data. The loader clears and
loads workbook data in batches; restart the backend to ensure the current code is
running.

If the database is still exhausted, clear old workbook data or use a fresh Neo4j
database.

### Butterbase Mirror Warning

`workbook mirror failed` is an optional integration warning. It does not block
the core workbook audit.

Keep this disabled unless the Butterbase `workbooks` and `ask_history` tables
match the app payloads:

```bash
SHEETSLEUTH_BUTTERBASE_ENABLED=0
```

### Frontend Cannot Reach The Backend

The dev frontend calls:

```text
http://localhost:8788
```

Start the backend on port `8788`, then refresh the frontend.

## Current Scope

SheetSleuth currently treats each uploaded `.xlsx` file as one audit target.
Support for multiple linked workbooks can be added later if cross-workbook
references become part of the product workflow.
