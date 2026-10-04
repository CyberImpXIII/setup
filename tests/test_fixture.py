"""PLAN-repo-setup §3 "Fixture": a new folder, scaffolded, is a repo carrying every
component, and its check stub fails by name rather than faking green."""
import json
import shutil
import subprocess

from tests.helpers import ROOT, Case, git


class Fixture(Case):
    def test_new_folder_is_scaffolded_and_committed(self):
        code, res = self.run_json("fresh")
        self.assertEqual(code, 0)
        self.assertEqual(self.statuses(res), {
            "repo": "installed", "rules": "installed", "hooks": "needs-jacob",
            "todo": "installed", "check": "installed", "ignore": "installed", "commit": "installed",
            "remote": "none", "agent": "needs-harness", "server": "needs-harness"})
        repo = self.tmp / "fresh"
        self.assertEqual(git(["rev-parse", "--show-toplevel"], repo).stdout.strip(), str(repo))
        tracked = set(git(["ls-files"], repo).stdout.split())
        hooks = {f".claude/hooks/{p.name}" for p in (ROOT / ".claude" / "hooks").glob("*.sh")}
        self.assertEqual(tracked, {"CLAUDE.md", "TODO.md", "dev.sh", ".gitignore"} | hooks)
        # the settings proposal is Jacob's to apply: written, never committed,
        # and ignored, so the fresh repo reads clean and `git add -A` cannot take it
        self.assertTrue((repo / ".claude/settings.proposed.json").is_file())
        self.assertEqual(git(["status", "--porcelain", "--untracked-files=all"], repo).stdout, "")
        for h in hooks:
            self.assertEqual((repo / h).read_bytes(), (ROOT / h).read_bytes(), h)

    def test_check_stub_fails_by_name(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        r = subprocess.run(["./dev.sh", "check"], cwd=repo, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not implemented: fill in the contract", r.stdout)
        r = subprocess.run(["./dev.sh", "check", "--json"], cwd=repo, capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIs(json.loads(r.stdout)["ok"], False)
        # and setup itself names it as unfilled on the next run
        _, res = self.run_json("fresh")
        self.assertEqual(res["check"]["status"], "needs-owner")
        self.assertIn("unfilled stub", res["check"]["detail"])

    def test_applied_proposal_wires_every_hook(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        shutil.copy(repo / ".claude/settings.proposed.json", repo / ".claude/settings.json")
        _, res = self.run_json("fresh")
        self.assertEqual(res["hooks"]["status"], "unchanged")
        wired = json.loads((repo / ".claude/settings.json").read_text())
        source = json.loads((ROOT / ".claude/settings.json").read_text())
        self.assertEqual(wired, source)

    def test_name_flag_changes_the_output(self):
        self.run_json("fresh", "--name", "other-name")
        head = (self.tmp / "fresh" / "CLAUDE.md").read_text().splitlines()[0]
        self.assertEqual(head, "# other-name")
