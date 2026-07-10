> **Status (submission night):** internal architecture review produced by a teammate's
> agent during the hackathon. The product ships as-is; items 1, 4 (partially), 5 (memory
> write moved out of the HTTP layer), and 10 (logging instead of swallowed exceptions)
> were addressed before submission. The rest is the agreed post-hackathon roadmap —
> deliberately not executed hours before the deadline on a working, tested product.

# SheetSleuth Backend Cleanup Handoff

## Purpose

This document is for the next agent that will clean up the SheetSleuth backend. The goal is not to add new product features. The goal is to turn the current hackathon-style backend into a clean, testable backend design while preserving the existing product behavior:

- Upload/demo workbook ingestion.
- Spreadsheet parsing into a dependency graph.
- Neo4j-backed smell detection.
- Finding verification through workbook recomputation.
- Agent Q&A through RocketRide or local fallback.
- Optional Butterbase, Daytona, and Cognee integrations.

Repo root:

```text
/Users/nitishc/Desktop/projs/sheetsleuth
```

Primary backend paths:

```text
backend/app/main.py
backend/app/parser/extract.py
backend/app/graph/db.py
backend/app/graph/loader.py
backend/app/graph/queries.py
backend/app/audit/smells.py
backend/app/audit/fixes.py
backend/app/audit/verify.py
backend/app/audit/agent.py
backend/app/services/*.py
backend/requirements.txt
tests/
```

Do not include secrets in commits or docs. `.env.example` contains placeholder names only; real credentials are in `.env` and must stay uncommitted.

## Suggested Skills

- `codebase-design`: Use this for deciding module interfaces, seams, adapters, and tests.
- `diagnose` or `diagnosing-bugs`: Use only if behavior breaks while refactoring.
- `tdd`: Use for the refactor slices where behavior must be locked down before moving code.
- `review`: Use at the end to review the branch against this handoff.

## Current Backend Shape

The backend currently works as a thin FastAPI app over a graph/audit spine, but the app layer is also doing orchestration and optional integration work.

The intended core flow is:

```text
.xlsx bytes
  -> save workbook file
  -> parser.extract.extract_workbook()
  -> graph.loader.load_workbook()
  -> audit.smells.audit()
  -> optional audit.agent.semantic_audit()
  -> findings stored in Neo4j
```

Verification flow:

```text
finding id
  -> fetch finding from Neo4j
  -> audit.fixes.propose()
  -> audit.verify.verify_finding()
  -> build temp job
  -> run Daytona or local subprocess
  -> create Run node in Neo4j
  -> update Finding.status
  -> optional Cognee memory write
```

Ask flow:

```text
question
  -> services.rocketride.ask_agent()
  -> RocketRide Cloud if configured
  -> local audit.agent.answer() fallback otherwise
  -> optional Butterbase ask_history mirror
```

The clean core is:

```text
parser -> graph repository -> detectors -> findings -> verifier
```

The messy layer is:

```text
HTTP route functions -> direct graph calls
HTTP route functions -> optional LLM calls
HTTP route functions -> optional Butterbase mirror
HTTP route functions -> optional memory thread
verification module -> graph writes
agent module -> graph reads, LLM calls, memory calls, sandbox calls
service adapters -> hidden fallbacks and swallowed failures
```

## High-Level Critique

The backend has a coherent product idea, but the module design is shallow. Most modules expose implementation details instead of owning a useful slice of behavior behind a small interface.

The biggest design issue is not Neo4j. Neo4j is the correct central store for the workbook graph. The issue is that the backend lacks a clear application layer. FastAPI routes, graph persistence, detector orchestration, verification, agent execution, and third-party mirroring are mixed together.

The current design makes several things harder than they should be:

- Understanding what must succeed versus what is best-effort.
- Testing behavior without live Neo4j or network services.
- Knowing whether Daytona, Butterbase, RocketRide, or Cognee were actually used.
- Returning useful errors to clients.
- Refactoring the agent or verifier without breaking unrelated API routes.
- Running concurrent uploads safely.
- Replacing a third-party integration with a fake adapter in tests.

