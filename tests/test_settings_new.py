"""PLAN-repo-setup §7.9: a repo setup creates gets `.claude/settings.json`, written
from the same render that makes `settings.proposed.json` and committed with the
scaffold. Nothing of Jacob's exists there yet. Every other repo, including one setup
created, on any later run, keeps the proposal path: its settings.json is never touched.

The gate that the written file is the shared wiring reuses the proposal generator
rather than restating the rule: the file a new folder gets equals, byte for byte, the
proposal an existing repo with no settings.json gets from the same inputs."""
import json
import subprocess
import unittest

from setuplib.fsw import Writer
from tests.helpers import ROOT, Case, git, git_repo, snapshot, workspace_cli
from tests import test_userscope as us  # a module, so its TestCase is not collected twice

BLOBS = us.BLOBS

SETTINGS = ".claude/settings.json"
PROPOSAL = ".claude/settings.proposed.json"


class CreatedRepo(Case):
    def test_created_repo_commits_settings_json_holding_the_shared_wiring(self):
        code, res = self.run_json("fresh")
        self.assertEqual(code, 0)
        self.assertEqual(res["hooks"]["status"], "installed")
        self.assertIn(f"wrote {SETTINGS}", res["hooks"]["detail"])
        repo = self.tmp / "fresh"
        # in the one commit setup made, not merely on disk
        self.assertEqual(git(["rev-list", "--count", "HEAD"], repo).stdout.strip(), "1")
        self.assertIn(SETTINGS, git(["show", "--name-only", "--format=", "HEAD"], repo).stdout.split())
        self.assertEqual(json.loads((repo / SETTINGS).read_text()),
                         json.loads((ROOT / SETTINGS).read_text()))
        # no proposal: it would hold the same thing, and settings.json already does
        self.assertFalse((repo / PROPOSAL).exists())
        self.assertEqual(git(["status", "--porcelain", "--untracked-files=all"], repo).stdout, "")

    def test_an_empty_folder_made_a_repo_gets_it_too(self):
        (self.tmp / "empty").mkdir()
        self.run_json("empty")
        self.assertIn(SETTINGS, git(["ls-files"], self.tmp / "empty").stdout.split())

    def test_dry_run_says_it_would_write_it_and_writes_nothing(self):
        _, res = self.run_json("fresh", "--dry-run")
        self.assertEqual(res["hooks"]["status"], "installed")
        self.assertIn(f"would write {SETTINGS}", res["hooks"]["detail"])
        self.assertFalse((self.tmp / "fresh").exists())


class SameRender(Case):
    """The written file is the proposal, for every input that shapes the proposal."""

    def both(self, *args):
        git_repo(self.tmp / "old")  # an existing repo with no settings.json: proposal only
        _, old = self.run_json("old", *args)
        _, new = self.run_json("fresh", *args)
        self.assertEqual(old["hooks"]["status"], "needs-jacob")
        self.assertFalse((self.tmp / "old" / SETTINGS).exists())
        return (self.tmp / "old" / PROPOSAL).read_bytes(), (self.tmp / "fresh" / SETTINGS).read_bytes()

    def test_default_source(self):
        proposal, written = self.both()
        self.assertEqual(written, proposal)

    def test_another_hook_source(self):
        src = self.tmp / "src"
        (src / "hooks").mkdir(parents=True)
        (src / "hooks/only-one.sh").write_text("#!/bin/sh\nexit 0\n")
        (src / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/only-one.sh"}]}]}}))
        proposal, written = self.both("--hooks-from", str(src))
        self.assertEqual(written, proposal)
        self.assertEqual(list(json.loads(written)["hooks"]), ["Stop"])

    def test_user_scope_coverage_is_left_out_of_both(self):
        report = us.UserScope.report(self, {BLOBS: True})
        proposal, written = self.both("--user-scope", report)
        self.assertEqual(written, proposal)
        # counterfactual: the source wiring registers the covered hook, the render does not
        self.assertIn(BLOBS, (ROOT / SETTINGS).read_text())
        self.assertNotIn(BLOBS, written.decode())


class ExistingRepo(Case):
    def test_existing_repo_without_settings_gets_only_a_proposal(self):
        repo = git_repo(self.tmp / "r")
        code, res = self.run_json("r")
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        self.assertFalse((repo / SETTINGS).exists())
        self.assertTrue((repo / PROPOSAL).is_file())
        self.assertEqual(res["commit"]["status"], "none")

    def test_existing_settings_json_is_untouched(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude").mkdir()
        own = '{"permissions": {"allow": ["Bash(ls:*)"]}}'
        (repo / SETTINGS).write_text(own)
        self.run_json("r")
        self.assertEqual((repo / SETTINGS).read_text(), own)

    def test_a_later_run_on_a_created_repo_only_proposes(self):
        # once created, the repo is an existing one: what setup wrote is now Jacob's
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        before = (repo / SETTINGS).read_bytes()
        src = self.tmp / "src"
        (src / "hooks").mkdir(parents=True)
        (src / "hooks/only-one.sh").write_text("#!/bin/sh\nexit 0\n")
        (src / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/only-one.sh"}]}]}}))
        _, res = self.run_json("fresh", "--hooks-from", str(src))
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        self.assertEqual((repo / SETTINGS).read_bytes(), before)
        self.assertIn("Stop", json.loads((repo / PROPOSAL).read_text())["hooks"])
        # the proposal is ignored, so the repo shows only the new hook copy
        self.assertEqual(git(["status", "--porcelain", "--untracked-files=all"], repo).stdout,
                         "?? .claude/hooks/only-one.sh\n")


CHECKS_CLI = workspace_cli("checks")[1]


class LiveSettingsTracked(Case):
    """The seam with the shared checks' `settings-tracked` (§7.9's gate there): a repo
    setup creates passes it as created. Run as a subprocess, never imported."""

    def tracked_status(self, repo):
        r = subprocess.run([str(CHECKS_CLI), "one", "settings-tracked", str(repo), "--json"],
                           capture_output=True, text=True, env=self.env)
        results = json.loads(r.stdout)["results"]
        self.assertEqual([x["check"] for x in results], ["settings-tracked"], r.stdout)
        return results[0]["status"]

    @unittest.skipIf(CHECKS_CLI is None, "no shared checks CLI in a workspace around this tool (a lone clone)")
    def test_created_repo_passes_settings_tracked_and_an_untracked_copy_does_not(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        self.assertEqual(self.tracked_status(repo), "ok")
        # counterfactual: the same file, on disk but not committed
        git(["rm", "-q", "--cached", SETTINGS], repo)
        git(["commit", "-q", "-m", "untrack"], repo)
        self.assertEqual(self.tracked_status(repo), "fail")


class ScaffoldCommit(Case):
    def test_commit_takes_exactly_the_files_marked_for_it(self):
        repo = git_repo(self.tmp / "w", commit=False)
        w = Writer(repo, dry_run=False)
        w.write("kept.txt", "a\n")
        w.write("left-out.txt", "b\n", commit=False)
        self.assertIsNone(w.commit_scaffold("scaffold"))
        self.assertEqual(git(["ls-files"], repo).stdout.split(), ["kept.txt"])
        self.assertTrue((repo / "left-out.txt").is_file())

    def test_a_dry_writer_commits_nothing(self):
        repo = git_repo(self.tmp / "w", commit=False)
        before = snapshot(repo)
        w = Writer(repo, dry_run=True)
        w.write("kept.txt", "a\n")
        self.assertIsNone(w.commit_scaffold("scaffold"))
        self.assertEqual(snapshot(repo), before)
