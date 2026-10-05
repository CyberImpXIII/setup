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


def workspace_cli(tool):
    """(workspace top, CLI) for the sibling tool `tools/<tool>/<tool>` in the workspace
    around this one, or (None, None) in a lone clone. Run as a subprocess, never imported."""
    for top in ROOT.parents:
        cli = top / "tools" / tool / tool
        if os.access(cli, os.X_OK):
            return top, cli
    return None, None


def hook_listing(source=None):
    """[(installed rel, source file)] the hooks dependency's own `list --json` names
    for `source` (default: its own): what a repo setup renders must end up holding,
    taken from the dependency rather than from setup. None in a lone clone."""
    _, cli = workspace_cli("hooks")
    if cli is None:
        return None
    source = source or cli.parent / "source"
    r = subprocess.run([str(cli), "list", "--json", "--source", str(source)], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"{cli} list --json failed: {r.stderr.strip()[-300:]}")
    out = []
    for row in json.loads(r.stdout):
        out.append((f"{row['dest']}/{row['name']}", source / row["path"]))
        if row["test_installed"]:
            out.append((f"{row['dest']}/{Path(row['test']).name}", source / row["test"]))
    return out


_, _HOOKS_CLI = workspace_cli("hooks")
HOOK_SOURCE = _HOOKS_CLI.parent / "source" if _HOOKS_CLI else None  # the default hook source; None: lone clone


def hook_source(path: Path, hooks, settings=None, body="exit 0\n"):
    """A --hooks-from fixture the hooks dependency's `list` accepts: each hook declared
    (`# hooks: applies_to=all`) with its test beside it, and settings.json (`settings`,
    else every hook registered on Stop). Returns path."""
    (path / "hooks").mkdir(parents=True, exist_ok=True)
    for n in hooks:
        for name in (n, f"test-{n}"):
            f = path / "hooks" / name
            f.write_text(f"#!/bin/sh\n# hooks: applies_to=all\n{body}")
            f.chmod(0o755)
    if settings is None:
        settings = {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{n}"} for n in hooks]}]}}
    (path / "settings.json").write_text(settings if isinstance(settings, str) else json.dumps(settings))
    return path


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
        self.env.pop("DATA_REPO", None)  # the data component reads it: a test sets its own or none
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
