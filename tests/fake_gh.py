#!/usr/bin/env python3
"""A stand-in for `gh`, so no test ever creates a real GitHub repo.

State lives under $FAKE_GH_ROOT: <owner>/<name>.git is a bare repo playing the
remote, <owner>/<name>.vis its visibility, calls.log every invocation.
$FAKE_GH_LIE=1 makes `repo create` report success without creating or pushing,
which is what the remote component's verification exists to catch;
$FAKE_GH_VIS=<v> makes it create the repo with visibility v whatever was asked.
"""
import os
import subprocess
import sys
from pathlib import Path

root = Path(os.environ["FAKE_GH_ROOT"])
root.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
with open(root / "calls.log", "a") as log:
    log.write(" ".join(args) + "\n")

if args[:2] == ["api", "user"]:
    print("fakeowner")
    sys.exit(0)

if args[:2] == ["repo", "view"]:
    slug = args[2]
    bare = root / f"{slug}.git"
    if not bare.exists():
        print(f"Could not resolve to a Repository with the name '{slug}'", file=sys.stderr)
        sys.exit(1)
    if "--json" in args:
        print((root / f"{slug}.vis").read_text().strip().upper())
    sys.exit(0)

if args[:2] == ["repo", "create"]:
    slug = args[2]
    vis = "private" if "--private" in args else "public"
    vis = os.environ.get("FAKE_GH_VIS", vis)  # a gh that ignored the flag
    src = args[args.index("--source") + 1]
    if os.environ.get("FAKE_GH_LIE") == "1":
        sys.exit(0)
    bare = root / f"{slug}.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    (root / f"{slug}.vis").write_text(vis)
    subprocess.run(["git", "-C", src, "remote", "add", "origin", str(bare)], check=True)
    subprocess.run(["git", "-C", src, "push", "-q", "origin", "HEAD"], check=True)
    sys.exit(0)

print(f"fake gh: unhandled {args}", file=sys.stderr)
sys.exit(2)
