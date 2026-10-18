"""The `## Practices` rules of `setup plans` (setuplib/practices.py; PLAN-services
§3 A3, §4 step 7.3), each input against its counterfactual: an id that resolves
in the registry passes and one that does not fails; a section naming no id, or
one id twice, fails; an approved decision naming a gate row that resolves, or
saying `prose:`, passes, and one doing neither fails, as does a gate row that
does not resolve; a decision not approved, and every decision of a plan without
the heading, is left alone. The required-heading rule is held (counted, never
failed) and, turned on, fails a plan without it. The registry is read from the
checks dependency's `registry` file; unreadable, ids named are UNCHECKED, exit 3,
in the gate and in `plans edit`. The live class runs the real gate against the
real registry (skipped, with the reason, when the workspace has none)."""
import json
import re
import shutil
import subprocess
import unittest

from setuplib import deps, practices
from tests.helpers import ROOT, Case, git_repo

IDS = {"root-seams", "wrong-answer"}
LIVE_IDS, LIVE_WHERE = practices.registry_ids()


def plan(practices_lines=None, decisions="", status="plan, planted"):
    """A plan not done, with a `## Practices` section holding the lines (none: no heading)."""
    sec = "" if practices_lines is None else f"## Practices\n\n{practices_lines}\n\n"
    return (f"# PLAN-p.md: planted\n\n> **Status: {status}.**\n\n## 1. Design\n\nThe design.\n\n"
            f"{sec}## 2. Decisions\n\n{decisions}\n\n## Setup component\n\nnone\n")


def run(text, ids=IDS, require=False):
    return practices.findings([("PLAN-p.md", text)], ids, require_heading=require)


def kinds(found):
    return [f.split(": ")[1] for f in found]


class Grammar(unittest.TestCase):
    def test_an_id_that_resolves_passes_and_one_that_does_not_fails(self):
        self.assertEqual(run(plan("- `root-seams`: held by its test")), ([], [], []))
        found, _, _ = run(plan("- `root-seamz`: held by its test"))
        self.assertEqual(kinds(found), ["unresolved"])
        self.assertIn("`root-seamz`", found[0])
        self.assertTrue(found[0].startswith("PLAN-p.md:11: "), found[0])

    def test_a_section_naming_no_id_fails(self):
        found, _, _ = run(plan("Every practice applies."))
        self.assertEqual(kinds(found), ["no-ids"])
        self.assertTrue(found[0].startswith("PLAN-p.md:9: "), found[0])  # the heading's line

    def test_an_id_named_twice_fails(self):
        found, _, _ = run(plan("- `root-seams`: one\n- `root-seams`: two"))
        self.assertEqual(kinds(found), ["listed-twice"])

    def test_only_a_list_item_starting_with_the_id_names_one(self):
        # prose mentioning an id in backticks is not a listing; the section still needs one
        found, _, _ = run(plan("This touches `root-seams` somewhere."))
        self.assertEqual(kinds(found), ["no-ids"])

    def test_a_numbered_or_parenthesised_heading_counts(self):
        for head in ("## 3. Practices", "### Practices (touched)"):
            with self.subTest(head=head):
                text = plan(None).replace("## 2. Decisions", f"{head}\n\n- `root-seams`: x\n\n## 2. Decisions")
                self.assertEqual(run(text), ([], [], []))

    def test_a_heading_in_fenced_code_is_no_heading(self):
        text = plan(None).replace("The design.", "The design.\n\n```\n## Practices\n```")
        self.assertEqual(run(text), ([], [], ["PLAN-p.md"]))

    def test_an_approved_decision_names_its_gate_row_or_says_prose(self):
        ok = "- `root-seams`: x"
        self.assertEqual(run(plan(ok, "- D1, approved: Jacob 2026-10-18. gate: `wrong-answer`")), ([], [], []))
        self.assertEqual(run(plan(ok, "- D1, approved: Jacob 2026-10-18. prose: no check can see intent")),
                         ([], [], []))
        found, _, _ = run(plan(ok, "- D1, approved: Jacob 2026-10-18."))
        self.assertEqual(kinds(found), ["no-gate-row"])
        found, _, _ = run(plan(ok, "- D1, approved: Jacob 2026-10-18. gate: `no-such-row`"))
        self.assertEqual(kinds(found), ["unresolved"])

    def test_a_decision_runs_over_its_continuation_lines_and_paragraphs_count(self):
        ok = "- `root-seams`: x"
        self.assertEqual(run(plan(ok, "- D1: adopt it\n  (approved: Jacob 2026-10-18),\n  gate: `wrong-answer`")),
                         ([], [], []))
        found, _, _ = run(plan(ok, "Approved 2026-10-18: the top level.\n\n- D2, approved; gate: `wrong-answer`"))
        self.assertEqual(kinds(found), ["no-gate-row"])
        self.assertTrue(found[0].startswith("PLAN-p.md:15: "), found[0])  # the paragraph, not D2

    def test_a_decision_not_approved_is_left_alone(self):
        self.assertEqual(run(plan("- `root-seams`: x", "- D1: open, for Jacob.")), ([], [], []))

    def test_a_plan_without_the_heading_is_counted_and_its_decisions_left_alone(self):
        self.assertEqual(run(plan(None, "- D1, approved: Jacob 2026-10-18.")), ([], [], ["PLAN-p.md"]))

    def test_the_required_heading_rule_is_held_and_turned_on_fails(self):
        self.assertFalse(practices.REQUIRE_HEADING)
        found, _, without = run(plan(None), require=True)
        self.assertEqual((kinds(found), without), (["missing"], ["PLAN-p.md"]))
        self.assertEqual(run(plan("- `root-seams`: x"), require=True), ([], [], []))

    def test_the_kinds_are_exactly_those_found(self):
        # KINDS is the documented vocabulary: every kind is produced, and nothing else is
        got = set()
        for text in (plan(None), plan("prose"), plan("- `root-seams`: a\n- `root-seams`: b"),
                     plan("- `x-y`: a", "- D1, approved.")):
            got |= set(kinds(run(text, require=True)[0]))
        self.assertEqual(got, set(practices.KINDS))

    def test_without_a_registry_every_id_is_unchecked_and_none_is_a_finding(self):
        found, unchecked, _ = run(plan("- `root-seams`: x", "- D1, approved. gate: `wrong-answer`"), ids=None)
        self.assertEqual((found, unchecked), ([], ["root-seams", "wrong-answer"]))
        # the grammar still holds without one
        self.assertEqual(kinds(run(plan("no ids"), ids=None)[0]), ["no-ids"])


