#!/usr/bin/env python3
"""A stand-in for a tool's store CLI (PLAN-repo-setup.md §7.11), copied into a test
repo as `./tool`: the store is data/store.db (JSON, so a test can read it), its
exported form $DATA_REPO/<repo folder name>/items.json. The data component runs
`import` and then `verify --json`; the shared checks' stores-exported runs `verify`.

$FAKE_STORE_MODE breaks one thing: `lie` (import exits 0, writes nothing), `fail`
(import exits 1), `differs` (verify reports an item differing), `empty` (verify
reports no item), `unavailable` (verify could not compare), `exit` (verify all same,
exit 1). $FAKE_STORE_LOG, when set, gets one JSON line per call: argv, DATA_REPO.
"""
import json
import os
import sys
from pathlib import Path

USAGE = """./tool <command>

  import     build the store from its export in $DATA_REPO (only when it is absent)
  export     write the store's export into $DATA_REPO
  verify     compare the store with its export (--json: one report)
"""

args = sys.argv[1:]
mode = os.environ.get("FAKE_STORE_MODE", "")
if os.environ.get("FAKE_STORE_LOG"):
    with open(os.environ["FAKE_STORE_LOG"], "a") as log:
        log.write(json.dumps({"argv": args, "DATA_REPO": os.environ.get("DATA_REPO")}) + "\n")
store = Path("data/store.db")
export = Path(os.environ.get("DATA_REPO", "/nonexistent")) / Path.cwd().name / "items.json"

if not args or args[0] in ("help", "-h", "--help"):
    print(USAGE)
    sys.exit(0)
if args[0] == "import":
    if mode == "fail":
        print("import: cannot read the export", file=sys.stderr)
        sys.exit(1)
    if store.exists():
        print("import: the store exists; never dropped", file=sys.stderr)
        sys.exit(1)
    if mode != "lie":
        store.parent.mkdir(exist_ok=True)
        store.write_text(export.read_text())
    sys.exit(0)
if args[0] == "export":
    export.parent.mkdir(parents=True, exist_ok=True)
    export.write_text(store.read_text())
    sys.exit(0)
if args[0] == "verify":
    mine = json.loads(store.read_text()) if store.exists() else {}
    theirs = json.loads(export.read_text()) if export.exists() else {}
    items = []
    for k in sorted(set(mine) | set(theirs)):
        st = "same" if mine.get(k) == theirs.get(k) else ("missing" if k not in mine or k not in theirs else "differs")
        items.append({"item": k, "status": st})
    if mode == "differs" and items:
        items[0] = {"item": items[0]["item"], "status": "differs", "detail": "value changed"}
    if mode == "unavailable" and items:
        items[0] = {"item": items[0]["item"], "status": "unavailable", "detail": "no network"}
    if mode == "empty":
        items = []
    print(json.dumps({"items": items}))
    sys.exit(1 if mode == "exit" or any(i["status"] in ("differs", "missing") for i in items) else 0)
print(USAGE, file=sys.stderr)
sys.exit(2)
