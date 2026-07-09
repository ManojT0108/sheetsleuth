"""The verification engine's recompute-and-diff harness, run locally
(no Daytona, no Neo4j): prove the E3 fix changes the right numbers."""

from app.audit.verify import build_job, run_local

E3_FIXES = {f"Costs!{c}8": f"=SUM({c}3:{c}7)" for c in "BCDEFGHIJKLM"}


def test_e3_fix_confirmed_with_exact_impact(demo_xlsx):
    verdict = run_local(build_job(demo_xlsx, E3_FIXES))
    assert verdict["verdict"] == "CONFIRMED"
    assert verdict["cellsChanged"] == 8
    deltas = {d["cell"]: d for d in verdict["topDeltas"]}
    assert deltas["SUMMARY!B4"]["delta"] == 35000        # costs up
    assert deltas["SUMMARY!B5"]["delta"] == -35000       # net income down
    assert deltas["SUMMARY!B6"]["delta"] == -35000       # ending cash down
    assert deltas["SUMMARY!B4"]["label"].startswith("Total FY2026 costs")


def test_noop_fix_has_no_impact(demo_xlsx):
    # writing the identical formula back must not change anything
    verdict = run_local(build_job(demo_xlsx, {"Costs!B8": "=SUM(B3:B6)"}))
    assert verdict["verdict"] == "NO_IMPACT"
    assert verdict["cellsChanged"] == 0


def test_numeric_string_values_coerced(demo_xlsx):
    # what-if scenarios may send numbers as strings; they must compute
    verdict = run_local(build_job(demo_xlsx, {"Assumptions!B8": "203500"}))
    assert verdict["verdict"] == "CONFIRMED"
    deltas = {d["cell"]: d for d in verdict["topDeltas"]}
    assert deltas["SUMMARY!B4"]["delta"] == 222000       # +18.5k x 12 months


def test_original_workbook_never_mutated(demo_xlsx):
    before = demo_xlsx.read_bytes()
    run_local(build_job(demo_xlsx, E3_FIXES))
    assert demo_xlsx.read_bytes() == before
