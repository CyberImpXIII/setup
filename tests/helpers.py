"""Shared test plumbing: temp folders, running the CLI, snapshots of a tree."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / "setup"
FAKE_GH = ROOT / "tests" / "fake_gh.py"


def git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def git_repo(path: Path, commit=True):
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q"], path)
    git(["config", "user.email", "t@example.invalid"], path)
    git(["config", "user.name", "t"], path)
    if commit:
        (path / "README").write_text("x\n")
        git(["add", "README"], path)
        git(["commit", "-q", "-m", "init"], path)
    return path


def snapshot(path: Path):
    """{relative path: (sha256, mode)} for every file, .git included: a dry run
    or a refusal must leave even the index alone."""
    out = {}
    if not path.exists():
        return None
    for p in sorted(path.rglob("*")):
        if p.is_file():
            out[str(p.relative_to(path))] = (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode)
        elif p.is_dir():
            out[str(p.relative_to(path)) + "/"] = ("dir", 0)
    return out


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="setup-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = dict(os.environ)
        self.env["SETUP_GH"] = str(FAKE_GH)
        self.env["FAKE_GH_ROOT"] = str(self.tmp / "_github")
        # A commit needs an identity; never borrow the user's for test commits.
        self.env.update({"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                         "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})

    def run_setup(self, *args, cwd=None):
        r = subprocess.run([str(SETUP), *args], cwd=cwd or self.tmp, env=self.env,
                           capture_output=True, text=True)
        return r

    def run_json(self, *args, cwd=None):
        r = self.run_setup(*args, "--json", cwd=cwd)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        doc = json.loads(r.stdout)
        return r.returncode, {x["component"]: x for x in doc["results"]}

    def statuses(self, results):
        return {k: v["status"] for k, v in results.items()}
