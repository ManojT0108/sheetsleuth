# SheetSleuth

SheetSleuth audits Excel workbooks by parsing formulas into a Neo4j dependency graph, running graph-based detectors, and verifying proposed fixes by recomputing the workbook.

## Components

- `backend/`: FastAPI API, workbook ingestion, graph loading, findings, verification, and ask-agent workflows.
- `frontend/`: Vite/React UI. In dev it calls `http://localhost:8788`; when served by the backend on port `8788`, it uses the same origin.
- `demo/`: demo workbook generator and sample workbook.
- `tests/`: pure unit/workflow tests plus Neo4j-backed integration tests when a database is configured.

## Environment

Create a local env file from the example:

```bash
cp .env.example .env
```

Required for the full product loop:

- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`: workbook graph database.

Optional integrations:

- `DAYTONA_API_KEY`: sandboxed verification runner. If absent, verification falls back to local subprocess execution.
- `BUTTERBASE_API_KEY`, `BUTTERBASE_APP_ID`: workbook/ask mirrors and LLM gateway.
- `ROCKETRIDE_APIKEY`: cloud ask-agent path. If absent, ask falls back to the local agent path.
- `COGNEE_NEO4J_*`: separate Cognee memory graph settings.

Useful local flags:

```bash
SHEETSLEUTH_SKIP_SEMANTIC=1          # disable LLM semantic audit during ingest
SHEETSLEUTH_DATA_DIR=backend/data    # override uploaded workbook storage
SHEETSLEUTH_ALLOW_LOCAL_AGENT=1      # allow local ask fallback
SHEETSLEUTH_ALLOW_LOCAL_VERIFICATION=1
```

## Backend

Install Python dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

Run the API on the port expected by the frontend:

```bash
.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8788
```

Check health:

```bash
curl http://127.0.0.1:8788/api/health
```

`neo4j:false` means the API is running but the configured Neo4j database is not reachable.

## Frontend

Install frontend dependencies:

```bash
cd frontend
npm ci
```

Run the Vite dev server:

```bash
npm run dev
```

Open the Vite URL it prints. The dev frontend calls the backend at `http://localhost:8788`.

Build the frontend:

```bash
npm run build
```

After `frontend/dist` exists, the backend serves the built UI from:

```text
http://127.0.0.1:8788/
```

## Tests

Run the backend tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

Tests that need Neo4j skip automatically when no reachable `NEO4J_URI` is configured. Most unit and workflow tests do not need Neo4j or network services.

## Main API Routes

- `POST /api/workbooks/upload`: upload an `.xlsx`.
- `POST /api/demo`: ingest the demo workbook.
- `GET /api/workbooks/{workbook}/graph`: graph nodes and edges.
- `GET /api/workbooks/{workbook}/findings`: findings and verification runs.
- `GET /api/workbooks/{workbook}/critical`: most load-bearing cells.
- `GET /api/workbooks/{workbook}/blast/{sheet}/{address}`: downstream blast radius.
- `POST /api/findings/{finding_id}/verify`: verify a deterministic fix.
- `POST /api/workbooks/{workbook}/ask`: ask the agent.
- `GET /api/health`: API and Neo4j health.

## Backend Shape

The backend is organized around use-case workflows:

```text
http routes -> workflows -> repositories/domain modules -> adapters
```

Key modules:

- `backend/app/config.py`: env parsing and runtime settings.
- `backend/app/main.py`: FastAPI app factory only.
- `backend/app/http/`: route handlers and error mapping.
- `backend/app/workflows/`: ingestion, query, verification, and ask use cases.
- `backend/app/repositories/`: Neo4j-backed workbook, finding, and run persistence.
- `backend/app/storage/`: workbook file storage.
- `backend/app/verification/`: verification job packaging and runners.
- `backend/app/integrations/`: optional Butterbase, RocketRide, Cognee, semantic-audit adapters.
