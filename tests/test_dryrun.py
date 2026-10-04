"""PLAN-repo-setup §3 "It's the definition": --dry-run reports drift and writes nothing."""
from tests.helpers import Case, git_repo, snapshot


class DryRun(Case):
    def test_dry_run_on_a_new_path_creates_nothing(self):
        code, res = self.run_json("fresh", "--dry-run")
        self.assertEqual(code, 0)
        self.assertFalse((self.tmp / "fresh").exists())
        self.assertEqual(res["repo"]["status"], "installed")
        self.assertIn("would", res["repo"]["detail"])

    def test_dry_run_on_a_drifted_repo_reports_and_writes_nothing(self):
        repo = git_repo(self.tmp / "old")
        (repo / "CLAUDE.md").write_text("# old\n\nhand-copied rules, no markers\n")
        (repo / ".claude/hooks").mkdir(parents=True)
        (repo / ".claude/hooks/no-inline-blobs.sh").write_text("#!/bin/sh\necho drifted\n")
        (repo / "dev.sh").write_text("#!/usr/bin/env bash\necho ok\n")
        (repo / "dev.sh").chmod(0o644)
        before = snapshot(repo)
        code, res = self.run_json("old", "--dry-run")
        self.assertEqual(code, 1)
        self.assertEqual(snapshot(repo), before)
        st = self.statuses(res)
        self.assertEqual((st["rules"], st["hooks"], st["check"]), ("drift", "drift", "drift"))
        self.assertEqual(st["todo"], "installed")  # would install; did not
        self.assertFalse((repo / "TODO.md").exists())
