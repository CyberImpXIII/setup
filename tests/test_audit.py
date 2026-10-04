"""The content-agnostic audit (PLAN-repo-setup §3) and the direction audit, each on a
planted workspace, so both are shown able to fail and not only to pass."""
import json
import shutil
import subprocess

from setuplib import audit
from tests.helpers import ROOT, Case, git_repo


class Content(Case):
    def workspace(self):
        """ws/tools/tool (the tool under audit), ws/alpha-repo (a sibling repo with a
        command), ws/scripts (a sibling whose name is a plain word)."""
        ws = self.tmp / "ws"
        tool = ws / "tools" / "tool"
        (tool / "setuplib").mkdir(parents=True)
        (tool / "setup").write_text("clean\n")
        alpha = git_repo(ws / "alpha-repo")
        (alpha / "runme").write_text("#!/bin/sh\n")
        (alpha / "runme").chmod(0o755)
        (alpha / "dev.sh").write_text("#!/bin/sh\n")
        (alpha / "dev.sh").chmod(0o755)
        git_repo(ws / "scripts")
        git_repo(ws / "tools" / "nested-one")
        return tool

    def plant(self, tool, text):
        (tool / "setuplib" / "x.py").write_text(text + "\n")
        return audit.audit_content(tool)

    def test_clean_tool_passes_and_counts_what_it_found(self):
        tool = self.workspace()
        findings, note = self.plant(tool, "# nothing to see; dev.sh is a contract name; scripts are fine")
        self.assertEqual(findings, [])
        self.assertIn("3 discovered repos", note)

    def test_each_kind_of_name_is_caught(self):
        tool = self.workspace()
        cases = {
            "x = 'alpha-repo'": "repo name alpha-repo",
            "run('./runme')": "repo command runme",
            "see `runme`": "repo command runme",
            "path = 'scripts/x.py'": "repo name scripts",
            "dir = 'tools/nested-one'": "repo path tools/nested-one",
        }
        for text, label in cases.items():
            with self.subTest(text=text):
                findings, _ = self.plant(tool, text)
                self.assertTrue(any(f.endswith(label) for f in findings), findings)

    def test_a_plain_name_under_a_contract_folder_is_not_the_sibling(self):
        # a sibling repo named `hooks` beside every repo's own `.claude/hooks/`
        tool = self.workspace()
        git_repo(tool.parent / "hooks")
        for text in ["p = '.claude/hooks/x.sh'", r"rx = r'\.claude/hooks/([^/]+)'", "for h in .claude/hooks"]:
            with self.subTest(text=text):
                findings, _ = self.plant(tool, text)
                self.assertEqual(findings, [])
        for text in ["p = 'hooks/x.sh'", "p = '../hooks'", "see `hooks`"]:
            with self.subTest(text=text):
                findings, _ = self.plant(tool, text)
                self.assertTrue(any(f.endswith("repo name hooks") for f in findings), findings)

    def test_templates_are_in_scope(self):
        tool = self.workspace()
        (tool / "templates").mkdir()
        (tool / "templates" / "t.md").write_text("cd alpha-repo\n")
        findings, _ = audit.audit_content(tool)
        self.assertTrue(any("templates/t.md:1: repo name alpha-repo" in f for f in findings), findings)

    def test_the_cli_audits_this_tools_own_files(self):
        """End to end: a copy of this tool beside a sibling repo is clean, and a
        sibling's name planted in its components.json turns `setup audit content` red."""
        ws = self.tmp / "ws"
        copy = ws / "tools" / "tool"
        shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__"))
        git_repo(ws / "alpha-repo")
        r = subprocess.run([str(copy / "setup"), "audit", "content"], cwd=copy, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("1 discovered repos", r.stdout)
        spec = copy / "components.json"
        spec.write_text(spec.read_text().replace('"file": "TODO.md"', '"file": "../alpha-repo/TODO.md"'))
        r = subprocess.run([str(copy / "setup"), "audit", "content"], cwd=copy, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("components.json", r.stdout)
        self.assertIn("repo name alpha-repo", r.stdout)

    def test_nothing_discovered_is_unchecked_not_a_pass(self):
        tool = self.tmp / "lonely" / "tools" / "tool"
        tool.mkdir(parents=True)
        findings, note = audit.audit_content(tool)
        self.assertEqual(findings, [])
        self.assertTrue(note.startswith("UNCHECKED"), note)


class Direction(Case):
    def tool(self, planted):
        tool = self.tmp / "tool"
        (tool / "setuplib").mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "audit-terms.json", tool / "audit-terms.json")
        (tool / "setuplib" / "x.py").write_text(planted + "\n")
        return tool

    def test_each_term_kind_is_caught(self):
        terms = json.loads((ROOT / "audit-terms.json").read_text())
        self.assertTrue(terms["paths"] and terms["roster_names"])
        # a quoted name from each list, assembled so this file does not itself match
        planted = ["open('../" + ".claude/x')", "agents" + ".sh", "the " + terms["roster_names"][0] + " agent"]
        for text in planted:
            with self.subTest(text=text):
                findings, _ = audit.audit_direction(self.tool(text))
                self.assertTrue(findings, text)

    def test_allowed_phrase_is_not_a_finding(self):
        findings, _ = audit.audit_direction(self.tool("status = 'needs-' + c['needs']  # prints needs harness"))
        self.assertEqual(findings, [])

    def test_tests_are_in_scope(self):
        tool = self.tool("clean")
        (tool / "tests").mkdir()
        (tool / "tests" / "test_x.py").write_text("p = 'wiring" + ".json'\n")
        findings, _ = audit.audit_direction(tool)
        self.assertTrue(any("tests/test_x.py:1" in f for f in findings), findings)

    def test_empty_term_file_fails_rather_than_passing_everything(self):
        tool = self.tool("clean")
        (tool / "audit-terms.json").write_text(json.dumps({"paths": [], "roster_names": [], "allowed_phrases": []}))
        findings, _ = audit.audit_direction(tool)
        self.assertTrue(findings)


class Plans(Case):
    def folder(self, plans):
        d = self.tmp / "plans"
        d.mkdir()
        for name, text in plans.items():
            (d / name).write_text(text)
        return d

    def test_plan_without_heading_fails_by_name(self):
        d = self.folder({"PLAN-a.md": "# A\n**Status: draft**\n## 1. Setup component\nx\n",
                         "PLAN-b.md": "# B\n**Status: approved**\n## 1. Something else\n",
                         "PLAN-c.md": "# C\n**Status: done** (2026-10-01)\n"})
        r = self.run_setup("plans", str(d))
        self.assertEqual(r.returncode, 1)
        self.assertIn("PLAN-b.md: status approved, no 'Setup component' heading", r.stdout)
        self.assertNotIn("PLAN-a.md", r.stdout)
        self.assertNotIn("PLAN-c.md", r.stdout)

    def test_heading_shapes_accepted(self):
        for h in ("## Setup component", "### 1b. Setup component", "## 12 Setup component"):
            with self.subTest(h=h):
                findings, _ = audit.audit_plans(self._one(h))
                self.assertEqual(findings, [])

    def _one(self, heading):
        d = self.tmp / f"p{len(list(self.tmp.iterdir()))}"
        d.mkdir()
        (d / "PLAN-x.md").write_text(f"# X\n{heading}\n")
        return d

    def test_a_mention_in_prose_is_not_a_heading(self):
        findings, _ = audit.audit_plans(self._one("This plan has no Setup component heading."))
        self.assertTrue(findings)

    def test_an_empty_folder_fails(self):
        d = self.folder({})
        r = self.run_setup("plans", str(d))
        self.assertEqual(r.returncode, 1)
