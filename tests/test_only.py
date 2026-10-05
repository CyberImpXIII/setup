"""--only COMPONENT: one component alone, on an existing repo (so an owner can install
the hook copies without the rest). Documented == implemented: the help, `setup
components`, and every flag the parser takes."""
import re

from setuplib import core
from tests.helpers import ROOT, Case, git_repo, hook_source, snapshot


class Only(Case):
    def test_only_hooks_installs_the_hook_copies_and_nothing_else(self):
        repo = git_repo(self.tmp / "r")
        src = hook_source(self.tmp / "src", ["a.sh", "b.sh"])
        before = snapshot(repo)
        code, res = self.run_json("r", "--hooks-from", str(src), "--only", "hooks")
        self.assertEqual(list(res), ["hooks"], res)
        self.assertIn("4 installed", res["hooks"]["detail"])  # needs-jacob: the proposal is his
        self.assertTrue((repo / ".claude/hooks/a.sh").is_file())
        changed = {p for p in set(snapshot(repo)) ^ set(before) if not p.startswith(".git/")}
        self.assertTrue(changed and all(p.startswith(".claude/") for p in changed), sorted(changed))
        # the counterfactual: a full run writes outside .claude/ (TODO.md among them)
        self.run_json("r", "--hooks-from", str(src))
        self.assertTrue((repo / "TODO.md").is_file())

    def test_only_on_a_new_folder_is_refused_and_writes_nothing(self):
        r = self.run_setup("fresh", "--only", "hooks")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--only hooks", r.stderr)
        self.assertFalse((self.tmp / "fresh").exists())

    def test_an_unknown_component_is_a_usage_error(self):
        git_repo(self.tmp / "r")
        r = self.run_setup("r", "--only", "nope")
        self.assertEqual(r.returncode, 2)
        for c in core.load_spec()["components"]:
            self.assertIn(c["name"], r.stderr)

    def test_only_with_node_is_a_usage_error(self):
        git_repo(self.tmp / "r")
        r = self.run_setup("r", "--node", "--only", "hooks")
        self.assertEqual(r.returncode, 2, r.stderr)


class Documented(Case):
    def test_help_and_components_name_only(self):
        self.assertIn("--only COMPONENT", self.run_setup("--help").stdout)
        self.assertIn("--only <component>", self.run_setup("components").stdout)

    def test_every_flag_the_parser_takes_is_in_the_help(self):
        flags = set(re.findall(r'add_argument\("(--[a-z-]+)"', (ROOT / "setup").read_text()))
        self.assertIn("--only", flags)
        helped = set(re.findall(r"--[a-z][a-z-]*", self.run_setup("--help").stdout))
        self.assertEqual(flags - helped, set())
