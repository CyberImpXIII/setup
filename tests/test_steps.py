"""Plan steps (PLAN-services.md §3 G1, G5; §4 step 6.1): the one parser
(`setup plans steps <file> --json`), what each step's track tag resolves to
(`setup plans <dir> --steps`), the reverse check of step citations
(`--cited-in FILE`), and the plans gate that counts unplaceable steps without
failing on them (G2's failing rule is held). Planted plans only."""
import json
import sys

from setuplib import steps
from tests.helpers import ROOT, Case, git, git_repo

FAKE_TODO = ROOT / "tests" / "fake_todo.py"

PLAN = """# PLAN-p.md: planted

> **Status: plan, planted.**

## 1. Background

1. a numbered list outside a steps heading is not a step

## 2. Steps
<!-- status: approved -->

1. `alpha`: build the first thing
2. **`beta`:** build the second thing track: todo:beta#bt-7
3. nobody owns this one
4. Group step, placed through its children
   1. `alpha` and `beta`: the first child,
   wrapped lazily onto a second line
   2. a child with a tag track: TODO.md "Second child"
5. a step with two tags track: done x@abc1234 track: done x@abc1234
6. `alpha`: a tag off the table track: whenever

   continued after a blank line, still step 6 (indented to its text)

```
7. inside a fence: not a step
```

### 2.1 Phase one

1. a step under a nested heading track: needs-yes PLAN-p.md §1
2. replaced step track: superseded-by PLAN-p.md §9

## 3. Handoff to owners

1. done already track: done repo@{commit}
2. a vanished commit track: done repo@deadbee
3. store item still open track: todo:repo#td-1
4. store item closed track: todo:repo#td-2
5. store item the lookup cannot reach track: todo:repo#td-404

## Setup component

none
"""


class Parse(Case):
    def plan(self, text=None, name="PLAN-p.md", commit="abc1234"):
        d = self.tmp / "plans"
        d.mkdir(exist_ok=True)
        (d / name).write_text((text or PLAN).replace("{commit}", commit))
        return d / name

    def by_step(self, parsed):
        return {(s["section"], s["step"]): s for s in parsed}

    def test_grammar(self):
        got = self.by_step(steps.parse("PLAN-p.md", self.plan().read_text()))
        self.assertNotIn(("1", "1"), got, "a numbered list outside a steps heading is not a step")
        self.assertNotIn(("2", "7"), got, "a fenced numbered line is not a step")
        self.assertEqual(got[("2", "1")]["owners"], ["alpha"])
        self.assertIsNone(got[("2", "1")]["track"])
        self.assertTrue(got[("2", "1")]["placeable"])
        self.assertEqual(got[("2", "2")]["owners"], ["beta"])
        self.assertEqual(got[("2", "2")]["track"]["kind"], "todo")
        self.assertEqual(got[("2", "2")]["track"]["fields"], {"repo": "beta", "id": "bt-7"})
        self.assertFalse(got[("2", "3")]["placeable"])
        self.assertIn("no owner", got[("2", "3")]["why"])
        self.assertEqual(got[("2", "4")]["children"], ["4.1", "4.2"])
        self.assertTrue(got[("2", "4")]["placeable"], "a group is placed through its children")
        self.assertEqual(got[("2", "4.1")]["owners"], ["alpha", "beta"])
        self.assertEqual(got[("2", "4.1")]["parent"], "4")
        self.assertIn("wrapped lazily", got[("2", "4.1")]["text"])
        self.assertNotIn("first child", got[("2", "4")]["text"], "a group's own text leaves out its children's")
        self.assertEqual(got[("2", "4.2")]["track"]["kind"], "TODO.md")
        self.assertIn("2 track tags", got[("2", "5")]["why"])
        self.assertFalse(got[("2", "6")]["placeable"], "an owner does not excuse a tag off the table")
        self.assertIn("off G1's table", got[("2", "6")]["why"])
        self.assertIn("continued after a blank line", got[("2", "6")]["text"])
        self.assertEqual(got[("2.1", "1")]["track"]["kind"], "needs-yes")
        self.assertEqual(got[("2.1", "1")]["heading"], "2.1 Phase one")
        self.assertEqual(got[("3", "1")]["track"]["fields"]["commit"], "abc1234")
        self.assertEqual(got[("2", "1")]["line"], 12)

    def test_hash_ignores_the_tag_and_follows_the_text(self):
        a = steps.parse("PLAN-p.md", "## 1. Steps\n\n1. `x`: do it\n")[0]
        b = steps.parse("PLAN-p.md", "## 1. Steps\n\n1. `x`: do it track: todo:x#x-1\n")[0]
        c = steps.parse("PLAN-p.md", "## 1. Steps\n\n1. `x`: do it now\n")[0]
        self.assertEqual(a["hash"], b["hash"])
        self.assertNotEqual(a["hash"], c["hash"])

    def test_a_tag_inside_a_code_span_is_text(self):
        s = steps.parse("PLAN-p.md", "## 1. Steps\n\n1. `x`: write `track: done a@1234567` in the plan\n")[0]
        self.assertIsNone(s["track"])
        self.assertTrue(s["placeable"])

    def test_cli_json_is_the_parse(self):
        p = self.plan()
        r = self.run_setup("plans", "steps", str(p), "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), steps.parse("PLAN-p.md", p.read_text()))

    def test_cli_text_counts_and_input_changes_output(self):
        p = self.plan()
        r = self.run_setup("plans", "steps", str(p))
        self.assertEqual(r.returncode, 0, r.stderr)
        last = r.stdout.strip().splitlines()[-1]
        n = len(steps.parse("PLAN-p.md", p.read_text()))
        self.assertIn(f"{n} steps", last)
        p.write_text("# PLAN-p.md\n\n## 1. Steps\n\n1. `x`: one\n")
        self.assertIn("1 steps, 0 unplaceable", self.run_setup("plans", "steps", str(p)).stdout)

    def test_cli_refuses_an_unreadable_file(self):
        r = self.run_setup("plans", "steps", str(self.tmp / "PLAN-none.md"))
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, "")
        self.assertIn("plans steps:", r.stderr)


