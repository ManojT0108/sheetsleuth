"""Self-contained workbook recompute script used by verification jobs."""

VERIFY_SCRIPT = r'''
import json, re
from pathlib import Path
import formulas, openpyxl

job = json.loads(Path("job.json").read_text())
src = job["workbook"]

def compute(path):
    sol = formulas.ExcelModel().loads(path).finish().calculate()
    fname = Path(path).name.upper()
    out = {}
    for k, v in sol.items():
        m = re.match(r"^'\[(.+?)\](.+?)'!([A-Z]{1,3}[0-9]+)$", k)
        if not m or m.group(1).upper() != fname:
            continue
        try:
            val = v.value[0, 0]
        except Exception:
            continue
        if hasattr(val, "item"):
            val = val.item()
        out[f"{m.group(2)}!{m.group(3)}"] = val
    return out

wb = openpyxl.load_workbook(src)
labels = {}
for ws in wb.worksheets:
    for row in ws.iter_rows():
        label = None
        for cell in row:
            if isinstance(cell.value, str) and not cell.value.startswith("="):
                label = label or cell.value
            elif cell.value is not None and label:
                labels[f"{ws.title.upper()}!{cell.coordinate}"] = label

baseline = compute(src)

sheets = {s.upper(): s for s in wb.sheetnames}
for ref, formula in job["fixes"].items():
    sheet, addr = ref.split("!")
    if isinstance(formula, str) and not formula.startswith("="):
        try:
            formula = float(formula) if "." in formula else int(formula)
        except ValueError:
            pass
    wb[sheets[sheet.upper()]][addr] = formula
fixed_path = "fixed.xlsx"
wb.save(fixed_path)
fixed = compute(fixed_path)

deltas = []
for key, before in baseline.items():
    after = fixed.get(key)
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        if abs(after - before) > 0.005:
            deltas.append({"cell": key, "label": labels.get(key),
                           "before": before, "after": after,
                           "delta": after - before})
    elif after != before:
        deltas.append({"cell": key, "label": labels.get(key),
                       "before": str(before), "after": str(after),
                       "delta": None})

deltas.sort(key=lambda d: -abs(d["delta"] or 0))
verdict = {
    "verdict": "CONFIRMED" if deltas else "NO_IMPACT",
    "cellsChanged": len(deltas),
    "maxAbsDelta": max((abs(d["delta"]) for d in deltas if d["delta"]), default=0),
    "topDeltas": deltas[:12],
}
Path("verdict.json").write_text(json.dumps(verdict, indent=2))
print(json.dumps(verdict))
'''
