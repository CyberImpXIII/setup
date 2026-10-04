"""PLAN-repo-setup §3 "Idempotent": a second run writes nothing and installs nothing;
once the owner and Jacob have done their parts, everything setup owns is unchanged."""
import shutil

from tests.helpers import Case, snapshot


class Idempotent(Case):
    def test_second_run_writes_nothing(self):
        self.run_json("fresh")
        before = snapshot(self.tmp / "fresh")
        code, res = self.run_json("fresh")
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(self.tmp / "fresh"), before)
        self.assertNotIn("installed", self.statuses(res).values())
        self.assertNotIn("drift", self.statuses(res).values())

    def test_settled_repo_is_all_unchanged(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        shutil.copy(repo / ".claude/settings.proposed.json", repo / ".claude/settings.json")
        (repo / "dev.sh").write_text("#!/usr/bin/env bash\necho ok\n")
        code, res = self.run_json("fresh")
        self.assertEqual(code, 0)
        st = self.statuses(res)
        for comp in ("repo", "rules", "hooks", "todo", "check", "ignore"):
            self.assertEqual(st[comp], "unchanged", comp)
        self.assertEqual((st["commit"], st["remote"], st["agent"], st["server"]),
                         ("none", "none", "needs-harness", "needs-harness"))
