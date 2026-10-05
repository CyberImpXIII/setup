#!/usr/bin/env python3
"""This repo's `./dev.sh check --json`: one document in the one schema every
repo's check prints (ok, checks[] of name/status/counts/failures, each failure
with message, file, line and role; the shared checks tool holds the schema).

  devtools/checkjson.py <gate>:<role>:<exit code>:<output file> ...

One check per gate, in the order given. Exit 0 -> `ok`, no failures (whatever
the output says). Anything else -> `fail`, with one failure per finding line in
the gate's captured output:

  FAIL / BASELINE-RED / STALE / SURVIVED / UNCHECKED lines   (dev.sh, setup audit, mutate.py)
  unittest's `FAIL: name (tests.module.Class.name)` / `ERROR: ...`

`file`/`line` are set only where the line itself says them: an audit finding's
`<path>:<line>: <label>` under this repo, or a unittest module whose file exists.
Otherwise both are null (prefer null to a guess). A red gate with no finding
line still gets one failure naming the gate to re-run, so a `fail` always says
what. Prints the document and exits 0 iff every gate passed (exit agrees with ok).

tests/test_checkjson.py holds this against tests/fixtures/ and, in the
workspace, against the real validator."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FINDING = re.compile(r"^\s*(FAIL|BASELINE-RED|STALE|SURVIVED|UNCHECKED)\b[\s:]+(.*\S)")
UNITTEST = re.compile(r"^(FAIL|ERROR): (\S+) \(([\w.]+)\)")
AUDIT_AT = re.compile(r"^(/\S+?):(\d+): (.+)$")


def _module_file(dotted):
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        rel = "/".join(parts[:i]) + ".py"
        if (ROOT / rel).is_file():
            return rel
    return None


def _repo_rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return None


def findings(gate, text):
    """[(message, file, line)] for every finding line in a red gate's output."""
    out = []
    for raw in text.splitlines():
        line = raw.rstrip()
        m = UNITTEST.match(line)
        if m:
            out.append((line, _module_file(m.group(3)), None))
            continue
        m = FINDING.match(line)
        if not m:
            continue
        msg = f"{m.group(1)} {m.group(2)}" if m.group(1) != "FAIL" else m.group(2)
        at = AUDIT_AT.match(m.group(2)) if gate == "audit" else None
        rel = _repo_rel(at.group(1)) if at else None
        if rel:  # the message says the same place the fields do, repo-relative
            out.append((f"{rel}:{at.group(2)}: {at.group(3)}", rel, int(at.group(2))))
        else:
            out.append((msg, None, None))
    return out


def check(gate, role, code, text):
    found = [] if code == 0 else findings(gate, text)
    if code != 0 and not found:
        found = [(f"./dev.sh {gate} failed (exit {code}) with no finding line; run it for the output", None, None)]
    failures = [{"message": m, "file": f, "line": ln, "role": role} for m, f, ln in found]
    return {"name": gate, "status": "ok" if code == 0 else "fail",
            "counts": {"failed": len(failures)}, "failures": failures}


def parse(args):
    rows = []
    for a in args:
        gate, role, code, path = a.split(":", 3)
        if not gate or not role:
            raise ValueError(a)
        rows.append((gate, role, int(code), path))
    return rows


def _read(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError as e:
        return f"FAIL the gate's output could not be read: {e}"


def main(argv):
    try:
        rows = parse(argv)
    except ValueError:
        print(f"usage: devtools/checkjson.py <gate>:<role>:<exit code>:<output file> ... (got {argv})", file=sys.stderr)
        return 64
    if not rows:
        print("checkjson: no gates: a report of nothing is not a pass", file=sys.stderr)
        return 64
    checks = [check(g, r, c, _read(p)) for g, r, c, p in rows]
    doc = {"ok": all(c["status"] == "ok" for c in checks), "checks": checks}
    print(json.dumps(doc))
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
