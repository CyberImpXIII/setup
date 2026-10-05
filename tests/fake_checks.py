#!/usr/bin/env python3
"""A stand-in for the shared checks CLI, for the gates component's own cases (a
missing gate, an error, output that is not JSON), which the real one cannot be
made to produce on demand. The live tests in tests/test_contract.py hold setup to
the real CLI; this one only answers the two calls setup makes.

$FAKE_CHECKS is a JSON file: {"gates": [names `list` reports], "results": [rows
`run` reports], "one": [rows `one <name>` picks its own from], "faults": [...],
"raw": text printed instead of JSON (optional)}.
Every call is appended to $FAKE_CHECKS_LOG as one JSON line: its argv, and for
`run`, the files at the target then (so a test can tell setup rendered first).
"""
import json
import os
import sys
from pathlib import Path

spec = json.loads(Path(os.environ["FAKE_CHECKS"]).read_text())
args = sys.argv[1:]
entry = {"argv": args}
if args[:1] == ["run"] and len(args) > 1:
    entry["files"] = sorted(p.name for p in Path(args[1]).iterdir())
with open(os.environ["FAKE_CHECKS_LOG"], "a") as log:
    log.write(json.dumps(entry) + "\n")

if "raw" in spec:
    print(spec["raw"])
    sys.exit(1)
if args == ["list", "--json"]:
    print(json.dumps({"checks": [{"name": n, "applies_to": "all"} for n in spec["gates"]],
                      "refused": [], "faults": []}))
    sys.exit(0)
if args[:1] == ["run"] and args[2:] == ["--json"]:
    bad = any(r["status"] in ("fail", "error") for r in spec["results"]) or spec.get("faults")
    print(json.dumps({"repo": args[1], "results": spec["results"], "faults": spec.get("faults", []),
                      "ok": not bad}))
    sys.exit(1 if bad else 0)
if args[:1] == ["one"] and args[3:] == ["--json"]:
    rows = [r for r in spec.get("one", []) if r["check"] == args[1]]
    print(json.dumps({"repo": args[2], "results": rows, "faults": [],
                      "ok": not any(r["status"] in ("fail", "error") for r in rows)}))
    sys.exit(0)
print(f"fake checks: unexpected call {args}", file=sys.stderr)
sys.exit(2)