The codebase should be re-centered around deep modules with small interfaces:

- `WorkbookIngestion` should own the full ingestion use case.
- `FindingVerifier` should own verification behavior and return a result, not write graph state as a hidden side effect.
- `AskWorkflow` should own the ask path and make fallback behavior explicit.
- `GraphRepository` should hide Neo4j query/write mechanics from application logic.
- Optional external integrations should be adapters called through explicit ports, not imports inside route functions.

## Specific Problems

### 1. `main.py` Is Doing Too Much

`backend/app/main.py` should be an HTTP adapter. Instead it directly performs:

- `.env` loading.
- CORS setup.
- data directory creation.
- workbook id generation.
- file writes.
- parser invocation.
- graph loading.
- audit invocation.
- optional semantic LLM audit.
- optional Butterbase mirror.
- direct graph reads.
- finding lookup.
- deterministic fix proposal.
- verification execution.
- optional Cognee memory thread.
- RocketRide delegation.
- static frontend mounting.

This makes the route file a shallow orchestration script. Every route knows too much about implementation order and dependencies.

Clean target:

```python
@router.post("/api/workbooks/upload")
async def upload(file: UploadFile, app: AppServices = Depends(get_services)):
    result = app.ingestion.ingest_upload(
        name=file.filename or "workbook",
        raw=await file.read(),
    )
    return result
```

The route should only:

- Parse HTTP inputs.
- Call one use-case interface.
- Convert domain/application errors to HTTP responses.

It should not know about Neo4j, Butterbase, Cognee, Daytona, or LLMs.

### 2. No Explicit Application Layer

There are useful implementation modules, but no module that represents the backend use cases.

Missing use-case modules:

```text
backend/app/workflows/ingestion.py
backend/app/workflows/verification.py
backend/app/workflows/ask.py
backend/app/workflows/queries.py
```

These modules should provide the stable interfaces that route handlers and tests use.

Suggested interfaces:

```python
class WorkbookIngestion:
    def ingest(self, raw: bytes, original_name: str) -> IngestResult: ...
    def ingest_demo(self) -> IngestResult: ...

class WorkbookQueries:
    def graph(self, workbook_id: str) -> WorkbookGraph: ...
    def findings(self, workbook_id: str) -> list[Finding]: ...
    def critical_cells(self, workbook_id: str) -> list[CriticalCell]: ...
    def blast_radius(self, workbook_id: str, sheet: str, address: str) -> BlastRadius: ...

class FindingVerifier:
    def verify(self, finding_id: str) -> VerificationResult: ...

class AskWorkflow:
    def ask(self, workbook_id: str, question: str) -> AskResult: ...
```

The exact class names are negotiable. The important point is the seam: FastAPI should call use-case modules, and use-case modules should coordinate lower-level modules.

### 3. Environment and Configuration Are Scattered

Configuration is read directly from `os.environ` in multiple places:

- `graph/db.py`
- `services/butterbase.py`
- `services/daytona.py`
- `services/rocketride.py`
- `services/cognee_mem.py`
- `main.py`
- tests through `tests/conftest.py`

This creates hidden runtime behavior. Example: setting or not setting `ROCKETRIDE_APIKEY` changes whether `/ask` uses RocketRide or local agent fallback. Setting or not setting `DAYTONA_API_KEY` changes whether verification is truly sandboxed.

Clean target:

```text
backend/app/config.py
```

Provide one settings object:

```python
@dataclass(frozen=True)
class Settings:
    data_dir: Path
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    semantic_audit_enabled: bool
    daytona_enabled: bool
    rocketride_enabled: bool
    butterbase_enabled: bool
    cognee_enabled: bool
    butterbase_app_id: str | None
```

Do not let arbitrary modules read env directly. Build settings once at startup, inject it into factories/adapters, and use explicit booleans for optional features.

Tests should be able to construct `Settings` without touching process env.

### 4. Optional Integrations Are Hidden Side Effects

Several behaviors are best-effort and failure-swallowed:

