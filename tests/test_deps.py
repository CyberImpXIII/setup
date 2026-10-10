"""dependencies.json (PLAN-repo-setup §7.12): the sibling tools setup installs FROM.
Documented == read, both directions; each one resolves to a discovered repo or the
audit is red (UNCHECKED with nothing discovered); exempt from the content audit and
from nothing else; the hooks component names a dependency that exists."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from setuplib import audit, core, deps
from tests.helpers import ROOT, Case, git_repo, workspace_cli

DOC = json.loads((ROOT / deps.DEPS_FILE).read_text())


def plant(top: Path, name, cli=True, source=True, executable=True, runner=True):
    """A sibling repo at top/tools/<name> with its CLI, source folder and (when
    dependencies.json declares one for it) its runner file (or not)."""
    repo = git_repo(top / "tools" / name, commit=False)
    declared = DOC["dependencies"].get(name, {}).get("runner")
    if runner and declared:
        (repo / declared).parent.mkdir(parents=True, exist_ok=True)
        (repo / declared).write_text("x = 1\n")
    if cli:
        (repo / name).write_text("#!/bin/sh\nexit 0\n")
        (repo / name).chmod(0o755 if executable else 0o644)
    if source:
        (repo / "source").mkdir()
    return repo


class Vocabulary(Case):
    def test_every_key_in_the_file_is_read_and_every_read_key_is_used(self):
        used = {k for d in DOC["dependencies"].values() for k in d if not k.startswith("_")}
        self.assertEqual(used, deps.KEYS)
        src = (ROOT / "setuplib" / "deps.py").read_text()
        for k in deps.KEYS:
            self.assertIn(f'["{k}"]' if k != "comparator" else '.get("comparator")', src, k)

    def test_the_hooks_component_names_a_dependency_with_a_source_and_comparator(self):
        hooks = next(c for c in core.load_spec()["components"] if c["name"] == "hooks")
        d = DOC["dependencies"][hooks["dependency"]]
        self.assertIn("source", d)
        self.assertIn("comparator", d)
        self.assertNotIn("source", hooks)  # no second default: the old one pointed at this tool's copies

    def test_components_subcommand_says_where_the_hooks_come_from(self):
        r = self.run_setup("components")
        line = next(l for l in r.stdout.splitlines() if l.startswith("  hooks "))
        for phrase in ("dependency lists", "dependencies.json", "--hooks-from DIR",
                       "header refreshed", "drift, never overwritten"):
            self.assertIn(phrase, line)

    def test_load_refuses_what_it_does_not_read(self):
        for bad in ({"x": {"path": "a", "cli": "a", "extra": 1}},
                    {"x": {"path": "/abs", "cli": "a"}},
                    {"x": {"path": "../up", "cli": "a"}},
                    {"x": {"path": "a", "cli": "a", "comparator": {"module": "m"}}},
                    {}):
            tool = self.tmp / "t"
            tool.mkdir(exist_ok=True)
            (tool / deps.DEPS_FILE).write_text(json.dumps({"dependencies": bad}))
            got, why = deps.load(tool)
            self.assertIsNone(got, bad)
            self.assertTrue(why, bad)


class Audit(Case):
    def tool_in(self, top):
        """This tool's dependencies.json, in a folder at top/tools/setup."""
        tool = top / "tools" / "setup"
        tool.mkdir(parents=True)
        shutil.copy(ROOT / deps.DEPS_FILE, tool / deps.DEPS_FILE)
        git_repo(tool, commit=False)
        return tool

    def run_audit(self, tool):
        return deps.audit(tool, list(audit.discover_repos(tool)))

    def test_every_dependency_present_is_ok(self):
        top = self.tmp / "ws"
        tool = self.tool_in(top)
        plant(top, "hooks")
        plant(top, "checks", source=False)
        findings, note = self.run_audit(tool)
        self.assertEqual(findings, [])
        self.assertIn("2 dependencies against", note)

    def test_a_missing_dependency_is_a_finding(self):
        top = self.tmp / "ws"
        tool = self.tool_in(top)
        plant(top, "hooks")
        plant(top, "other")  # something discovered, so the audit runs
        findings, _ = self.run_audit(tool)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("`checks`", findings[0])

    def test_a_cli_that_is_not_executable_and_a_missing_source_are_findings(self):
        top = self.tmp / "ws"
        tool = self.tool_in(top)
        plant(top, "hooks", source=False)
        plant(top, "checks", executable=False)
        findings, _ = self.run_audit(tool)
        self.assertEqual(len(findings), 2, findings)
        self.assertTrue(any("not a folder" in f for f in findings))
        self.assertTrue(any("not an executable file" in f for f in findings))

    def test_a_missing_runner_is_a_finding(self):
        top = self.tmp / "ws"
        tool = self.tool_in(top)
        plant(top, "hooks")
        plant(top, "checks", source=False, runner=False)
        findings, _ = self.run_audit(tool)
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("is not a file", findings[0])

    def test_nothing_discovered_is_unchecked_and_exits_3(self):
        lone = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, lone, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__"))
        r = subprocess.run([str(lone / "setup"), "audit", "deps"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("UNCHECKED", r.stdout)

    def test_the_real_workspace_resolves(self):
        if workspace_cli("hooks")[1] is None:
            self.skipTest("lone clone: test_nothing_discovered_is_unchecked_and_exits_3 covers it")
        r = subprocess.run([str(ROOT / "setup"), "audit", "deps"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ContentExemption(Case):
    def test_the_file_is_exempt_from_content_only(self):
        names = lambda files: {p.name for p in files}  # noqa: E731
        self.assertNotIn(deps.DEPS_FILE, names(audit.code_files(ROOT, exempt=audit.CONTENT_EXEMPT)))
        self.assertIn(deps.DEPS_FILE, names(audit.code_files(ROOT, extra_globs=["tests/*.py"])))

    def test_without_the_exemption_content_would_find_it(self):
        # counterfactual: the exemption is what keeps content green, not an absence of names
        repos = audit.discover_repos(ROOT)
        if not repos:
            self.skipTest("lone clone: no repos to name")
        hits = audit.scan([ROOT / deps.DEPS_FILE], audit.repo_terms(repos))
        self.assertTrue(hits)


class Comparator(Case):
    def setUp(self):
        super().setUp()
        self.d, why = deps.load()
        self.where, why = deps.resolve("hooks", deps=self.d)
        if self.where is None:
            self.skipTest(f"lone clone: {why}")

    def test_the_real_comparator_ignores_comments_and_sees_logic(self):
        fn, why = deps.comparator("hooks", self.where, self.d)
        self.assertIsNone(why)
        a, b, c = (self.tmp / n for n in "abc")
        a.write_text("#!/bin/sh\n# a header\nexit 0\n")
        b.write_text("#!/bin/sh\n# another header\n\nexit 0\n")
        c.write_text("#!/bin/sh\n# a header\nexit 1\n")
        self.assertEqual(fn(a), fn(b))
        self.assertNotEqual(fn(a), fn(c))

    def test_a_module_from_elsewhere_is_refused(self):
        # the name already resolves to the real dependency: a planted folder claiming
        # the same module is not where it came from, so it is refused, never used
        deps.comparator("hooks", self.where, self.d)
        fake = self.tmp / "fake"
        (fake / "hookslib").mkdir(parents=True)
        fn, why = deps.comparator("hooks", fake.resolve(), self.d)
        self.assertIsNone(fn)
        self.assertIn("refused", why)


class HooksLine(Case):
    def test_the_dependency_changes_what_is_compared(self):
        # the comparator is what makes a header-only copy `installed`, not `drift`:
        # without the dependency (a lone clone and --hooks-from) the same copy is drift
        if workspace_cli("hooks")[1] is None:
            self.skipTest("lone clone")
        from tests.helpers import hook_source
        src = hook_source(self.tmp / "src", ["a.sh"])
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        (repo / ".claude/hooks/a.sh").write_bytes((src / "hooks/a.sh").read_bytes() + b"# comment\n")
        _, res = self.run_json("r", "--hooks-from", str(src))
        self.assertIn("header refreshed", res["hooks"]["detail"])
        self.assertNotEqual(res["hooks"]["status"], "drift")
        self.assertEqual(os.access(repo / ".claude/hooks/a.sh", os.X_OK), True)
