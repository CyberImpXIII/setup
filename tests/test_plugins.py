"""The hooks component's plug-in proposals: a hook owned elsewhere and run in place
is proposed for settings.json when the registry given with --plugins says it
applies to the target, and never otherwise. The registry's shape is the JSON the
shared hooks source prints for its plug-ins: {root, ok, plugins: [{name,
applies_to, faults, registration}]}."""
import json

from tests.helpers import Case, git_repo

CMD = "$CLAUDE_PROJECT_DIR/kb/hooks/pointers.sh"


def registration(cmd=CMD):
    return {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": cmd}]}]}


class Plugins(Case):
    def registry(self, root, applies_to="repos:.", ok=True, faults=(), **extra):
        doc = {"root": str(root), "ok": ok, "plugins": [
            {"name": "pointers", "applies_to": applies_to, "faults": list(faults),
             "registration": registration(), **extra}]}
        f = self.tmp / "plugins.json"
        f.write_text(json.dumps(doc))
        return str(f)

    def proposed_commands(self, repo, event="UserPromptSubmit"):
        prop = json.loads((repo / ".claude/settings.proposed.json").read_text())
        return [h["command"] for g in prop["hooks"].get(event, []) for h in g.get("hooks", [])]

    def test_plugin_that_applies_here_is_proposed_and_only_with_the_registry(self):
        top = git_repo(self.tmp / "ws")
        _, res = self.run_json("ws", "--plugins", self.registry(top))
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        self.assertEqual(self.proposed_commands(top), [CMD])
        self.assertIn("pointers", res["hooks"]["detail"])
        # counterfactual: the same repo without the registry proposes no plug-in
        other = git_repo(self.tmp / "ws2")
        _, res = self.run_json("ws2")
        self.assertEqual(self.proposed_commands(other), [])
        self.assertIn("no --plugins", res["hooks"]["detail"])

    def test_plugin_for_another_place_is_not_proposed(self):
        top = git_repo(self.tmp / "ws")
        sub = git_repo(top / "sub")
        code, res = self.run_json("ws/sub", "--plugins", self.registry(top, "repos:."))
        self.assertEqual(self.proposed_commands(sub), [])
        self.assertNotEqual(res["hooks"]["status"], "failed")
        code, res = self.run_json("ws", "--plugins", self.registry(top, "repos:other,sub"))
        self.assertEqual(self.proposed_commands(top), [])

    def test_plugin_already_registered_by_meaning_is_not_proposed_again(self):
        top = git_repo(self.tmp / "ws")
        (top / ".claude").mkdir()
        quoted = '"$CLAUDE_PROJECT_DIR"/kb/hooks/pointers.sh'
        (top / ".claude/settings.json").write_text(json.dumps({"hooks": registration(quoted)}))
        _, res = self.run_json("ws", "--plugins", self.registry(top))
        self.assertEqual(self.proposed_commands(top), [quoted])

    def test_registry_that_is_not_ok_fails_and_proposes_nothing_from_it(self):
        top = git_repo(self.tmp / "ws")
        code, res = self.run_json("ws", "--plugins", self.registry(top, ok=False))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertEqual(self.proposed_commands(top), [])

    def test_faulty_plugin_fails_and_is_not_proposed(self):
        top = git_repo(self.tmp / "ws")
        code, res = self.run_json("ws", "--plugins", self.registry(top, faults=["not executable"]))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertEqual(self.proposed_commands(top), [])

    def test_unreadable_registry_fails(self):
        top = git_repo(self.tmp / "ws")
        (self.tmp / "bad.json").write_text("{not json")
        code, res = self.run_json("ws", "--plugins", str(self.tmp / "bad.json"))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertIn("unreadable", res["hooks"]["detail"])

    def test_plugin_applying_below_the_top_fails_rather_than_guess_its_command(self):
        # the registration runs from the workspace top; from sub/ the same command
        # would point at sub/kb/hooks/pointers.sh, so nothing is proposed
        top = git_repo(self.tmp / "ws")
        sub = git_repo(top / "sub")
        code, res = self.run_json("ws/sub", "--plugins", self.registry(top, "repos:sub"))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertEqual(self.proposed_commands(sub), [])
        self.assertIn("workspace top", res["hooks"]["detail"])

    def test_roles_plugin_is_left_to_the_harness_with_its_registration(self):
        top = git_repo(self.tmp / "ws")
        code, res = self.run_json("ws", "--plugins", self.registry(top, "roles:reviewer"))
        self.assertEqual(self.proposed_commands(top), [])
        self.assertIn("roles", res["hooks"]["detail"])
        self.assertIn("pointers.sh", res["hooks"]["detail"])
        self.assertNotEqual(res["hooks"]["status"], "failed")

    def test_unknown_applies_to_fails(self):
        top = git_repo(self.tmp / "ws")
        code, res = self.run_json("ws", "--plugins", self.registry(top, "everywhere"))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertEqual(self.proposed_commands(top), [])

    def test_dry_run_reports_the_plugin_and_writes_nothing(self):
        top = git_repo(self.tmp / "ws")
        _, res = self.run_json("ws", "--dry-run", "--plugins", self.registry(top))
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        self.assertFalse((top / ".claude").exists())