- Upload mirrors workbook metadata to Butterbase.
- Upload optionally runs semantic LLM audit.
- Verification optionally writes to Cognee memory in a background thread.
- Ask mirrors ask history to Butterbase.
- Ask falls back from RocketRide to local agent.
- Verification falls back from Daytona to local subprocess.

Best-effort is reasonable for a demo, but it must be visible in the design.

Current problem:

```python
try:
    external_call()
except Exception:
    pass
```

This hides operational failures, makes tests ambiguous, and makes the response lie by omission.

Clean target:

- Introduce an `IntegrationEvents` or `Outbox` style module.
- Use explicit result metadata to describe which optional systems ran.
- Log failures with enough context.
- Keep optional side effects out of the critical path unless product behavior requires them.

Example result shape:

```python
@dataclass
class IngestResult:
    workbook_id: str
    name: str
    cells: int
    edges: int
    sheets: int
    findings: int
    semantic_audit: IntegrationStatus
    butterbase_mirror: IntegrationStatus
```

`IntegrationStatus` can be:

```python
@dataclass
class IntegrationStatus:
    attempted: bool
    ok: bool
    provider: str
    error: str | None = None
```

The public API does not have to expose every detail, but the application layer should know it.

### 5. Verification Module Mixes Computation, Execution, and Persistence

`audit/verify.py` currently:

- Builds a temp verification job.
- Embeds a large Python script string.
- Runs a local subprocess.
- Tries Daytona through `services.daytona`.
- Creates `Run` nodes in Neo4j.
- Updates `Finding.status`.

This is too much behind one function. It makes it hard to test verification without graph writes, and hard to reason about whether a failed runner should affect graph state.

Clean target:

Split into three pieces:

```text
verification/job.py        # build job directory or job payload
verification/runner.py     # run job via LocalRunner or DaytonaRunner
verification/workflow.py   # load finding, propose fix, run verifier, persist result
```

Suggested interfaces:

```python
class VerificationRunner(Protocol):
    def run(self, job: VerificationJob) -> RunnerResult: ...

class VerificationRunRepository(Protocol):
    def record(self, finding_id: str, proposal: FixProposal, result: RunnerResult) -> RunRecord: ...

class FindingVerifier:
    def verify(self, finding_id: str) -> VerificationResult: ...
```

The recompute harness itself can stay close to what exists now. The cleanup is about moving graph writes out of the low-level runner.

Important invariant:

- The original workbook file must never be mutated during verification.
- Finding status should only transition through recorded run results.
- `RUN_FAILED` should create a run record if useful, but it should not silently look like a no-op.

### 6. Fallbacks Are Too Silent

Daytona fallback:

```text
try Daytona
except Exception:
    run local subprocess
```

RocketRide fallback:

```text
try RocketRide
except Exception:
    run local agent
```

These fallbacks are useful, but they need explicit policy.

Questions the design should answer:

- In production, is local fallback allowed?
- In tests, should fallback be forced?
- Should the API response say which runner/provider was used?
- Should fallback failures be logged?
- Should some integration failures return 503 instead of fallback?

Clean target:

```python
@dataclass(frozen=True)
class FallbackPolicy:
    allow_local_verification: bool
    allow_local_agent: bool
    expose_fallback_reason: bool
```

For a hackathon demo, fallback may stay enabled. For a clean backend, the policy should be explicit and testable.

### 7. The Agent Layer Has Too Many Dependencies

`audit/agent.py` currently:

- Queries Neo4j directly.
- Calls Butterbase LLM directly.
- Reads workbook files from `DATA_DIR`.
- Calls the sandbox verifier.
- Calls Cognee memory.
- Parses JSON from LLM text.
- Builds prompts.

This module is doing real product work, but it is not isolated behind a clean interface.

Clean target:

```text
agent/context.py       # graph facts and finding summaries
agent/prompts.py       # prompt construction
agent/json_extract.py  # LLM JSON extraction utility
agent/workflow.py      # ask flow and semantic audit flow
agent/ports.py         # LLMClient, MemoryStore, ScenarioRunner
```

Do not over-abstract every helper. The key seam is around external dependencies:

