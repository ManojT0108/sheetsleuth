# 🕵️ SheetSleuth

**Your spreadsheet is lying to you — and our agent can prove it.**

SheetSleuth audits Excel workbooks by turning every formula into a live
**Neo4j dependency graph**, detecting the errors hiding in the wiring, then
**proving** each one by re-executing the entire workbook in an isolated
**Daytona** sandbox and measuring the damage in dollars. A **RocketRide Cloud**
agent answers questions about the graph and runs what-if scenarios for real.
**Butterbase** provides auth, Postgres, payments, the AI gateway behind every
LLM call, and hosting. **Cognee** gives the agent long-term memory across
audits.

> Built for **HackwithBay 3.0** (July 2026) · Track 10 — Open Innovation
>
> **Live demo:** https://sheetsleuth.butterbase.dev
> **Demo login:** `demo@sheetsleuth.dev` / `SleuthDemo1!`
> Click **"▶ Audit the demo model"**, double-click the red `Revenue!G3` node,
> then try **"🧪 Prove it"** on a finding and a suggestion chip in *Ask the agent*.

## The problem

Business runs on spreadsheets, and spreadsheets are silently wrong. Field
research (Panko et al.) finds errors in ~90% of large production spreadsheets.
JPMorgan's $6B "London Whale" loss involved an Excel copy-paste error; the UK
lost 16,000 COVID cases to a row limit. The root cause: a workbook is a
**dependency graph nobody can see** — and no existing tool *proves* whether a
suspected error actually changes your numbers. SheetSleuth makes the wiring
visible, finds the errors, and settles every accusation by execution.

## How it works

1. Upload an `.xlsx` workbook or run the included demo model.
2. Parse formulas, values, sheets, and cell references.
3. Load the workbook into Neo4j as a graph of cells and dependencies.
4. Run graph detectors for risky spreadsheet patterns, plus an LLM semantic
   audit for label/reference mismatches.
5. Inspect findings, critical cells, and downstream blast radius in the UI.
6. Prove findings by re-executing the workbook (as-is vs. fixed) in a Daytona
   sandbox and recording the measured dollar impact.
7. Ask the RocketRide Cloud agent anything — structural answers come from live
   Cypher traversals; what-ifs are executed, never guessed.

## The Neo4j graph model

```
(:Workbook)-[:HAS_SHEET]->(:Sheet)-[:CONTAINS]->(:Cell)
(:Cell)-[:FEEDS_INTO]->(:Cell)          # precedent → dependent, the wiring
(:Finding)-[:AFFECTS]->(:Cell)          # detector output
(:Run)-[:VERIFIES]->(:Finding)          # sandbox-executed verdict + $ impact
```

Everything judge-visible is a genuine traversal, not lookup:

- **Blast radius** — `MATCH (c:Cell {id:$id})-[:FEEDS_INTO*1..64]->(d)` — one
  query, any depth, across sheets (the demo traces one hardcoded growth rate
  into 52 downstream cells including the board summary).
- **Detectors** — hardcoded constants in formula chains, pasted-over formulas
  (static value amid formula siblings), SUM ranges that stop short of data,
  orphaned assumptions, circular references (`-[:FEEDS_INTO*1..8]->(c)`), and
  load-bearing-cell ranking by downstream reach.

## Hackathon stack — every technology is load-bearing

| Technology | Requirement | How it's used |
|---|---|---|
| **Neo4j Aura** | mandatory | The workbook as a traversable property graph; all detectors and blast-radius analysis are Cypher; the cloud agent runs text-to-Cypher against it live |
| **RocketRide Cloud** | mandatory | `pipelines/sheetsleuth_agent.pipe` deployed on api.rocketride.ai as a managed endpoint the app calls for agent Q&A (`agent_rocketride` + `db_neo4j` tool + HTTP what-if tool + memory); local fallback exists only for offline development |
| **Butterbase** | mandatory | End-user auth (signup/login), Postgres (workbook + ask-history mirrors), **payments** ($9 "Full Audit Report" product with the Stripe Connect checkout flow; demo-mode unlock while seller onboarding is skipped), **AI gateway** for every LLM call (semantic audit, agent, pipeline LLM node, Cognee), and hosting of the frontend |
| **Daytona** | bonus track | Every verification and what-if scenario executes in a fresh isolated sandbox — create, install deps, recompute the whole workbook twice, diff every cell, destroy — ~7s per verdict |
| **Cognee** | bonus track | Long-term agent memory (remember/recall) with its own Neo4j graph store; recalled audit history enriches answers across sessions |