class Registry(Case):
    """registry_ids reads the checks dependency's `registry` file, `rules[].id`."""

    def tool_with(self, gates):
        tool = self.tmp / "ws" / "tools" / "setup"
        tool.mkdir(parents=True)
        shutil.copy(ROOT / deps.DEPS_FILE, tool / deps.DEPS_FILE)
        d = json.loads((ROOT / deps.DEPS_FILE).read_text())["dependencies"]["checks"]
        checks = git_repo(self.tmp / "ws" / d["path"], commit=False)
        if gates is not None:
            (checks / d["registry"]).write_text(gates if isinstance(gates, str) else json.dumps(gates))
        return tool

    def test_the_rule_ids_are_read(self):
        tool = self.tool_with({"rules": [{"id": "a-b"}, {"id": "c"}, {"no": "id"}]})
        ids, where = practices.registry_ids(tool)
        self.assertEqual(ids, {"a-b", "c"})
        self.assertTrue(where.endswith("gates.json"), where)

    def test_an_unreadable_registry_gives_none_and_why(self):
        for gates, why in ((None, "is not a file"), ("{", "unreadable"), ({"rules": []}, "no `rules` list"),
                           ({"rules": [{"x": 1}]}, "carries an id")):
            with self.subTest(gates=gates):
                shutil.rmtree(self.tmp / "ws", ignore_errors=True)
                ids, got = practices.registry_ids(self.tool_with(gates))
                self.assertIsNone(ids)
                self.assertIn(why, got)


class LoneClone(Case):
    """No checks dependency: ids named are UNCHECKED, exit 3, never ok, and `plans
    edit` is refused naming it; a folder naming none still passes."""

    def test_ids_without_the_registry_are_unchecked_and_edit_is_refused(self):
        lone = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, lone, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__", ".progress"))
        d = self.tmp / "plans"
        d.mkdir()
        f = d / "PLAN-p.md"
        f.write_text(plan(None))
        r = subprocess.run([str(lone / "setup"), "plans", str(d)], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("  note  practices: 0 of 1 plan(s) not done carry a `## Practices` heading (the "
                      "required-heading rule is held: never a failure)", r.stdout)
        f.write_text(plan("- `root-seams`: x"))
        r = subprocess.run([str(lone / "setup"), "plans", str(d)], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        last = r.stdout.splitlines()[-1]
        self.assertTrue(last.startswith("  UNCHECKED  practices: 1 id(s) named (root-seams), none resolved: "), last)
        self.assertNotIn("  ok    ", r.stdout)
        show = subprocess.run([str(lone / "setup"), "plans", "show", str(f), "§1"], capture_output=True, text=True,
                              env=self.env)
        digest = re.search(r"digest (\w+)", show.stderr).group(1)
        src = self.tmp / "s1.md"
        src.write_text("## 1. Design\n\nThe design, edited.\n")
        r = subprocess.run([str(lone / "setup"), "plans", "edit", str(f), "§1", "--from", str(src),
                            "--digest", digest], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)  # a plans refusal exits 1
        self.assertIn("is not green: UNCHECKED practices: 1 id(s) named (root-seams)", r.stderr)
        self.assertIn("The design.\n", f.read_text())


@unittest.skipIf(LIVE_IDS is None, f"no practice registry in the workspace around this clone ({LIVE_WHERE})")
class Live(Case):
    """The real gate against the real registry: an id from it passes, one not in it fails."""

    def gate(self, text):
        d = self.tmp / "plans"
        d.mkdir(exist_ok=True)
        (d / "PLAN-p.md").write_text(text)
        return self.run_setup("plans", str(d))

    def test_a_registry_id_resolves_and_another_does_not(self):
        rid = sorted(LIVE_IDS)[0]
        r = self.gate(plan(f"- `{rid}`: held here", f"- D1, approved: Jacob 2026-10-18. gate: `{rid}`"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(f"1 of 1 plan(s) not done carry a `## Practices` heading (the required-heading rule is "
                      f"held: never a failure); ids resolved in {LIVE_WHERE}", r.stdout)
        self.assertTrue(r.stdout.splitlines()[-1].startswith("  ok    "), r.stdout)
        r = self.gate(plan(f"- `{rid}-not-a-row`: held here"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f"FAIL  PLAN-p.md:11: unresolved: `{rid}-not-a-row` is no id of the practice registry",
                      r.stdout)