```python
class LLMClient(Protocol):
    def complete(self, messages: list[Message], max_tokens: int) -> str: ...

class MemoryStore(Protocol):
    def recall(self, query: str) -> list[str]: ...
    def remember(self, text: str) -> None: ...

class ScenarioRunner(Protocol):
    def run_changes(self, workbook_id: str, changes: dict[str, Any]) -> ScenarioResult: ...
```

Then `AskWorkflow` can be tested with fake LLM and fake scenario runner.

### 8. Graph Access Is a Global Function

`graph/db.py` exposes a global `run(query, **params)` function using a lazy global driver.

This is convenient but creates weak seams:

- Tests monkeypatch global functions or need live Neo4j.
- There is no typed repository interface.
- Query code leaks into higher layers.
- Driver lifecycle is not owned by app startup/shutdown.

Clean target:

Keep Cypher queries, but wrap access behind repository modules.

Suggested structure:

```text
graph/neo4j.py              # Neo4jClient, session lifecycle
repositories/workbooks.py   # WorkbookGraphRepository
repositories/findings.py    # FindingRepository
repositories/runs.py        # RunRepository
```

Do not create a generic repository abstraction for everything. Create repositories around actual use cases:

```python
class WorkbookGraphRepository:
    def replace_workbook_graph(self, workbook_id: str, name: str, extracted: ExtractedWorkbook) -> GraphStats: ...
    def get_graph(self, workbook_id: str) -> WorkbookGraph: ...
    def critical_cells(self, workbook_id: str, limit: int = 10) -> list[CriticalCell]: ...
    def blast_radius(self, cell_id: str) -> BlastRadius: ...

class FindingRepository:
    def replace_candidates(self, workbook_id: str, findings: list[Finding]) -> None: ...
    def list_for_workbook(self, workbook_id: str) -> list[FindingWithRuns]: ...
    def get(self, finding_id: str) -> FindingWithRuns | None: ...

class RunRepository:
    def record_verification(self, finding_id: str, result: VerificationResult) -> RunRecord: ...
```

This keeps Cypher locality while giving the application layer a clean interface.

### 9. Domain Data Is Mostly Untyped Dicts

The backend passes many untyped dictionaries:

- extracted workbook nodes and edges
- findings
- evidence
- proposals
- verification verdicts
- graph endpoint results
- ask responses

This was fast to build, but it creates fragile contracts. Keys like `"cells"`, `"evidence"`, `"topDeltas"`, `"runner"`, and `"status"` are assumed across modules.

Clean target:

Use lightweight dataclasses or Pydantic models for internal application contracts.

Suggested model files:

```text
backend/app/models/workbook.py
backend/app/models/graph.py
backend/app/models/findings.py
backend/app/models/verification.py
backend/app/models/integrations.py
```

Start small. Do not type every internal Cypher row on day one. Prioritize the use-case outputs and persistence inputs:

- `ExtractedWorkbook`
- `GraphStats`
- `Finding`
- `FixProposal`
- `VerificationResult`
- `RunRecord`
- `AskResult`
- `IntegrationStatus`

### 10. Error Handling Is Not Product-Grade

Current issues:

- Bare `except Exception: pass` in request paths.
- Some missing resources return empty arrays rather than 404.
- External service failure often disappears.
- Verification can fall back without making that explicit in policy.
- Semantic audit errors print to stdout.

Clean target:

Define application errors:

```python
class WorkbookNotFound(AppError): ...
class FindingNotFound(AppError): ...
class NoDeterministicFix(AppError): ...
class VerificationFailed(AppError): ...
class IntegrationUnavailable(AppError): ...
```

FastAPI should map these to HTTP responses in one place:

```text
backend/app/http/errors.py
```

Also add structured logging:

```text
backend/app/logging.py
```

At minimum, replace swallowed exceptions with logger warnings that include provider, workbook id, finding id, and operation.

### 11. Data Storage Is Implicit and Local

Uploaded files are saved to `backend/data`. That directory is created at import time in `main.py`.

Problems:

