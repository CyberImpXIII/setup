"""The hooks component: copies, drift that is never overwritten, settings proposals."""
import json

from tests.helpers import ROOT, Case, git_repo


class Hooks(Case):
    def test_differing_copy_is_drift_and_not_overwritten(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        mine = repo / ".claude/hooks/no-inline-blobs.sh"
        mine.write_text("#!/bin/sh\nlocal edit\n")
        code, res = self.run_json("r")
        self.assertEqual((code, res["hooks"]["status"]), (1, "drift"))
        self.assertIn("no-inline-blobs.sh differs", res["hooks"]["detail"])
        self.assertEqual(mine.read_text(), "#!/bin/sh\nlocal edit\n")

    def test_proposal_keeps_existing_settings(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude").mkdir()
        own = {"permissions": {"allow": ["Bash(ls:*)"]},
               "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                   {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/own.sh"}]}]}}
        (repo / ".claude/settings.json").write_text(json.dumps(own))
        _, res = self.run_json("r")
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        prop = json.loads((repo / ".claude/settings.proposed.json").read_text())
        self.assertEqual(prop["permissions"], own["permissions"])
        bash = [g for g in prop["hooks"]["PreToolUse"] if g["matcher"] == "Bash"]
        self.assertEqual(len(bash), 1)
        cmds = [h["command"].rsplit("/", 1)[1] for h in bash[0]["hooks"]]
        self.assertEqual(cmds[0], "own.sh")
        self.assertIn("no-inline-blobs.sh", cmds)
        # settings.json itself is Jacob's: untouched
        self.assertEqual(json.loads((repo / ".claude/settings.json").read_text()), own)

    def test_unparseable_settings_fail_and_propose_nothing(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude").mkdir()
        (repo / ".claude/settings.json").write_text("{not json")
        code, res = self.run_json("r")
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertFalse((repo / ".claude/settings.proposed.json").exists())

    def test_hooks_from_changes_what_is_installed(self):
        src = self.tmp / "src"
        (src / "hooks").mkdir(parents=True)
        (src / "hooks/only-one.sh").write_text("#!/bin/sh\nexit 0\n")
        (src / "settings.json").write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/only-one.sh"}]}]}}))
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--hooks-from", str(src))
        self.assertEqual(sorted(p.name for p in (repo / ".claude/hooks").iterdir()), ["only-one.sh"])
        prop = json.loads((repo / ".claude/settings.proposed.json").read_text())
        self.assertEqual(list(prop["hooks"]), ["Stop"])
        self.assertIn("1 installed", res["hooks"]["detail"])

    def test_empty_hook_source_fails(self):
        (self.tmp / "empty").mkdir()
        git_repo(self.tmp / "r")
        code, res = self.run_json("r", "--hooks-from", str(self.tmp / "empty"))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))

    def test_default_source_is_this_tools_own_copies(self):
        repo = git_repo(self.tmp / "r")
        self.run_json("r")
        got = sorted(p.name for p in (repo / ".claude/hooks").iterdir())
        self.assertEqual(got, sorted(p.name for p in (ROOT / ".claude/hooks").glob("*.sh")))
