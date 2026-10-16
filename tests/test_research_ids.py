"""The `## Research` id rules of `setup plans` (setuplib/rsids.py; PLAN-services
§3 R1, R6, §4 step 8.4), both ways, against the real research CLI on a scratch
store built through that CLI alone (RESEARCH_HOME): a Decisions row resting on a
question answered in full passes; one resting on an open question, on one answered
only at quick depth, or on an id that does not resolve fails; a malformed Research
line, an id cited and not listed, and one listed twice fail; a plan citing no id is
untouched. Without the CLI (a lone clone), ids cited are UNCHECKED, exit 3, never ok.
Skipped, with the reason, when the workspace has no research CLI."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from setuplib import rsids
from tests.helpers import ROOT, Case, workspace_cli

_, CLI = workspace_cli("research")
TODAY = "2026-10-16"

# (question, ask flags, then the steps after the ask) -> the record each test cites by role
QUESTIONS = {
    "full": ("Which boards list the planted roles, in full?", ["--depth", "full"], ["answer"]),
    "quick": ("Which boards list the planted roles, quickly?", [], ["answer"]),
    "open": ("Is the planted board still open to runs?", [], []),
    "raised": ("Does the planted board page its listings?", [], ["answer", "raise"]),
    "jacob": ("Should the planted board become a run source?", ["--to", "jacob"], ["jacob"]),
}


def _cli(home, *args):
    env = dict(os.environ, RESEARCH_HOME=str(home), RESEARCH_TODAY=TODAY,
               RESEARCH_KB=str(Path(home) / "no-kb"))
    r = subprocess.run([str(CLI), *args], env=env, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise AssertionError(f"research {' '.join(args)}: exit {r.returncode}: {r.stderr.strip()}")
    return r


def build_store(home):
    """{role: rs id} after building the store at `home` through the CLI."""
    _cli(home, "init")
    ids = {}
    for n, (role, (q, flags, then)) in enumerate(QUESTIONS.items(), 1):
        title = ["--title", "Planted questions"] if n == 1 else []  # a new topic is named once
        _cli(home, "ask", q, "--topic", "planted", *title, "--tags", "repo:planted", *flags, "--new")
        rid = f"rs-{n}"
        for step in then:
            if step == "answer":
                _cli(home, "answer", rid, "--text", "Planted answer.", "--ran", "planted --count", "3")
            elif step == "raise":
                _cli(home, "depth", rid, "full", "--by", "asker")
            elif step == "jacob":
                _cli(home, "jacob", rid, "yes, plant it", "--date", TODAY)
        ids[role] = rid
    return ids


def plan(research_lines="", decisions="", body=""):
    return (f"# PLAN-r.md: planted\n\n> **Status: plan, planted.**\n\n## 1. Design\n\nThe design. {body}\n\n"
            f"## Research\n\n{research_lines}\n\n## 2. Decisions for Jacob\n\n{decisions}\n\n"
            "## Setup component\n\nnone\n")


@unittest.skipIf(CLI is None, "no research CLI in the workspace around this clone (tools/research/research)")
class ResearchIds(Case):
    @classmethod
    def setUpClass(cls):
        cls.store = Path(tempfile.mkdtemp(prefix="setup-research-store-")).resolve()
        cls.ids = build_store(cls.store)
        cls.listing = "\n".join(f"- {rid} -- {QUESTIONS[role][0]}" for role, rid in cls.ids.items())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.store, True)

    def setUp(self):
        super().setUp()
        self.env["RESEARCH_HOME"] = str(self.store)

    def gate(self, text, name="PLAN-r.md"):
        d = self.tmp / "plans"
        d.mkdir(exist_ok=True)
        (d / name).write_text(text)
        r = self.run_setup("plans", str(d))
        return r.returncode, r.stdout.splitlines()

    def fails(self, lines, kind):
        return [l for l in lines if l.startswith("  FAIL  ") and f": {kind}: " in l]

    # the store is what the tests say it is: read back through the CLI, not assumed
    def test_the_store_holds_each_role(self):
        want = {"full": ("answered", "full"), "quick": ("answered", "quick"), "open": ("open", None),
                "raised": ("open", "quick")}
        for role, (status, depth) in want.items():
            rec = json.loads(_cli(self.store, "get", self.ids[role], "--json").stdout)
            self.assertEqual((rec["status"], rec["answered_depth"]), (status, depth), role)

    def test_a_decision_resting_on_a_full_answer_passes(self):
        code, out = self.gate(plan(self.listing, f"- Adopt the board ({self.ids['full']})."))
        self.assertEqual(code, 0, out)
        self.assertTrue(out[-1].startswith("  ok    "), out)
        self.assertIn("  note  research: 6 citation(s) of rs- ids in 1 plan(s), resolved with", "\n".join(out))

    def test_a_decision_resting_on_a_quick_answer_fails(self):
        code, out = self.gate(plan(self.listing, f"- Adopt the board ({self.ids['quick']})."))
        self.assertEqual(code, 1, out)
        hit = self.fails(out, "quick")
        self.assertEqual(len(hit), 1, out)
        self.assertIn(f"rests on {self.ids['quick']}, answered only at quick depth", hit[0])
        self.assertNotIn("  ok    ", "\n".join(out))

    def test_the_same_quick_answer_outside_decisions_passes(self):
        """The counterfactual: the location is what fails it, not the id."""
        code, out = self.gate(plan(self.listing, "- Adopt the board.", body=f"See {self.ids['quick']}."))
        self.assertEqual(code, 0, out)

    def test_a_decision_resting_on_an_open_question_fails(self):
        code, out = self.gate(plan(self.listing, f"- Adopt the board ({self.ids['open']})."))
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.fails(out, "open")), 1, out)

    def test_a_quick_answer_raised_to_full_is_open_and_says_its_depth(self):
        code, out = self.gate(plan(self.listing, f"- Adopt the board ({self.ids['raised']})."))
        self.assertEqual(code, 1, out)
        hit = self.fails(out, "open")
        self.assertEqual(len(hit), 1, out)
        self.assertIn("its answer is only at quick depth", hit[0])

    def test_an_id_that_does_not_resolve_fails_anywhere(self):
        listing = self.listing + "\n- rs-99 -- A question the store never heard of?"
        code, out = self.gate(plan(listing, "- Adopt the board.", body="See rs-99."))
        self.assertEqual(code, 1, out)
        hit = self.fails(out, "unresolved")
        self.assertEqual(len(hit), 2, out)  # listed and cited: each line names it
        self.assertIn("no such record", hit[0])

    def test_jacobs_answer_record_resolves_and_an_unknown_one_does_not(self):
        rid = self.ids["jacob"]
        code, out = self.gate(plan(self.listing, "- Adopt the board.", body=f"Jacob said so ({rid}.j1)."))
        self.assertEqual(code, 0, out)
        code, out = self.gate(plan(self.listing, "- Adopt the board.", body=f"Jacob said so ({rid}.j9)."))
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.fails(out, "unresolved")), 1, out)

    def test_a_malformed_research_line_fails_and_other_lines_are_left_alone(self):
        listing = self.listing.replace(f"- {self.ids['full']} -- ", f"- {self.ids['full']}: ")
        code, out = self.gate(plan(listing + "\n- Q5: a question from before the service", "- Adopt it."))
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.fails(out, "malformed")), 1, out)
        self.assertEqual([l for l in out if "  FAIL  " in l and "malformed" not in l], [], out)

    def test_an_id_cited_and_not_listed_fails(self):
        listing = "\n".join(l for l in self.listing.splitlines() if not l.startswith(f"- {self.ids['full']} "))
        code, out = self.gate(plan(listing, f"- Adopt the board ({self.ids['full']})."))
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.fails(out, "not-listed")), 1, out)

    def test_an_id_listed_twice_fails(self):
        first = self.listing.splitlines()[0]
        code, out = self.gate(plan(self.listing + "\n" + first, "- Adopt the board."))
        self.assertEqual(code, 1, out)
        self.assertEqual(len(self.fails(out, "listed-twice")), 1, out)

    def test_a_plan_citing_no_id_is_untouched(self):
        code, out = self.gate(plan("- Q1: a question from before the service", "- Adopt the board."))
        self.assertEqual(code, 0, out)
        self.assertNotIn("research:", "\n".join(out))

    def test_ids_in_fenced_code_and_in_a_done_plan_are_not_read(self):
        fenced = plan(self.listing, "- Adopt the board.\n\n```\nrs-99 in an example\n```")
        self.assertEqual(self.gate(fenced)[0], 0)
        done = plan("- rs-99 -- never heard of", "- Adopt it (rs-99).").replace(
            "**Status: plan, planted.**", "**Status: done**")
        self.assertEqual(self.gate(done, "PLAN-r.md")[0], 0)

    def test_a_numbered_decisions_subsection_counts_and_ends_at_its_level(self):
        text = plan(self.listing, "- Adopt the board.").replace(
            "## Setup component", f"### 2.1 Decisions\n\n- Rests on {self.ids['quick']}.\n\n"
                                  f"## 3. After\n\nAlso {self.ids['quick']}.\n\n## Setup component")
        code, out = self.gate(text)
        self.assertEqual(len(self.fails(out, "quick")), 1, out)  # the 2.1 row, not §3's mention

    def test_plans_edit_is_refused_when_it_would_rest_a_decision_on_a_quick_answer(self):
        d = self.tmp / "plans"
        d.mkdir()
        f = d / "PLAN-r.md"
        f.write_text(plan(self.listing, "- Adopt the board."))
        show = self.run_setup("plans", "show", str(f), "§2")
        self.assertEqual(show.returncode, 0, show.stderr)
        digest = show.stderr.split("digest ")[1].strip()
        src = self.tmp / "new.md"
        src.write_text(f"## 2. Decisions for Jacob\n\n- Adopt the board ({self.ids['quick']}).\n")
        before = f.read_text()
        r = self.run_setup("plans", "edit", str(f), "§2", "--from", str(src), "--digest", digest)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("would turn", r.stderr)
        self.assertIn(": quick: ", r.stderr)
        self.assertEqual(f.read_text(), before)
        src.write_text(f"## 2. Decisions for Jacob\n\n- Adopt the board ({self.ids['full']}).\n")
        r = self.run_setup("plans", "edit", str(f), "§2", "--from", str(src), "--digest", digest)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn(self.ids["full"], f.read_text())


class Grammar(Case):
    """setuplib/rsids.py's reading of a plan, no CLI needed."""

    def test_the_sections_are_read_as_the_plans_write_them(self):
        text = plan("- rs-1 -- a question", "- Rests on rs-1.")
        cites, listed, findings = rsids.cited(text)
        self.assertEqual(listed, {"rs-1": text.splitlines().index("- rs-1 -- a question") + 1})
        self.assertEqual(findings, [])
        self.assertEqual([c[2] for c in cites], [False, True])  # the listing, then the Decisions row

    def test_an_id_inside_a_longer_token_is_not_one(self):
        self.assertEqual(rsids.cited(plan("", "", body="xrs-1, rs-1x, rs-12a, crs-3"))[0], [])

    def test_the_status_reading_is_closed(self):
        """Every (status, answered_depth) the CLI can give has one reading; anything
        else is a finding, never a pass."""
        self.assertIsNone(rsids.depth_finding("rs-1", {"status": "answered", "answered_depth": "full"}))
        for rec, kind in (({"status": "answered", "answered_depth": "quick"}, "quick"),
                          ({"status": "open", "answered_depth": None}, "open"),
                          ({"status": "open", "answered_depth": "quick"}, "open"),
                          ({"status": "answered", "answered_depth": None}, "unresolved"),
                          ({"status": None, "answered_depth": "full"}, "unresolved"),
                          ({}, "unresolved")):
            self.assertEqual(rsids.depth_finding("rs-1", rec)[0], kind, rec)

    def test_a_record_for_another_id_or_no_json_is_not_taken(self):
        """lookup's fail paths, with a stand-in CLI printing what it is given."""
        fake = self.tmp / "fake-cli"
        out = self.tmp / "fake-out"
        fake.write_text(f"#!/bin/sh\ncat '{out}'\n")
        fake.chmod(0o755)
        out.write_text('{"id": "research:rs-2", "status": "answered", "answered_depth": "full"}')
        rec, why = rsids.lookup(fake, "rs-1")
        self.assertIsNone(rec)
        self.assertIn("answered for another id", why)
        self.assertEqual(rsids.lookup(fake, "rs-2")[0]["status"], "answered")  # the counterfactual
        out.write_text("not json")
        self.assertIn("printed no JSON", rsids.lookup(fake, "rs-2")[1])

    def test_without_a_cli_every_id_is_unchecked_and_nothing_found_about_it(self):
        out, unchecked, count = rsids.findings([("PLAN-r.md", plan("- rs-1 -- q", "- On rs-1."))], None)
        self.assertEqual((out, unchecked, count), ([], ["rs-1"], 2))


class LoneClone(Case):
    """No research dependency: ids cited are UNCHECKED, exit 3, and the ok line is
    never printed; a folder citing none still passes."""

    def test_ids_without_the_service_are_unchecked(self):
        lone = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, lone, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__", ".progress"))
        d = self.tmp / "plans"
        d.mkdir()
        f = d / "PLAN-r.md"
        f.write_text(plan("- Q1: before the service", "- Adopt it."))
        r = subprocess.run([str(lone / "setup"), "plans", str(d)], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        f.write_text(plan("- rs-1 -- a question", "- Adopt it (rs-1)."))
        r = subprocess.run([str(lone / "setup"), "plans", str(d)], capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        last = r.stdout.splitlines()[-1]
        self.assertTrue(last.startswith("  UNCHECKED  research: 1 id(s) cited (rs-1), none resolved: "), last)
        self.assertNotIn("  ok    ", r.stdout)