- Importing the app has filesystem side effects.
- Tests and production share the same default unless carefully configured.
- There is no `WorkbookStore` interface.
- File retention/deletion policy is undefined.

Clean target:

```python
class WorkbookStore:
    def save(self, workbook_id: str, raw: bytes) -> Path: ...
    def path_for(self, workbook_id: str) -> Path: ...
    def exists(self, workbook_id: str) -> bool: ...
```

Adapters:

- `LocalWorkbookStore` for current behavior.
- `TempWorkbookStore` for tests.

This is a local-substitutable dependency. Tests should use a temp store.

### 12. Tests Know Too Much About Current Wiring

The tests are useful, but they reveal the current design problem:

- API tests disable semantic audit via env.
- API tests monkeypatch verification runner.
- Neo4j integration tests skip when env is absent.
- There is no use-case-level fake graph repository test.

Clean target test pyramid:

1. Pure parser and formula tests: keep.
2. Use-case tests with in-memory/fake adapters: add.
3. Neo4j repository integration tests: keep but narrow.
4. API tests: reduce to contract and error mapping.
5. Optional provider adapter tests: mock HTTP/SDK behavior.

For example:

```python
def test_ingest_upload_saves_file_loads_graph_runs_audit_and_reports_optional_failures():
    store = FakeWorkbookStore()
    graph = FakeGraphRepository()
    audit = FakeAuditEngine(findings=[...])
    semantic = FakeSemanticAudit(...)
    mirror = FakeMirror(fails=True)

    result = WorkbookIngestion(...).ingest(raw, "model.xlsx")

    assert result.workbook_id
    assert result.findings == ...
    assert result.butterbase_mirror.ok is False
```

This test should not need FastAPI, Neo4j, Butterbase, or process env.

## Proposed Clean Architecture

Target package shape:

```text
backend/app/
  main.py                    # app factory only
  config.py                  # Settings
  dependencies.py            # construct AppServices
  http/
    routes.py                # FastAPI route handlers
    errors.py                # app error -> HTTP mapping
    schemas.py               # request/response schemas if needed
  workflows/
    ingestion.py             # WorkbookIngestion
    queries.py               # WorkbookQueries
    verification.py          # FindingVerifier
    ask.py                   # AskWorkflow
  models/
    workbook.py
    graph.py
    findings.py
    verification.py
    integrations.py
  parser/
    extract.py               # mostly keep
  graph/
    queries.py               # Cypher detector/read queries, or migrate under repositories
    neo4j.py                 # driver/client lifecycle
  repositories/
    workbooks.py             # graph load/read operations
    findings.py              # findings persistence
    runs.py                  # run persistence
  audit/
    detectors.py             # current smells.detect logic
    fixes.py                 # mostly keep
    semantic.py              # semantic audit workflow or helper
  verification/
    job.py
    runner.py
    script.py
  agent/
    workflow.py
    context.py
    prompts.py
    json_extract.py
  integrations/
    butterbase.py
    daytona.py
    rocketride.py
    cognee.py
    noop.py
  storage/
    workbook_store.py
```

Do not mechanically create every file first. Move in slices. The target shape is a guide, not a mandate.

## Desired Dependency Direction

Keep this direction:

```text
http -> workflows -> domain/application modules -> repositories/ports -> adapters
```

Avoid this:

```text
http -> graph.db.run
http -> services.butterbase
verify -> services.daytona + graph writes
agent -> graph + butterbase + cognee + verifier + filesystem
```

The workflows should own orchestration. Adapters should be dumb. Domain/application modules should return results.

## Refactor Plan

### Phase 0: Lock Current Behavior

Before moving code, run or inspect existing tests:

```bash
.venv/bin/python -m pytest tests/ -q
```

Some tests require Neo4j and may skip if env is missing. Do not force network credentials into tests.

Add a small number of characterization tests if needed:

- Ingest demo with semantic audit disabled returns structural findings.
- Verify short-sum finding records a run and updates status.
- Ask with RocketRide disabled uses local agent path.

Use fakes or monkeypatches only as temporary scaffolding. The later phases should replace monkeypatch-heavy tests with use-case tests.

