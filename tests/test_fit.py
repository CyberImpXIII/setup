"""The `## Fit` rule of `setup plans` (setuplib/fit.py; PLAN-architecture §6, §9
step 2), each input against its counterfactual: a plan declaring `**Creates:**`
passes with a `## Fit` section and fails without one (the passing and failing
fixture the plan's Gates name); a plan declaring nothing passes either way; an
empty Fit section fails; a Creates line naming no path fails; a declaration in
fenced code, or below the header, is no declaration. Through the real gate: the
FAIL line, the note, and `plans edit` refused when it would drop the section."""
import re
import unittest

from setuplib import fit
from tests.helpers import Case


def plan(creates=None, fit_body=None, status="plan, planted"):
    head = f"> **Creates:** {creates}\n" if creates is not None else ""
    sec = "" if fit_body is None else f"## Fit\n\n{fit_body}\n\n"
    return (f"# PLAN-f.md: planted\n\n> **Status: {status}.**\n{head}\n## 1. Design\n\nThe design.\n\n"
            f"{sec}## Setup component\n\nnone\n")


FIT = "Fits: `root-seams`. Duplicates: none (checks tools). Gives: unknown. Costs: unknown."


def run(text):
    return fit.findings([("PLAN-f.md", text)])


def kinds(found):
    return [f.split(": ")[1] for f in found]


class Grammar(unittest.TestCase):
    def test_a_plan_that_creates_a_tool_needs_the_heading(self):
        self.assertEqual(run(plan("`tools/x`", FIT)), ([], ["PLAN-f.md"], ["PLAN-f.md"]))
        found, declaring, with_fit = run(plan("`tools/x`"))
        self.assertEqual((kinds(found), declaring, with_fit), (["no-fit"], ["PLAN-f.md"], []))
        self.assertTrue(found[0].startswith("PLAN-f.md:4: no-fit: a plan that creates a tool (tools/x)"), found[0])

    def test_a_plan_declaring_nothing_passes_with_or_without_it(self):
        self.assertEqual(run(plan()), ([], [], []))
        self.assertEqual(run(plan(None, FIT)), ([], [], ["PLAN-f.md"]))  # accepted, never required

    def test_an_empty_fit_section_fails(self):
        found, _, _ = run(plan(None, ""))
        self.assertEqual(kinds(found), ["empty-fit"])
        found, _, _ = run(plan("`tools/x`", ""))
        self.assertEqual(kinds(found), ["empty-fit"])  # carried, so not no-fit

    def test_a_creates_line_names_its_paths(self):
        found, _, _ = run(plan("a new tool", FIT))
        self.assertEqual(kinds(found), ["no-path"])
        self.assertEqual(run(plan("`tools/x`, `tools/y`", FIT))[0], [])

    def test_both_bold_forms_and_a_numbered_heading_count(self):
        text = plan(None, None).replace("> **Status: plan, planted.**",
                                        "> **Status: plan, planted.**\n> **Creates: `tools/x`.**")
        self.assertEqual(kinds(run(text)[0]), ["no-fit"])
        text = text.replace("## Setup component", "## 4. Fit (for Jacob)\n\nFits: unknown.\n\n## Setup component")
        self.assertEqual(run(text)[0], [])

    def test_a_declaration_in_fenced_code_or_below_the_header_is_none(self):
        fenced = plan().replace("> **Status: plan, planted.**",
                                "> **Status: plan, planted.**\n```\n> **Creates:** `tools/x`\n```")
        self.assertEqual(run(fenced), ([], [], []))
        low = plan() + "\n" * 30 + "> **Creates:** `tools/x`\n"
        self.assertEqual(run(low), ([], [], []))

    def test_the_kinds_are_exactly_those_found(self):
        got = set()
        for text in (plan("`tools/x`"), plan(None, ""), plan("a tool", FIT)):
            got |= set(kinds(run(text)[0]))
        self.assertEqual(got, set(fit.KINDS))


class Gate(Case):
    """The real `setup plans`: the FAIL line, the note, and the guarded write."""

    def folder(self, text):
        d = self.tmp / "plans"
        d.mkdir(exist_ok=True)
        f = d / "PLAN-f.md"
        f.write_text(text)
        return d, f

    def test_the_gate_fails_without_the_heading_and_passes_with_it(self):
        d, f = self.folder(plan("`tools/x`", FIT))
        r = self.run_setup("plans", str(d))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("  note  fit: 1 plan(s) not done declare `**Creates:**`, 1 carry a `## Fit` heading", r.stdout)
        self.assertTrue(r.stdout.splitlines()[-1].startswith("  ok    "), r.stdout)
        f.write_text(plan("`tools/x`"))
        r = self.run_setup("plans", str(d))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("  FAIL  PLAN-f.md:4: no-fit: a plan that creates a tool (tools/x)", r.stdout)

    def test_plans_edit_is_refused_when_it_would_empty_the_fit_section(self):
        d, f = self.folder(plan("`tools/x`", FIT).replace("## Fit", "## 2. Fit"))
        show = self.run_setup("plans", "show", str(f), "§2")
        self.assertEqual(show.returncode, 0, show.stderr)
        digest = re.search(r"digest (\w+)", show.stderr).group(1)
        src = self.tmp / "s2.md"
        src.write_text("## 2. Fit\n\n")
        r = self.run_setup("plans", "edit", str(f), "§2", "--from", str(src), "--digest", digest)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("would turn `setup plans", r.stderr)
        self.assertIn("empty-fit", r.stderr)
        self.assertIn(FIT, f.read_text())
