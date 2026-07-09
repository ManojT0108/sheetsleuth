# SheetSleuth — Teammate Handoff

> **For the agent picking this up:** this document is your single source of truth.
> Read it fully before touching code. Your mission: **review the codebase, write
> test cases, and test it** — while the other teammate's session works on frontend
> redesign, README, Stripe checkout, and submission. Stay in your lane (see
> "Division of labor") to avoid merge conflicts.

## What this is

**SheetSleuth** — HackwithBay 3.0 entry (Track 10, Open Innovation).
*"Your spreadsheet is lying to you — and our agent can prove it."*

Upload an .xlsx → every formula becomes a node in a **Neo4j** dependency graph
(`FEEDS_INTO` edges) → graph queries detect structural errors → the agent
proposes fixes → a **Daytona** sandbox recomputes the entire workbook with and
without each fix → `CONFIRMED` verdicts with **measured dollar impact** are
written back to the graph. A **RocketRide Cloud** pipeline hosts the Q&A agent
(text-to-Cypher against Aura + sandbox what-ifs). **Butterbase** provides auth,
Postgres, payments ($9 report unlock), the AI gateway for every LLM call, and
hosts the frontend. **Cognee** gives the agent long-term memory.

Demo prop: `demo/lumeo_fy2026_model.xlsx` — a realistic SaaS financial model
with **5 planted errors** (`demo/ground_truth.json` is the oracle):

| ID | Type | Where | Detector |
|----|------|-------|----------|
| E1 | hardcoded-constant-in-chain | Revenue!G3 (0.15 growth) | Cypher: literals + blast radius |
| E2 | stale-pasted-constant | Revenue!K5 (Oct MRR pasted) | Cypher: number amid formula siblings |
| E3 | short-sum-range | Costs!B8:M8 (misses row 7) | Cypher: SUM range vs populated gap |
| E4 | label-reference-mismatch | Summary!B10 (Dec ARR → Nov col) | LLM semantic triage via Butterbase |
| E5 | orphaned-assumption | Assumptions!B12 | Cypher: labeled input, no out-edges |

All 5 detected with zero false positives; E1/E2/E3 verify as CONFIRMED via
sandbox recompute (E1: $28.5k ARR overstatement, E3: $35k hidden costs).

## Architecture & file map

```
backend/app/
  parser/extract.py      xlsx -> {nodes, edges} via openpyxl formula Tokenizer
  graph/db.py            Neo4j driver (env: NEO4J_URI/USER/PASSWORD/DATABASE)
  graph/loader.py        load extracted graph into Neo4j (namespaced ids
                         "<workbook>::<Sheet>!<ADDR>"); clear_workbook()
  graph/queries.py       THE showcase: 5 smell detectors + blast_radius +
                         critical_cells + cell_context (all pure Cypher)
  audit/smells.py        orchestrates detectors -> Finding nodes (+evidence JSON)
  audit/fixes.py         deterministic fix proposals: sibling drag-fill
                         translation (translate_formula) + SUM range extension
  audit/verify.py        VERIFY_SCRIPT (self-contained recompute-and-diff via
                         `formulas` pkg) + build_job/run_local/run_sandboxed +
                         Run nodes written to Neo4j
  audit/agent.py         LLM layers: semantic_audit (E4) + answer() two-wave
                         what-if agent (emits SCENARIO -> sandbox -> answer)
  services/butterbase.py REST mirror (workbooks/ask_history tables) + llm()
                         via gateway (model: anthropic/claude-sonnet-4.6)
  services/daytona.py    fresh sandbox per verification job (SDK: daytona)
  services/rocketride.py app -> CLOUD pipeline (attach-or-deploy by
                         project_id, chat via SDK); local-agent fallback
  services/cognee_mem.py remember/recall; LLM via gateway, embeddings local
                         (fastembed), graph in LOCAL Docker neo4j (APOC)
  main.py                FastAPI: upload/demo/graph/findings/verify/ask/
                         blast/critical/health + serves frontend/
frontend/index.html      single-file app (vis-network graph, evidence+paywall,
                         ask tab, Butterbase auth+checkout)
pipelines/sheetsleuth_agent.pipe   RocketRide pipeline (agent_rocketride +
                         llm_openai_api->Butterbase + db_neo4j->Aura +
                         tool_http_request->backend + memory_internal)
pipelines/test_pipeline.py         deploy/exercise pipeline via SDK
demo/make_demo_workbook.py         regenerates the demo xlsx + ground truth
demo/check_extraction.py           extraction de-risk gate (run it!)
demo/test_graph_layer.py           detector smoke test (needs Neo4j)
demo/test_verification.py          full closed-loop smoke test
```