### Phase 1: Introduce Settings and App Factory

Create:

```text
backend/app/config.py
backend/app/dependencies.py
```

Move env parsing into `Settings.from_env()`.

Change `main.py` toward:

```python
def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    services = build_services(settings)
    app = FastAPI(title="SheetSleuth")
    register_routes(app, services)
    register_error_handlers(app)
    mount_frontend(app, settings)
    return app

app = create_app()
```

Acceptance criteria:

- Importing modules other than `main.py` should not load `.env`.
- Tests can build an app with explicit settings.
- Existing routes still work.

### Phase 2: Extract Workbook Store

Move `DATA_DIR` and `_wb_path()` logic out of `main.py`.

Create:

```text
backend/app/storage/workbook_store.py
```

Acceptance criteria:

- Upload saves through `WorkbookStore`.
- Verification resolves workbook path through `WorkbookStore`.
- Tests can use temp directories.
- No backend module creates `backend/data` at import time.

### Phase 3: Extract Ingestion Workflow

Create:

```text
backend/app/workflows/ingestion.py
```

Move `_ingest()` out of `main.py`.

The workflow should coordinate:

- workbook id generation
- workbook store save
- parser
- graph load
- structural audit
- optional semantic audit
- optional mirror

Acceptance criteria:

- `main.py` upload/demo routes call `WorkbookIngestion`.
- Use-case tests cover success and optional integration failure.
- Butterbase failure is recorded/logged, not silently swallowed.

### Phase 4: Introduce Graph/Finding/Run Repositories

Wrap current Neo4j operations behind repositories.

Start by moving existing functionality, not rewriting all Cypher.

Possible mapping:

- `graph.loader.load_workbook` -> `WorkbookGraphRepository.replace_graph`
- `graph.loader.clear_workbook` -> `WorkbookGraphRepository.clear`
- `smells.write_findings` / `get_findings` -> `FindingRepository`
- run creation in `verify.verify_finding` -> `RunRepository`

Acceptance criteria:

- Workflow modules do not call `graph.db.run`.
- Route handlers do not call `graph.db.run`.
- Cypher remains localized in repository/query modules.

### Phase 5: Split Verification

Separate:

- proposal creation
- job construction
- runner selection
- run persistence
- optional memory event

Recommended flow:

```python
class FindingVerifier:
    def verify(self, finding_id: str) -> VerificationResult:
        finding = findings.get(finding_id)
        proposal = fix_proposer.propose(finding)
        runner_result = runner.run(workbook_path, proposal)
        run = runs.record(finding_id, proposal, runner_result)
        events.publish(VerificationConfirmed(...))  # if confirmed
        return VerificationResult(...)
```

Acceptance criteria:

- Low-level runner does not write to Neo4j.
- Local and Daytona runners implement the same interface.
- Tests can verify behavior with a fake runner.
- API still returns `runId`, `runner`, `verdict`, and deltas.

### Phase 6: Make Optional Integration Policy Explicit

Create explicit ports/adapters for:

- workbook mirror
- ask history mirror
- LLM client
- memory store
- verification runner
- RocketRide client

Provide noop adapters:

```text
NoopWorkbookMirror
NoopAskHistoryMirror
NoopMemoryStore
DisabledSemanticAudit
```

This is better than `if env exists` checks scattered through business logic.

Acceptance criteria:

- Tests can construct workflows entirely with noop/fake adapters.
- Production service construction chooses real or noop adapters based on `Settings`.
- Failures are logged and returned as `IntegrationStatus` where appropriate.

### Phase 7: Clean Agent Workflow

Move local ask/semantic audit behavior out of `audit/agent.py` into cleaner modules.

Recommended split:

- `agent/context.py`: graph facts for prompts.
- `agent/prompts.py`: prompt text.
- `agent/workflow.py`: ask flow and semantic audit flow.
- `agent/json_extract.py`: `_extract_json`.

Acceptance criteria:

- The ask workflow takes an `LLMClient`, `MemoryStore`, `ScenarioRunner`, and graph/finding readers.
- Unit tests can simulate LLM output, scenario execution, and memory recall.
- RocketRide adapter remains separate from local ask workflow.

