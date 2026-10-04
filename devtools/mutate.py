#!/usr/bin/env python3
"""Prove each gate can fail: break it once in a throwaway copy, see red.

  devtools/mutate.py [mutants.json] [--only ID]

Each mutant names a file, an exact string to replace (it must occur exactly
once, or the mutant is STALE and fails the run: the code moved and the proof
with it), the replacement, and the command that must go red. Every command is
first run on an unmutated copy and must be green, so the red is the mutant's
doing (the counterfactual), not a broken baseline.

Copies are separate folders run as separate processes, in parallel; every
mutant's outcome is reported, never just the first failure. Each copy is a fresh
`git init` (setup works on a repo) under .mutants/ inside this repo, gitignored
and removed afterwards: the shared hooks' own tests find their sibling repos by
walking up, so a copy in the system temp folder would fail for its location,
not for the mutant. Nothing else in the working tree is touched.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(".git", ".mutants", "__pycache__", "*.pyc")
WORK = ROOT / ".mutants"


def copy_tree(dest: Path) -> Path:
    shutil.copytree(ROOT, dest, ignore=IGNORE, symlinks=True)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    return dest


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-3:]


def baseline(cmd, tmp: Path, i: int):
    d = copy_tree(tmp / f"base{i}")
    code, tail = run(cmd, d)
    return cmd, code, tail


def mutant(m, tmp: Path):
    d = copy_tree(tmp / m["id"])
    f = d / m["file"]
    text = f.read_text()
    n = text.count(m["old"])
    if n != 1:
        return m["id"], "STALE", f"{m['file']}: the string to replace occurs {n} times, not once"
    f.write_text(text.replace(m["old"], m["new"]))
    code, tail = run(m["run"], d)
    if code == 0:
        return m["id"], "SURVIVED", f"{' '.join(m['run'])} stayed green with the gate broken"
    return m["id"], "red", f"{' '.join(m['run'])} -> exit {code}"


def main(argv):
    path = Path(argv[0]) if argv and not argv[0].startswith("--") else ROOT / "devtools" / "mutants.json"
    mutants = json.loads(path.read_text())["mutants"]
    if "--only" in argv:
        want = argv[argv.index("--only") + 1]
        mutants = [m for m in mutants if m["id"] == want]
    if not mutants:
        print("mutants: none loaded; nothing proven")
        return 1
    ids = [m["id"] for m in mutants]
    if len(ids) != len(set(ids)):
        print("mutants: duplicate ids")
        return 1
    WORK.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="run-", dir=WORK))
    try:
        cmds = list({tuple(m["run"]): None for m in mutants})
        with ThreadPoolExecutor(max_workers=6) as pool:
            bases = list(pool.map(lambda a: baseline(list(a[1]), tmp, a[0]), enumerate(cmds)))
            bad_base = [(c, code, tail) for c, code, tail in bases if code != 0]
            for c, code, tail in bad_base:
                print(f"  BASELINE-RED  {' '.join(c)} exits {code} unmutated: {' | '.join(tail)}")
            results = list(pool.map(lambda m: mutant(m, tmp), mutants))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            WORK.rmdir()  # only when no other run is using it
        except OSError:
            pass
    for mid, verdict, detail in results:
        if verdict != "red":
            print(f"  {verdict:<9} {mid}: {detail}")
    red = sum(v == "red" for _, v, _ in results)
    failed = len(results) - red + len(bad_base)
    print(f"mutants: {red} of {len(results)} red" + (f", {failed} problem(s)" if failed else ", every gate shown able to fail"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
