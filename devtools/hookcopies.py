#!/usr/bin/env python3
"""This repo's hook copies agree with their source by meaning: the short check's
stand-in for re-running every shared hook's own test (PLAN-check-progress.md §13:
those tests run once, in the hooks source's own check).

  devtools/hookcopies.py [--cli PATH]

Runs the hooks dependency's `copies --repo <this repo> --json` (dependencies.json
names the dependency; setuplib/deps.py resolves it by walking up, as the hooks
component does) and judges the document, never the exit code alone:

  ok        exit 0, `ok` true, exactly one location and it is this repo, at least
            one file compared, every file `ok`, nothing unresolved
  FAIL      anything else, each file that is not `ok` named with its status; a
            document that does not parse, a run that compared nothing, and an
            exit code that disagrees with the rows are failures too (exit 1)
  UNCHECKED the hooks dependency does not resolve (a lone clone): exit 3, never a
            pass

--cli PATH runs that CLI instead of the resolved one (the tests' fake).
Exit 2: an argument it does not know.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from setuplib import deps  # noqa: E402  (this repo's resolver, imported from ROOT)

DEP = "hooks"
TIMEOUT_S = 300  # a meaning comparison of one repo takes seconds; this bounds a hung CLI
USAGE = "usage: devtools/hookcopies.py [--cli PATH]"


def find_cli():
    """(cli, None, None) or (None, kind, why), kind 'fail' or 'unchecked'."""
    d, why = deps.load(ROOT)
    if why:
        return None, "fail", why
    where, why = deps.resolve(DEP, ROOT, d)
    if where is None:
        return None, "unchecked", f"no hooks dependency to compare against: {why}"
    cli = deps.cli(DEP, where, d)
    if cli is None:
        return None, "fail", f"{where / d[DEP]['cli']} (dependencies.json `{DEP}`) is not an executable file"
    return cli, None, None


def judge(code, out, err, repo: Path):
    """(failures, count): the lines that make the comparison red, and how many files
    it compared for this repo. Reads the document first and holds the exit code to it."""
    tail = (err.strip().splitlines() or ["(nothing on stderr)"])[-1]
    try:
        doc = json.loads(out)
    except ValueError:
        return [f"`copies --repo --json` printed no JSON document (exit {code}): {tail}"], 0
    if not isinstance(doc, dict) or not isinstance(doc.get("locations"), list):
        return [f"`copies --repo --json` printed no report with `locations` (exit {code}): {tail}"], 0
    root = Path(str(doc.get("root") or "/"))
    mine = [loc for loc in doc["locations"]
            if isinstance(loc, dict) and (root / str(loc.get("path"))).resolve() == repo.resolve()]
    fails = []
    if len(mine) != 1 or len(doc["locations"]) != 1:
        names = [loc.get("path") for loc in doc["locations"] if isinstance(loc, dict)]
        fails.append(f"the report is not of this repo alone: locations {names} under {root}, this repo {repo}")
    files = [f for loc in mine for f in (loc.get("files") or []) if isinstance(f, dict)]
    if not files:
        fails.append("compared no file: a comparison of nothing is no pass")
    for f in files:
        if f.get("status") != "ok":
            fails.append(f"{f.get('file')}: {f.get('status')}")
    for u in doc.get("unresolved") or []:
        fails.append(f"unresolved: {u.get('file') if isinstance(u, dict) else u}")
    if doc.get("ok") is not True and not fails:
        fails.append(f"the report says ok={doc.get('ok')!r} though every row is ok")
    if code != 0 and not fails:
        fails.append(f"exit {code} though every row is ok: {tail}")
    return fails, len(files)


def main(argv):
    cli = None
    if argv[:1] == ["--cli"] and len(argv) == 2:
        cli = Path(argv[1])
    elif argv:
        print(USAGE, file=sys.stderr)
        return 2
    if cli is None:
        cli, kind, why = find_cli()
        if cli is None:
            if kind == "unchecked":
                print(f"  UNCHECKED  copies: {why}")
                return 3
            print(f"  FAIL  copies: {why}")
            return 1
    try:
        r = subprocess.run([str(cli), "copies", "--repo", str(ROOT), "--json"],
                           capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        print(f"  FAIL  copies: {cli} copies --repo did not finish in {TIMEOUT_S}s")
        return 1
    except OSError as e:
        print(f"  FAIL  copies: cannot run {cli}: {e.strerror}")
        return 1
    fails, n = judge(r.returncode, r.stdout, r.stderr, ROOT)
    if fails:
        for f in fails:
            print(f"  FAIL  copies: {f}")
        return 1
    print(f"  ok    copies: {n} hook file(s) here agree with their source by meaning ({cli.name} copies --repo)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