### Phase 8: Simplify API Tests

After workflows exist, reduce API tests to:

- request/response shape
- HTTP error mapping
- app dependency wiring

Move behavior assertions to workflow tests.

Acceptance criteria:

- Most tests run without Neo4j or network.
- Neo4j tests only validate repository Cypher behavior.
- Provider adapter tests mock HTTP/SDK calls.

## Acceptance Criteria For The Finished Cleanup

The backend design is clean when:

- `main.py` is mostly app creation and route registration.
- FastAPI routes call workflow interfaces only.
- Workflows own orchestration and return typed results.
- Neo4j access is localized behind repository modules.
- Low-level verification runners do not write graph state.
- Optional integrations are explicit adapters with noop/fake implementations.
- Process env is read in one place.
- Best-effort failures are logged and represented, not silently swallowed.
- Tests cover workflows with fakes and repositories with integration tests.
- Existing product behavior still works from the frontend.

## Things To Preserve

Do not throw away the useful core. Preserve these unless tests prove they are broken:

- Parser behavior in `parser/extract.py`.
- Cypher detector ideas in `graph/queries.py`.
- Finding shapes and statuses expected by frontend.
- Deterministic fix proposal logic in `audit/fixes.py`.
- Verification recompute approach using `formulas` and `openpyxl`.
- Demo workbook behavior.
- Existing API route paths, unless the frontend is updated at the same time.

## Known Risk Areas

### Frontend API Contract

The frontend likely expects current response keys. Avoid changing public JSON shapes during the refactor unless coordinated.

### Finding IDs

Finding ids are generated from workbook id and detector order. Refactors may accidentally change ordering. If frontend or tests depend on this, preserve ordering or explicitly document the change.

### Semantic Audit

Semantic audit currently runs during ingestion unless `SHEETSLEUTH_SKIP_SEMANTIC` is set. This can make uploads slow and flaky. A clean design should make semantic audit policy explicit:

- run synchronously
- run asynchronously
- disable
- mark as pending

Do not accidentally make every test call an LLM.

### Cognee Memory

Cognee uses a separate local Neo4j configuration. Keep its graph separate from the workbook graph. Do not load workbook graph nodes into Cognee's graph.

### Daytona Fallback

Local fallback is convenient but can mask production sandbox failures. Make fallback policy explicit.

### Static Frontend Mount

`main.py` currently mounts `frontend/` at `/`. Keep this behavior unless deployment is changed.

## Suggested First Commit Sequence

Keep commits small enough for another agent or human to review.

1. Add `Settings` and `create_app(settings)` without changing behavior.
2. Add `WorkbookStore` and move file path logic.
3. Extract `WorkbookIngestion` and move `_ingest()`.
4. Add workflow tests for ingestion with fakes.
5. Extract `FindingVerifier` while preserving API response.
6. Split verification runner from run persistence.
7. Introduce repository classes around existing graph/finding/run operations.
8. Replace swallowed optional integration failures with logged `IntegrationStatus`.
9. Clean ask workflow and adapters.
10. Trim old tests that now test implementation details.

## Concrete Anti-Goals

Do not do these during the cleanup:

- Do not rewrite all Cypher at once.
- Do not replace Neo4j.
- Do not redesign the frontend.
- Do not change public route paths casually.
- Do not introduce a large dependency injection framework.
- Do not create abstract ports for dependencies that do not vary.
- Do not bury every function behind a class just for symmetry.
- Do not add background queues unless the synchronous version is already clean.

## Summary Diagnosis

The backend is not fundamentally broken. It is a working prototype with a good graph/audit core and too much orchestration in the wrong places.

The fix is to extract a real application layer:

```text
FastAPI routes
  -> workflows
  -> repositories/domain modules
  -> injected external adapters
```

Once that seam exists, the rest of the cleanup becomes straightforward: env parsing centralizes, optional services become explicit, tests move up to the workflow interface, and the graph/verifier logic becomes easier to trust.