class Resolve(Case):
    def setUp(self):
        super().setUp()
        self.d = self.tmp / "plans"
        repo = git_repo(self.d / "repo")
        sha = git(["rev-parse", "--short", "HEAD"], repo).stdout.strip()
        (self.d / "PLAN-p.md").write_text(PLAN.replace("{commit}", sha))
        (self.d / "TODO.md").write_text("# TODO\n\n- **Second child** waits\n")
        # the fake store: td-1 open, td-2 closed, anything else not found
        (self.d / "repo" / "fake-store.json").write_text(json.dumps({"td-1": False, "td-2": True}))

    def report(self, *extra):
        r = self.run_setup("plans", str(self.d), "--steps", *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def lines(self, r):
        out = {}
        for line in r.stdout.splitlines()[:-1]:
            status, rest = line.split(None, 1)
            out[rest.split("  ")[0]] = status
        return out

    def test_every_status_with_the_store(self):
        got = self.lines(self.report("--todo", str(FAKE_TODO)))
        want = {
            "PLAN-p.md §2 step 1": "untracked", "PLAN-p.md §2 step 2": "unchecked",  # beta/ is no repo here
            "PLAN-p.md §2 step 3": "unplaceable", "PLAN-p.md §2 step 4": "group",
            "PLAN-p.md §2 step 4.1": "untracked", "PLAN-p.md §2 step 4.2": "open",
            "PLAN-p.md §2 step 5": "unplaceable", "PLAN-p.md §2 step 6": "unplaceable",
            "PLAN-p.md §2.1 step 1": "needs-yes", "PLAN-p.md §2.1 step 2": "dangling",
            "PLAN-p.md §3 step 1": "closed", "PLAN-p.md §3 step 2": "dangling",
            "PLAN-p.md §3 step 3": "open", "PLAN-p.md §3 step 4": "closed",
            "PLAN-p.md §3 step 5": "unchecked",
        }
        self.assertEqual(got, want)

    def test_without_a_store_cli_a_store_item_is_unchecked_never_guessed(self):
        got = self.lines(self.report())
        self.assertEqual(got["PLAN-p.md §3 step 3"], "unchecked")
        self.assertEqual(got["PLAN-p.md §3 step 4"], "unchecked")

    def test_summary_is_last_and_counts(self):
        r = self.report("--todo", str(FAKE_TODO))
        last = r.stdout.strip().splitlines()[-1]
        self.assertTrue(last.startswith("steps: 15 steps"), last)
        self.assertIn("3 unplaceable", last)
        self.assertIn("never a failure", last)

    def test_json(self):
        r = self.report("--todo", str(FAKE_TODO), "--json")
        doc = json.loads(r.stdout)
        st = {(s["section"], s["step"]): s["status"] for s in doc["steps"]}
        self.assertEqual(st[("3", "4")], "closed")
        self.assertEqual(doc["counts"]["unplaceable"], 3)

    def test_a_missing_todo_md_is_dangling(self):
        (self.d / "TODO.md").unlink()
        self.assertEqual(self.lines(self.report())["PLAN-p.md §2 step 4.2"], "dangling")

    def test_a_done_plan_is_skipped(self):
        text = (self.d / "PLAN-p.md").read_text().replace("**Status: plan, planted.**", "**Status: done.**")
        (self.d / "PLAN-p.md").write_text(text)
        r = self.report()
        self.assertTrue(r.stdout.strip().splitlines()[-1].startswith("steps: 0 steps"), r.stdout)


class Reverse(Case):
    def setUp(self):
        super().setUp()
        self.d = self.tmp / "plans"
        self.d.mkdir()
        (self.d / "PLAN-p.md").write_text(PLAN.replace("{commit}", "abc1234"))
        twice = "# PLAN-q.md\n\n## 1. Steps\n\n1. `x`: one\n\n### Phase two\n\n1. `x`: also one\n"
        (self.d / "PLAN-q.md").write_text(twice)

    def cited(self, text):
        f = self.tmp / "notes.md"
        f.write_text(text)
        r = self.run_setup("plans", str(self.d), "--steps", "--cited-in", str(f))
        self.assertEqual(r.returncode, 0, r.stderr)
        return [line for line in r.stdout.splitlines() if "notes.md:" in line]

    def test_a_citation_that_resolves_is_ok(self):
        got = self.cited("see PLAN-p.md §2 step 4.1 and PLAN-p.md §2.1, step 2\n")
        self.assertEqual(len(got), 2, got)
        self.assertTrue(all(line.split()[0] == "ok" for line in got), got)

    def test_a_step_cited_in_its_parent_section(self):
        got = self.cited("PLAN-p.md §2 step 1\n")
        self.assertEqual(got[0].split()[0], "ok")

    def test_a_missing_step_is_dangling(self):
        got = self.cited("PLAN-p.md §2 step 9\n")
        self.assertEqual(got[0].split()[0], "dangling")
        self.assertIn("no step 9", got[0])

    def test_a_missing_section_is_dangling(self):
        got = self.cited("PLAN-p.md §8\n")
        self.assertEqual(got[0].split()[0], "dangling")

    def test_a_missing_plan_is_dangling(self):
        got = self.cited("PLAN-gone.md §1\n")
        self.assertEqual(got[0].split()[0], "dangling")

    def test_a_step_two_lists_carry_is_ambiguous(self):
        got = self.cited("PLAN-q.md §1 step 1\n")
        self.assertEqual(got[0].split()[0], "ambiguous", got)

    def test_an_unreadable_cited_file_is_named(self):
        r = self.run_setup("plans", str(self.d), "--steps", "--cited-in", str(self.tmp / "none.md"))
        self.assertEqual(r.returncode, 2)
        self.assertIn("none.md", r.stderr)


class Gate(Case):
    def test_unplaceable_steps_are_counted_never_a_failure(self):
        d = self.tmp / "plans"
        d.mkdir()
        (d / "PLAN-p.md").write_text(PLAN.replace("{commit}", "abc1234"))
        r = self.run_setup("plans", str(d))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.strip().splitlines()
        self.assertTrue(lines[-1].startswith("  ok"), "the ok line stays last")
        note = [line for line in lines if "steps:" in line]
        self.assertEqual(len(note), 1, lines)
        self.assertIn("3 unplaceable", note[0])
        self.assertIn("PLAN-p.md §2 step 3", note[0])

    def test_no_step_no_note(self):
        d = self.tmp / "plans"
        d.mkdir()
        (d / "PLAN-p.md").write_text("# PLAN-p.md\n\n## Setup component\n\nnone\n")
        r = self.run_setup("plans", str(d))
        self.assertEqual(r.returncode, 0)
        self.assertIn("0 steps, 0 unplaceable", r.stdout)


if __name__ == "__main__":
    sys.exit("run with python3 -m unittest")
