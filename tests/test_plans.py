"""`setup plans show <file> §<n>` (one numbered section, exactly), the per-section
status marker, and `setup plans` / `setup plans list` reading it (PLAN-todo-tool.md
§9 step 6). Planted plans only, so it runs anywhere."""
import hashlib
import re

from setuplib import plans
from tests.helpers import ROOT, Case

PLAN = """# PLAN-x.md: planted

> **Status: plan, planted.**

## 1. First

one

## 2. Second
<!-- status: approved -->

two

### 2.1 Inner

inner text

```
## 9. not a heading: fenced
```

## 2a. Lettered

lettered

### 7.12 Deep number

deep

## 3. Last
<!-- status: done -->

last


## Setup component

none
"""


class Show(Case):
    def plan(self, text=PLAN, name="PLAN-x.md"):
        d = self.tmp / "plans"
        d.mkdir(exist_ok=True)
        (d / name).write_text(text)
        return d / name

    def show(self, *args):
        return self.run_setup("plans", "show", *map(str, args))

    def test_prints_exactly_the_named_section_and_the_digest_on_stderr(self):
        p = self.plan()
        r = self.show(p, "§1")
        want = f"digest {hashlib.sha256(p.read_bytes()).hexdigest()}\n"
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "## 1. First\n\none\n", want))

    def test_the_digest_follows_the_file(self):
        p = self.plan()
        a = self.show(p, "§1").stderr
        p.write_text(PLAN.replace("last\n", "last, changed\n"))
        self.assertNotEqual(a, self.show(p, "§1").stderr)

    def test_a_different_section_gives_different_output(self):
        p = self.plan()
        one, two = self.show(p, "§1").stdout, self.show(p, "§2").stdout
        self.assertNotEqual(one, two)
        self.assertTrue(two.startswith("## 2. Second\n<!-- status: approved -->\n"))

    def test_a_section_holds_its_subsections_and_fenced_text_but_not_its_sibling(self):
        out = self.show(self.plan(), "§2").stdout
        self.assertIn("### 2.1 Inner\n\ninner text\n", out)
        self.assertIn("## 9. not a heading: fenced", out)
        self.assertNotIn("## 2a.", out)
        self.assertTrue(out.endswith("```\n"))

    def test_lettered_and_dotted_numbers_and_the_bare_form(self):
        p = self.plan()
        self.assertEqual(self.show(p, "§2a").stdout, "## 2a. Lettered\n\nlettered\n\n### 7.12 Deep number\n\ndeep\n")
        self.assertEqual(self.show(p, "§7.12").stdout, "### 7.12 Deep number\n\ndeep\n")
        self.assertEqual(self.show(p, "3").stdout, self.show(p, "§3").stdout)

    def test_the_last_section_ends_before_an_unnumbered_heading_of_its_level(self):
        self.assertEqual(self.show(self.plan(), "§3").stdout, "## 3. Last\n<!-- status: done -->\n\nlast\n")

    def test_a_missing_section_fails_saying_so(self):
        r = self.show(self.plan(), "§4")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertEqual(r.stderr, "plans show: PLAN-x.md: no section §4\n")

    def test_a_fenced_heading_is_not_a_section(self):
        r = self.show(self.plan(), "§9")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no section §9", r.stderr)

    def test_a_missing_file_fails_saying_so(self):
        r = self.show(self.tmp / "PLAN-absent.md", "§1")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertIn("PLAN-absent.md: cannot be read", r.stderr)

    def test_a_malformed_reference_fails_saying_so(self):
        r = self.show(self.plan(), "§one")
        self.assertEqual(r.returncode, 1)
        self.assertIn("not a section reference: '§one'", r.stderr)

    def test_an_ambiguous_number_fails_naming_the_lines(self):
        r = self.show(self.plan("# X\n## 1. A\n\n## 1. B\n"), "§1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("§1 is ambiguous: 2 headings carry it (lines 2, 4)", r.stderr)

    def test_wrong_arity_is_usage(self):
        r = self.show(self.plan())
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage: setup plans show <file> §<n>", r.stderr)


class Status(Case):
    def folder(self, text=PLAN):
        d = self.tmp / f"p{len(list(self.tmp.iterdir()))}"
        d.mkdir()
        (d / "PLAN-x.md").write_text(text)
        return d

    def test_statuses_are_read_from_the_marker_and_unstated_is_none(self):
        got = {s["number"]: s["status"] for s in plans.sections(PLAN)}
        self.assertEqual(got, {"1": None, "2": "approved", "2.1": None, "2a": None, "7.12": None, "3": "done"})

    def test_a_changed_status_changes_the_gate_output(self):
        a = self.run_setup("plans", str(self.folder())).stdout
        b = self.run_setup("plans", str(self.folder(PLAN.replace("status: done", "status: open")))).stdout
        self.assertIn("6 sections: 0 open, 1 approved, 1 done, 4 unstated", a)
        self.assertIn("6 sections: 1 open, 1 approved, 0 done, 4 unstated", b)
        self.assertEqual(a.splitlines()[-1].split()[0], "ok")

    def test_list_skips_done_sections_unless_asked(self):
        d = self.folder()
        live = self.run_setup("plans", "list", str(d))
        self.assertEqual(live.returncode, 0, live.stderr)
        self.assertEqual(live.stdout.splitlines(), [
            "PLAN-x.md §1 unstated  First",
            "PLAN-x.md §2 approved  Second",
            "PLAN-x.md §2.1 unstated  Inner",
            "PLAN-x.md §2a unstated  Lettered",
            "PLAN-x.md §7.12 unstated  Deep number",
        ])
        every = self.run_setup("plans", "list", str(d), "--all").stdout.splitlines()
        self.assertEqual(every[-1], "PLAN-x.md §3 done  Last")

    def test_list_skips_the_subsections_of_a_done_section(self):
        d = self.folder(PLAN.replace("## 2. Second\n<!-- status: approved -->", "## 2. Second\n<!-- status: done -->"))
        out = self.run_setup("plans", "list", str(d)).stdout
        self.assertNotIn("§2 ", out)
        self.assertNotIn("§2.1 ", out)
        self.assertIn("§2a ", out)

    def test_list_skips_a_done_plan_unless_asked(self):
        d = self.folder(PLAN.replace("**Status: plan, planted.**", "**Status: done**"))
        self.assertEqual(self.run_setup("plans", "list", str(d)).stdout, "")
        self.assertIn("§1 ", self.run_setup("plans", "list", str(d), "--all").stdout)

    def test_a_status_outside_the_vocabulary_fails_the_gate(self):
        r = self.run_setup("plans", str(self.folder(PLAN.replace("status: done", "status: finished"))))
        self.assertEqual(r.returncode, 1)
        self.assertIn("§3 status 'finished' is not one of open, approved, done", r.stdout)

    def test_a_misplaced_marker_fails_the_gate(self):
        r = self.run_setup("plans", str(self.folder(PLAN.replace("\none\n", "\none\n<!-- status: done -->\n"))))
        self.assertEqual(r.returncode, 1)
        self.assertIn("PLAN-x.md:8: a status marker not on the first line under a numbered heading", r.stdout)

    def test_a_marker_in_fenced_code_is_text(self):
        r = self.run_setup("plans", str(self.folder(PLAN.replace("## 9. not", "<!-- status: done -->\n## 9. not"))))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_a_duplicate_section_number_fails_the_gate(self):
        r = self.run_setup("plans", str(self.folder(PLAN.replace("## 2a. Lettered", "## 2. Lettered"))))
        self.assertEqual(r.returncode, 1)
        self.assertIn("PLAN-x.md: §2 is carried by 2 headings (lines 9, 22): a pointer to it cannot resolve", r.stdout)

    def test_help_names_exactly_the_statuses(self):
        r = self.run_setup("--help")
        m = re.search(r"<!-- status: ([a-z|]+) -->", r.stdout)
        self.assertIsNotNone(m, "the help does not show the status marker")
        self.assertEqual(tuple(m.group(1).split("|")), plans.STATUSES)

    def test_help_lists_exactly_the_plans_actions(self):
        src = (ROOT / "setup").read_text()
        actions = re.search(r"PLANS_USAGE = \{(.*?)\n\}", src, re.S).group(1)
        usages = re.findall(r'"[a-z]*": "(setup plans [^"]+)"', actions)
        listed = re.findall(r"^  (setup plans .*?)\s*$", self.run_setup("--help").stdout, re.M)
        listed = [re.split(r"\s{2,}", u)[0] for u in listed]  # the gate's line carries its summary
        self.assertEqual(sorted(listed), sorted(usages))


SECTION_2A = "## 2a. Lettered\n\nlettered\n\n### 7.12 Deep number\n\ndeep\n"


class Edit(Case):
    def setUp(self):
        super().setUp()
        self.dir = self.tmp / "plans"
        self.dir.mkdir()
        self.plan = self.dir / "PLAN-x.md"
        self.plan.write_text(PLAN)

    def digest(self):
        r = self.run_setup("plans", "show", str(self.plan), "§1")
        return r.stderr.split()[1]

    def edit(self, ref, body, *extra, digest=None):
        src = self.tmp / "new.md"
        src.write_text(body)
        return self.run_setup("plans", "edit", str(self.plan), ref, "--from", str(src),
                              "--digest", digest or self.digest(), *extra)

    def assertRefused(self, r, why, before=PLAN):
        self.assertEqual((r.returncode, r.stdout), (1, ""), r.stderr)
        self.assertIn("plans edit: refused, nothing written: ", r.stderr)
        self.assertIn(why, r.stderr)
        self.assertEqual(self.plan.read_text(), before)

    def test_replaces_the_section_and_keeps_every_other_byte(self):
        new = "## 2a. Lettered anew\n\nnew text\n\n\n"
        r = self.edit("§2a", new)
        self.assertEqual(r.returncode, 0, r.stderr)
        got = self.plan.read_bytes()
        self.assertEqual(got, PLAN.replace(SECTION_2A, "## 2a. Lettered anew\n\nnew text\n").encode())
        cut = PLAN.index(SECTION_2A)
        self.assertTrue(got.startswith(PLAN[:cut].encode()))
        self.assertTrue(got.endswith(PLAN[cut + len(SECTION_2A):].encode()))
        self.assertEqual(r.stdout, "plans edit: PLAN-x.md §2a replaced (lines 22-28 now 22-24); "
                                   f"digest {hashlib.sha256(got).hexdigest()}\n")
        self.assertEqual(self.run_setup("plans", "show", str(self.plan), "§2a").stdout,
                         "## 2a. Lettered anew\n\nnew text\n")

    def test_a_changed_status_is_an_edit_the_gate_reads(self):
        r = self.edit("§1", "## 1. First\n<!-- status: open -->\n\none\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("1 open, 1 approved, 1 done, 3 unstated", self.run_setup("plans", str(self.dir)).stdout)

    def test_crlf_line_ends_outside_the_section_are_kept(self):
        crlf = PLAN.replace("\n", "\r\n").encode()
        self.plan.write_bytes(crlf)
        r = self.edit("§2a", "## 2a. Lettered\n\nchanged\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        cut = crlf.index(b"## 2a.")
        after = crlf[crlf.index(b"deep\r\n") + len(b"deep\r\n"):]
        self.assertEqual(self.plan.read_bytes(), crlf[:cut] + b"## 2a. Lettered\n\nchanged\r\n" + after)

    def test_a_stale_digest_is_refused(self):
        d = self.digest()
        changed = PLAN.replace("\none\n", "\none, edited elsewhere\n")
        self.plan.write_text(changed)
        r = self.edit("§2a", "## 2a. Lettered\n\nmine\n", digest=d)
        self.assertRefused(r, "PLAN-x.md changed since digest", before=changed)

    def test_an_edit_that_would_turn_the_gate_red_is_refused(self):
        r = self.edit("§2", "## 2. Second\n<!-- status: approved -->\n\ntwo\n<!-- status: done -->\n")
        self.assertRefused(r, "would turn `setup plans")
        self.assertIn("a status marker not on the first line", r.stderr)
        r = self.edit("§1", "## 1. First\n<!-- status: finished -->\n")
        self.assertRefused(r, "status 'finished' is not one of open, approved, done")

    def test_an_edit_into_a_red_folder_is_refused(self):
        (self.dir / "PLAN-y.md").write_text("# PLAN-y\n\n## 1. Only\n")
        r = self.edit("§1", "## 1. First\n\nfine\n")
        self.assertRefused(r, "is already red (1 finding(s)), first: PLAN-y.md: status unstated, no 'Setup component' heading")

    def test_the_replacement_must_be_that_one_section(self):
        self.assertRefused(self.edit("§2a", "## 3. Last\n\nx\n"), "must start with the heading of §2a at its level")
        self.assertRefused(self.edit("§2a", "### 2a. Lettered\n\nx\n"), "must start with the heading of §2a at its level")
        self.assertRefused(self.edit("§1", "## 1. First\n\nx\n\n## 5. Smuggled\n"), "it would add a section")
        self.assertRefused(self.edit("§1", "## 1. First\n\n```\n## 5. hidden\n"), "opens a code fence it does not close")
        self.assertRefused(self.edit("§1", "\n\n"), "the replacement is empty")

    def test_a_missing_section_or_a_non_plan_is_refused(self):
        self.assertRefused(self.edit("§4", "## 4. New\n"), "PLAN-x.md: no section §4")
        other = self.dir / "notes.md"
        other.write_text(PLAN)
        src = self.tmp / "s.md"
        src.write_text("## 1. First\n")
        r = self.run_setup("plans", "edit", str(other), "§1", "--from", str(src), "--digest", "0" * 64)
        self.assertEqual(r.returncode, 1)
        self.assertIn("notes.md is not a plan (PLAN-*.md)", r.stderr)

    def test_dry_run_writes_nothing(self):
        d = self.digest()
        r = self.edit("§1", "## 1. First\n\nx\n", "--dry-run", digest=d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, f"plans edit: PLAN-x.md §1 would be replaced (lines 5-7 now 5-7); digest {d}\n")
        self.assertEqual(self.plan.read_text(), PLAN)

    def test_wrong_usage_is_exit_2(self):
        r = self.run_setup("plans", "edit", str(self.plan), "§1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage: setup plans edit <file> §<n> --from <src> --digest <sha256> [--dry-run]", r.stderr)