**Two Neo4j instances by design:**
- **Aura** (cloud) = product graph (cells, findings, runs). Backend + cloud pipeline use it.
- **Local Docker `sheetsleuth-neo4j`** (with APOC) = Cognee's private brain.
  Do NOT load workbook graphs into it — Cognee's migration scanner breaks on
  foreign nodes (learned the hard way).

## Running it

```bash
cd sheetsleuth
python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt  # or see below
# .env: copy .env.example, get real values from teammate (AirDropped separately)
docker start sheetsleuth-neo4j   # or: docker run -d --name sheetsleuth-neo4j \
  # -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/sheetsleuth123 \
  # -e NEO4J_PLUGINS='["apoc"]' neo4j:5
set -a && source .env && set +a
.venv/bin/uvicorn app.main:app --app-dir backend --port 8788   # serves API + frontend
curl -X POST localhost:8788/api/demo                           # ingest demo workbook
open http://localhost:8788                                     # UI
```

If `backend/requirements.txt` is missing, install:
`openpyxl networkx neo4j fastapi "uvicorn[standard]" python-multipart requests
python-dotenv formulas daytona rocketride cognee fastembed`

Deployed state (live right now):
- Frontend: https://sheetsleuth.butterbase.dev (Butterbase app `app_x89ezf73vxrn`)
- Backend tunnel: https://agency-upgrade-thru-karen.trycloudflare.com
  (cloudflared quick tunnel on the primary machine — dies with that machine;
  frontend falls back to it only when served from butterbase.dev)
- RocketRide Cloud: pipeline project `835dcdf8-...` running on api.rocketride.ai

## YOUR MISSION: tests

**UPDATE:** a starter suite now exists — `tests/` (35 passing: units, extractor
oracle, verify harness, Neo4j detector integration, API flow). Run it first:
`.venv/bin/python -m pytest tests/ -q`. **Extend it — don't rewrite it.**
Highest-value gaps remaining for you:

- Edge-case workbooks (see item 4 below) — the suite only covers the demo
  model + one synthetic circular workbook.
- Adversarial formulas: array formulas, defined names, external links,
  whole-row refs, merged cells — find where the extractor breaks and decide
  crash vs. skip-gracefully.
- The agent layer (`audit/agent.py`): semantic_audit false-positive rate on
  clean workbooks; scenario-extraction robustness.
- Concurrency: two uploads of the same file simultaneously.
- Frontend smoke (optional): the API contract is covered; UI is being
  redesigned by the other session, don't test its DOM yet.

Original priority list (items 1–3 are now largely covered by the suite):

1. **Pure-unit (no services needed) — do these first:**
   - `fixes.translate_formula`: drag-fill shifts relative refs only
     (`=ROUND(F3*(1+Assumptions!$B$3-B4),0)` col+1 → F3→G3, B4→C4, $B$3 fixed);
     function names with digits (LOG10) must not be mangled; row_delta variant.
   - `fixes.propose` SUM-extension regex: `=SUM(B3:B6)` row 8 → `=SUM(B3:B7)`;
     `$`-anchored ranges; non-SUM formulas return unchanged/None.
   - `parser/extract.py`: run against `demo/lumeo_fy2026_model.xlsx` —
     assert node/edge counts, all 5 ground-truth signals (port the asserts from
     `demo/check_extraction.py` into pytest), range expansion, cross-sheet refs,
     numeric literal capture, `empty-ref` node creation.
   - `agent._extract_json`: nested braces, anchors, garbage input.
   - `verify.VERIFY_SCRIPT` via `build_job` + `run_local`: apply the E3 fix to
     the demo workbook → expect verdict CONFIRMED, cellsChanged==8,
     Summary!B4 delta == +35000. (Runs the `formulas` recompute locally,
     no Daytona needed — ~10s.)