## Architecture

```
React (Vite) frontend ── FastAPI backend ──┬── Neo4j Aura (product graph)
  hosted on Butterbase                     ├── RocketRide Cloud (agent pipeline)
                                           │     ├── llm_openai_api → Butterbase AI gateway
                                           │     ├── db_neo4j tool → Aura
                                           │     └── http tool → backend what-ifs
                                           ├── Daytona (verification sandboxes)
                                           ├── Butterbase (auth · Postgres · billing · gateway)
                                           └── Cognee (memory, dedicated Neo4j + APOC)
```

## Features

- Excel `.xlsx` upload and demo workbook ingestion (multi-sheet, cross-sheet
  references, quoted sheet names).
- Neo4j-backed dependency graph for sheets, cells, formulas, and references.
- Interactive frontend graph explorer with cell inspection.
- Finding list for suspicious spreadsheet patterns.
- Critical-cell ranking for load-bearing assumptions and formulas.
- Blast-radius analysis for downstream impact.
- Sandbox-executed verification with measured per-cell dollar impact.
- LLM semantic audit through the Butterbase AI gateway.
- Agent Q&A through the deployed RocketRide Cloud pipeline (local fallback for
  offline development).
- Butterbase auth, payments checkout, and Postgres mirroring.
- Cognee long-term memory of audits and verdicts.

## Repository Structure

```text
backend/   FastAPI API, workflows, graph loading, detectors, integrations
frontend/  Vite/React UI
demo/      Demo workbook and demo-generation helpers
pipelines/ RocketRide pipeline definition + SDK test harness
tests/     Unit, workflow, and optional Neo4j integration tests
docs/      Architecture review (post-hackathon roadmap)
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
- `backend/app/integrations/`: external-service adapters.

## Prerequisites

- Python 3.12
- Node.js 18+
- Neo4j database, local or Aura

The core upload and graph workflow requires Neo4j. The remaining integrations
power semantic audit, the hosted agent, checkout, and mirrors — the hosted demo
runs with all of them enabled.

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

Integration credentials (all active in the hosted demo):

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
- `SHEETSLEUTH_SKIP_SEMANTIC=1` disables LLM semantic audit during ingestion
  (useful for fast deterministic tests).
- The hosted demo runs with `SHEETSLEUTH_BUTTERBASE_ENABLED=1` (workbook and
  ask-history mirrors on). Set `0` locally if you haven't provisioned the
  Butterbase tables.

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

## Demo script (3 minutes)

1. Open https://sheetsleuth.butterbase.dev → **Audit the demo model**.
2. The graph renders the workbook's hidden wiring (4 sheets, 247 edges) — amber
   nodes are suspects. Double-click `Revenue!G3` → blast radius lights up 52
   cells across three sheets.
3. Evidence → **"🧪 Prove it"** on the short-SUM finding → ~7s Daytona run →
   `CONFIRMED — $35,000 hidden; ending cash is actually −$117,065, not −$82,065`.
4. Ask (use a suggestion chip): *"What happens to runway if payroll rises
   10%?"* → the cloud agent executes the scenario in a sandbox and answers with
   measured before/after numbers.
5. Sign in → **Unlock full audit report — $9** → Butterbase billing purchase
   flow (demo-mode unlock; Stripe seller onboarding deliberately skipped).

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

`workbook mirror failed` is a best-effort integration warning. It does not block
the core workbook audit. The hosted demo runs with mirrors enabled; disable
locally with:

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
Support for multiple linked workbooks, Excel defined names, and array formulas
can be added later — see `docs/ARCHITECTURE_REVIEW.md` for the engineering
roadmap.

## Team

- **Manoj Thipare Gowda** ([@ManojT0108](https://github.com/ManojT0108))
- **Nitish ChandraShekar** ([@n1tishc](https://github.com/n1tishc))

Built in one day for HackwithBay 3.0 with Claude Code.
