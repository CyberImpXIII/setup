"""`setup plans <dir> --facts` (PLAN-architecture §12 item 3): a fact cites its
command as `` `<cmd>` → <value> ``; the command is re-run when it is a declared
read verb, and a changed value is listed. The gates: a cited command that is not
a declared verb fails (and is never run); a fact whose command now returns a
different value is listed as changed."""
import json

from tests.helpers import Case

CLI = """#!/bin/sh
here=$(dirname "$0")
case "$1" in
  count) [ "$2" = "--fail" ] && { echo "no such thing" >&2; exit 3; }; cat "$here/n" ;;
  add) touch "$here/ran-add" ;;
esac
"""

PLAN = """# Plan alpha

## 1. Counts

- open: `./alpha count` → 3
- the same, by name: `alpha count` → `3`.
- a write verb: `./alpha add x` → 1
- a CLI nobody declares: `beta count` → 1
- a pipe: `./alpha count | wc -l` → 1
- a failing run: `./alpha count --fail` → 1
- an old figure (read by hand, 2026-10-01)
"""


class Facts(Case):
    def fixture(self, n="3", plan=PLAN):
        d = self.tmp / "plans"
        d.mkdir(exist_ok=True)
        (d / "cli.json").write_text(json.dumps(
            {"cli": "alpha", "verbs": ["count", "add"], "read": {"verbs": {"count": {}}}}))
        (d / "alpha").write_text(CLI)
        (d / "alpha").chmod(0o755)
        (d / "n").write_text(n + "\n")
        (d / "PLAN-alpha.md").write_text(plan)
        return d

    def report(self, d, *extra):
        r = self.run_setup("plans", str(d), "--facts", "--json", *extra)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        doc = json.loads(r.stdout)
        return r.returncode, doc, {f["cmd"]: f for f in doc["facts"]}

    def test_each_kind_of_fact_gets_its_status(self):
        d = self.fixture()
        code, doc, by = self.report(d)
        self.assertEqual(code, 1)
        self.assertEqual({k: v["status"] for k, v in by.items()}, {
            "./alpha count": "same",
            "alpha count": "same",
            "./alpha add x": "not-declared",
            "beta count": "not-declared",
            "./alpha count | wc -l": "not-one-command",
            "./alpha count --fail": "failed",
        })
        self.assertEqual(doc["by_hand"], 1)
        self.assertIn("exit 3", by["./alpha count --fail"]["why"])

    def test_a_command_that_is_not_a_read_verb_is_never_run(self):
        d = self.fixture()
        self.report(d)
        self.assertFalse((d / "ran-add").exists())

    def test_a_changed_value_is_listed_and_the_same_one_is_not(self):
        d = self.fixture(n="4")
        _, _, by = self.report(d)
        self.assertEqual(by["./alpha count"]["status"], "changed")
        self.assertEqual(by["./alpha count"]["now"], "4")
        r = self.run_setup("plans", str(d), "--facts")
        self.assertIn("changed", r.stdout)
        self.assertIn("PLAN-alpha.md:5", r.stdout)

    def test_every_fact_the_same_exits_0(self):
        d = self.fixture(plan="# Plan alpha\n\n## 1. Counts\n\n- open: `./alpha count` → 3\n")
        code, doc, _ = self.report(d)
        self.assertEqual((code, doc["counts"]["same"]), (0, 1))
        # counterfactual: the same plan, the value moved
        (d / "n").write_text("5\n")
        code, doc, _ = self.report(d)
        self.assertEqual((code, doc["counts"]["changed"]), (1, 1))

    def test_two_cli_json_declaring_one_name_is_ambiguous(self):
        d = self.fixture(plan="# Plan alpha\n\n## 1. Counts\n\n- open: `alpha count` → 3\n")
        (d / "other").mkdir()
        (d / "other/cli.json").write_text(json.dumps({"cli": "alpha", "read": {"verbs": {"count": {}}}}))
        _, _, by = self.report(d)
        self.assertEqual(by["alpha count"]["status"], "ambiguous")

    def test_root_widens_where_cli_json_is_looked_for(self):
        d = self.fixture(plan="# Plan alpha\n\n## 1. Counts\n\n- open: `../tool/alpha count` → 3\n")
        tool = self.tmp / "tool"
        tool.mkdir()
        for f in ("cli.json", "alpha", "n"):
            (d / f).rename(tool / f)
        _, _, by = self.report(d)
        self.assertEqual(by["../tool/alpha count"]["status"], "not-declared")
        _, _, by = self.report(d, "--root", str(self.tmp))
        self.assertEqual(by["../tool/alpha count"]["status"], "same")

    def test_a_done_plan_is_not_read(self):
        d = self.fixture(plan="# Plan alpha\n\n**Status: done**\n\n## 1. Counts\n\n- `beta count` → 1\n")
        code, doc, _ = self.report(d)
        self.assertEqual((code, doc["facts"]), (0, []))

    def test_usage_and_missing_folders(self):
        d = self.fixture()
        self.assertEqual(self.run_setup("plans", str(d), "--facts", "--steps").returncode, 2)
        self.assertEqual(self.run_setup("plans", str(d), "--root", str(d)).returncode, 2)
        self.assertEqual(self.run_setup("plans", str(self.tmp / "nope"), "--facts").returncode, 2)
        self.assertEqual(self.run_setup("plans", str(d), "--facts", "--root", str(self.tmp / "nope")).returncode, 2)