2. **Integration (needs Aura or any Neo4j via env):** loader + 5 detectors →
   exactly the ground-truth findings, no false positives. Use a throwaway
   workbook id (e.g. `pytest-<uuid>`), always `clear_workbook()` in teardown.
3. **API (FastAPI TestClient):** /api/demo → 5 findings; /api/workbooks/{wb}/graph
   shape; /verify on the short-sum finding → CONFIRMED; 404/422 paths.
   NOTE: ingest triggers `semantic_audit` (LLM call, ~10s, costs pennies) —
   consider monkeypatching `app.audit.agent.semantic_audit` to return [] for
   speed, EXCEPT one test that exercises it for real.
4. **Edge-case workbooks (great findings for the demo):** empty workbook,
   formula-only, circular reference (A1=B1, B1=A1 — detector exists, untested!),
   whole-column refs `SUM(A:A)` (extractor skips them — verify no crash),
   unicode sheet names, defined names (KNOWN GAP: not resolved — document,
   don't fix unless trivial).

**Invariants to enforce:** detectors on the demo workbook find EXACTLY the
ground truth (5 findings, no more); `verify` never mutates the original xlsx
(job runs on a copy); `Finding.status` transitions candidate→CONFIRMED only via
a Run node; all graph writes are namespaced by workbook id.

**Bugs you find:** small/safe → fix directly with a test proving it; risky →
document in `KNOWN_ISSUES.md` and tell the humans.

## Division of labor (avoid merge conflicts!)

- **You (teammate agent):** `tests/`, `KNOWN_ISSUES.md`, bugfixes in
  `backend/app/parser|graph|audit` with tests.
- **Other session (primary machine):** `frontend/`, `README.md`, Stripe/payments,
  `pipelines/`, deployment, submission. Do not edit these.
- Work on a branch (`tests`), commit early and often.

## Gotchas that will bite you

- `formulas` pkg: computed keys look like `'[file.xlsx]SHEET'!B3` (sheet UPPERCASED);
  files written by openpyxl have no cached values, so `data_only=True` gives None —
  always recompute via `formulas`.
- October = column **K**, not J (B=Jan). Yes, this bit us.
- Cypher: `min()/max()` are row aggregates — `max([x IN list | x.row])` compares
  LISTS, silently returning garbage. Aggregate in the `WITH` instead.
- Neo4j 5 scoped subquery syntax `CALL (c) {...}` is used in queries.py — needs
  Neo4j 5.23+ (Aura and the Docker image are fine).
- Cognee state lives in `.venv/.../cognee/.cognee_system` + `.data_storage`;
  if migrations wedge, delete both AND wipe its (local) graph db.
- RocketRide: pipeline per project_id is a singleton — `use()` throws
  "already running"; attach via `client.get_task_token(project_id, "chat_1")`.
- The Butterbase gateway occasionally times out (~120s) — `llm()` has 3 retries.
- `.env` is gitignored and holds ALL credentials (Aura, Daytona, Butterbase,
  RocketRide). Get it from your teammate, never commit it.

## Current judging-requirements status

| Requirement | Status |
|---|---|
| Neo4j active traversal | DONE (5 Cypher detectors + blast radius + cloud text2cypher) |
| RocketRide Cloud deployed + app calls it | DONE (attach-or-deploy, `source: rocketride-cloud`) |
| Butterbase DB + auth | DONE (tables mirrored, signup/login tested) |
| Butterbase payments "in active use" | ⚠️ BLOCKED on Stripe Connect onboarding (product + checkout code ready) |
| Daytona bonus | DONE (sandbox verdicts ~6.6s) |
| Cognee bonus | DONE (remember/recall wired into agent) |
| Frontend polish, README, submission | other session's queue |
