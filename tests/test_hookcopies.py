"""devtools/hookcopies.py, the `copies` gate (PLAN-check-progress.md §13): this repo's
hook copies agree with their source by meaning, judged from the hooks dependency's
`copies --repo --json` document and never from its exit code alone. Canned documents
for each way it fails, a fake CLI for what it runs, a lone clone for UNCHECKED, and
the live CLI on this repo."""
import json
import os
import shutil
import subprocess
import sys

from tests.helpers import ROOT, Case, workspace_cli

sys.path.insert(0, str(ROOT / "devtools"))
import hookcopies  # noqa: E402

_, HOOKS_CLI = workspace_cli("hooks")
HELPER = ROOT / "devtools" / "hookcopies.py"


def doc(files, path=ROOT.name, root=str(ROOT.parent), ok=True, unresolved=()):
    """A `copies --repo --json` document, of this repo unless told otherwise."""
    return json.dumps({"root": root, "ok": ok, "unresolved": list(unresolved),
                       "locations": [{"path": path, "files": files}]})


GOOD = [{"file": ".claude/hooks/a.sh", "status": "ok"}, {"file": ".claude/hooks/test-a.sh", "status": "ok"}]
REPO = ROOT


class Judge(Case):
    def judge(self, out, code=0, err=""):
        return hookcopies.judge(code, out, err, REPO)

    def test_every_row_ok_passes_and_counts(self):
        self.assertEqual(self.judge(doc(GOOD)), ([], 2))

    def test_a_drifted_copy_is_named(self):
        fails, _ = self.judge(doc([GOOD[0], {"file": ".claude/hooks/b.sh", "status": "drift"}], ok=False), code=1)
        self.assertEqual(fails, [".claude/hooks/b.sh: drift"])

    def test_an_unknown_status_is_never_a_pass(self):
        fails, _ = self.judge(doc([{"file": "x", "status": "maybe"}]))
        self.assertEqual(fails, ["x: maybe"])

    def test_exit_0_does_not_excuse_a_failing_row(self):
        fails, _ = self.judge(doc([{"file": "x", "status": "missing"}], ok=True), code=0)
        self.assertEqual(fails, ["x: missing"])

    def test_a_non_zero_exit_over_ok_rows_fails(self):
        fails, _ = self.judge(doc(GOOD), code=1, err="boom\n")
        self.assertEqual(fails, ["exit 1 though every row is ok: boom"])

    def test_ok_false_over_ok_rows_fails(self):
        fails, _ = self.judge(doc(GOOD, ok=False))
        self.assertEqual(len(fails), 1)
        self.assertIn("ok=False", fails[0])

    def test_comparing_nothing_is_no_pass(self):
        fails, n = self.judge(doc([]))
        self.assertEqual(n, 0)
        self.assertIn("compared no file", fails[0])

    def test_another_location_fails(self):
        fails, _ = self.judge(doc(GOOD, path="tools/other"))
        self.assertIn("not of this repo alone", fails[0])

    def test_unresolved_fails(self):
        fails, _ = self.judge(doc(GOOD, unresolved=[{"file": ".claude/hooks/z.sh", "roles": []}]))
        self.assertEqual(fails, ["unresolved: .claude/hooks/z.sh"])

    def test_no_document_fails_with_stderr(self):
        fails, _ = self.judge("usage: ...", code=2, err="refused: --repo x\n")
        self.assertEqual(fails, ["`copies --repo --json` printed no JSON document (exit 2): refused: --repo x"])


class Run(Case):
    """main() with --cli: what it runs, and what its exit says."""

    def fake(self, out, code=0):
        f = self.tmp / "fake-hooks"
        argv = self.tmp / "argv"
        (self.tmp / "out.json").write_text(out)
        f.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{argv}'\ncat '{self.tmp / 'out.json'}'\nexit {code}\n")
        f.chmod(0o755)
        r = subprocess.run([sys.executable, str(HELPER), "--cli", str(f)], capture_output=True, text=True)
        return r.returncode, r.stdout, argv.read_text().split("\n")[:-1]

    def test_it_asks_for_this_repo_alone_as_json(self):
        code, out, argv = self.fake(doc(GOOD))
        self.assertEqual(argv, ["copies", "--repo", str(ROOT), "--json"])
        self.assertEqual(code, 0, out)
        self.assertIn("ok    copies: 2 hook file(s) here agree", out)

    def test_a_drifted_copy_is_red(self):
        rows = [GOOD[0], {"file": ".claude/hooks/b.sh", "status": "drift"}]
        code, out, _ = self.fake(doc(rows, ok=False), code=1)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  copies: .claude/hooks/b.sh: drift", out)
        self.assertNotIn("ok    copies", out)

    def test_an_unknown_argument_is_refused(self):
        r = subprocess.run([sys.executable, str(HELPER), "--gate", "x"], capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (2, ""))


class LoneClone(Case):
    def test_no_hooks_dependency_is_unchecked_never_a_pass(self):
        d = self.tmp / "setup"
        (d / "devtools").mkdir(parents=True)
        shutil.copy2(HELPER, d / "devtools" / "hookcopies.py")
        shutil.copytree(ROOT / "setuplib", d / "setuplib", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "dependencies.json", d / "dependencies.json")
        r = subprocess.run([sys.executable, "devtools/hookcopies.py"], cwd=d, capture_output=True, text=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("UNCHECKED  copies: no hooks dependency to compare against", r.stdout)


class Live(Case):
    def test_this_repos_copies_agree(self):
        if HOOKS_CLI is None:
            self.skipTest("lone clone: LoneClone covers it")
        r = subprocess.run(["./dev.sh", "copies"], cwd=ROOT, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"ok    copies: [1-9][0-9]* hook file\(s\) here agree")
