"""The hooks component (PLAN-repo-setup §7.12): every file the hooks dependency's
listing names, from its source; absent installed, a header-only difference
refreshed, a logic difference drift and never overwritten; settings proposals."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from tests.helpers import ROOT, Case, git_repo, hook_source, workspace_cli

TOP, HOOKS_CLI = workspace_cli("hooks")
SOURCE = HOOKS_CLI.parent / "source" if HOOKS_CLI else None


def listing(source=SOURCE):
    """[(rel, source file)] the hooks dependency's own `list --json` names: what a
    repo must end up holding, from the dependency itself rather than from setup."""
    r = subprocess.run([str(HOOKS_CLI), "list", "--json", "--source", str(source)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = []
    for row in json.loads(r.stdout):
        out.append((f"{row['dest']}/{row['name']}", source / row["path"]))
        if row["test_installed"]:
            out.append((f"{row['dest']}/{Path(row['test']).name}", source / row["test"]))
    return out


class Hooks(Case):
    def setUp(self):
        super().setUp()
        if HOOKS_CLI is None:
            self.skipTest("lone clone: no hooks dependency to install from (tests.test_hooks.LoneClone covers it)")

    def test_default_source_is_the_dependency_not_this_tools_copies(self):
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r")
        self.assertIn(f"against {SOURCE}", res["hooks"]["detail"])
        self.assertNotIn(str(ROOT / ".claude"), res["hooks"]["detail"])
        want = listing()
        got = sorted(str(p.relative_to(repo)) for p in (repo / ".claude").rglob("*")
                     if p.is_file() and p.name not in ("settings.json", "settings.proposed.json"))
        self.assertEqual(got, sorted(rel for rel, _ in want))
        for rel, src in want:
            self.assertEqual((repo / rel).read_bytes(), src.read_bytes(), rel)
            # a hook or library has the mode the listing gives (the source's own); an
            # installed test is always executable, as ./dev.sh hooks requires of every .sh
            want_x = True if Path(rel).name.startswith("test-") else os.access(src, os.X_OK)
            self.assertEqual(os.access(repo / rel, os.X_OK), want_x, rel)

    def test_missing_copy_is_installed(self):
        repo = git_repo(self.tmp / "r")
        self.run_json("r")
        rel, src = listing()[0]
        (repo / rel).unlink()
        _, res = self.run_json("r")
        self.assertEqual(res["hooks"]["status"], "needs-jacob")  # the proposal; the copy itself installed
        self.assertIn("1 installed, 0 header refreshed", res["hooks"]["detail"])
        self.assertEqual((repo / rel).read_bytes(), src.read_bytes())

    def test_header_only_difference_is_refreshed(self):
        repo = git_repo(self.tmp / "r")
        self.run_json("r")
        rel, src = next((r, s) for r, s in listing() if r.endswith("/no-inline-blobs.sh"))
        mine = repo / rel
        mine.write_bytes(src.read_bytes().replace(b"\n", b"\n# an older header line\n\n", 1))
        _, res = self.run_json("r")
        self.assertNotIn(res["hooks"]["status"], ("drift", "failed"), res["hooks"]["detail"])
        self.assertIn("header refreshed", res["hooks"]["detail"])
        self.assertIn(rel, res["hooks"]["detail"])
        self.assertEqual(mine.read_bytes(), src.read_bytes())

    def test_header_refresh_writes_nothing_in_a_dry_run(self):
        repo = git_repo(self.tmp / "r")
        self.run_json("r")
        rel, src = listing()[0]
        old = src.read_bytes() + b"# a trailing comment\n"
        (repo / rel).write_bytes(old)
        _, res = self.run_json("r", "--dry-run")
        self.assertIn("header would refresh", res["hooks"]["detail"])
        self.assertEqual((repo / rel).read_bytes(), old)

    def test_differing_copy_is_drift_and_not_overwritten(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        mine = repo / ".claude/hooks/no-inline-blobs.sh"
        mine.write_text("#!/bin/sh\nlocal edit\n")
        code, res = self.run_json("r")
        self.assertEqual((code, res["hooks"]["status"]), (1, "drift"))
        self.assertIn(".claude/hooks/no-inline-blobs.sh: its logic differs", res["hooks"]["detail"])
        self.assertEqual(mine.read_text(), "#!/bin/sh\nlocal edit\n")

    def test_old_six_file_repo_gets_the_rest_installed(self):
        # The income bug: a repo holding the six files of the old source got
        # "0 installed, 6 unchanged of 6" because setup compared against its own
        # stale copy. Against the dependency, the files it lacks are installed.
        repo = git_repo(self.tmp / "r")
        want = listing()
        six = [(r, s) for r, s in want if r.startswith(".claude/hooks/")][:6]
        for rel, src in six:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, repo / rel)
        _, res = self.run_json("r", "--dry-run")
        detail = res["hooks"]["detail"]
        self.assertNotIn("of 6,", detail)
        self.assertIn(f"{len(want) - 6} installed, 0 header refreshed, 6 unchanged of {len(want)}", detail)

    def test_every_copy_agrees_with_the_dependency_by_its_own_check(self):
        # The comparison seam, from the other side: after setup, the hooks
        # dependency's own copies report finds every file of this location ok.
        top = self.tmp / "top"
        (top).mkdir()
        (top / "CLAUDE.md").write_text("x\n")
        repo = git_repo(top / "r")
        self.run_json(str(repo))
        r = subprocess.run([str(HOOKS_CLI), "copies", str(top), "--json", "--gate", "r"],
                           capture_output=True, text=True)
        doc = json.loads(r.stdout)
        rows = [f for loc in doc["locations"] if loc["path"] == "r" for f in loc["files"]]
        self.assertEqual({f["status"] for f in rows}, {"ok"}, [f for f in rows if f["status"] != "ok"])
        self.assertEqual(sorted(f["file"] for f in rows), sorted(rel for rel, _ in listing()))
        self.assertIs(doc["gate_ok"], True)

    def test_proposal_keeps_existing_settings(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude").mkdir()
        own = {"permissions": {"allow": ["Bash(ls:*)"]},
               "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
                   {"type": "command", "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/own.sh"}]}]}}
        (repo / ".claude/settings.json").write_text(json.dumps(own))
        _, res = self.run_json("r")
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        prop = json.loads((repo / ".claude/settings.proposed.json").read_text())
        self.assertEqual(prop["permissions"], own["permissions"])
        bash = [g for g in prop["hooks"]["PreToolUse"] if g["matcher"] == "Bash"]
        self.assertEqual(len(bash), 1)
        cmds = [h["command"].rsplit("/", 1)[1] for h in bash[0]["hooks"]]
        self.assertEqual(cmds[0], "own.sh")
        self.assertIn("no-inline-blobs.sh", cmds)
        # settings.json itself is Jacob's: untouched
        self.assertEqual(json.loads((repo / ".claude/settings.json").read_text()), own)

    def test_unparseable_settings_fail_and_propose_nothing(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude").mkdir()
        (repo / ".claude/settings.json").write_text("{not json")
        code, res = self.run_json("r")
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertFalse((repo / ".claude/settings.proposed.json").exists())

    def test_hooks_from_changes_what_is_installed(self):
        src = hook_source(self.tmp / "src", ["only-one.sh"])
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--hooks-from", str(src))
        self.assertEqual(sorted(p.name for p in (repo / ".claude/hooks").iterdir()),
                         ["only-one.sh", "test-only-one.sh"])
        prop = json.loads((repo / ".claude/settings.proposed.json").read_text())
        self.assertEqual(list(prop["hooks"]), ["Stop"])
        self.assertIn("2 installed", res["hooks"]["detail"])

    def test_detail_names_the_source_it_compared_against(self):
        # "unchanged" is only as true as the source: say which one, so a stale
        # source is visible rather than read as agreement with the real one
        src = hook_source(self.tmp / "src", ["only-one.sh"], settings="{}")
        git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--hooks-from", str(src))
        self.assertIn(f"against {src} (", res["hooks"]["detail"])
        self.assertIn("compared by meaning", res["hooks"]["detail"])

    def test_listing_fault_fails_and_installs_nothing(self):
        # a hook with no test is a fault of the dependency's listing: no guess at the rest
        src = hook_source(self.tmp / "src", ["a.sh"])
        (src / "hooks/test-a.sh").unlink()
        repo = git_repo(self.tmp / "r")
        code, res = self.run_json("r", "--hooks-from", str(src))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertFalse((repo / ".claude/hooks").exists())

    def test_empty_hook_source_fails(self):
        (self.tmp / "empty").mkdir()
        git_repo(self.tmp / "r")
        code, res = self.run_json("r", "--hooks-from", str(self.tmp / "empty"))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))


class LoneClone(Case):
    """This tool copied where no hooks dependency is above it: without --hooks-from the
    hooks line fails naming why; with it, DIR's hooks folder, compared byte for byte."""

    def setUp(self):
        super().setUp()
        self.tool = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, self.tool, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__"))
        git_repo(self.tool, commit=False)

    def run_lone(self, *args):
        r = subprocess.run([str(self.tool / "setup"), *args, "--json"], cwd=self.tmp, env=self.env,
                           capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return {x["component"]: x for x in json.loads(r.stdout)["results"]}

    def test_no_dependency_and_no_hooks_from_fails_naming_both(self):
        repo = git_repo(self.tmp / "r")
        res = self.run_lone(str(repo), "--dry-run")
        self.assertEqual(res["hooks"]["status"], "failed")
        self.assertIn("is not a git work tree above", res["hooks"]["detail"])
        self.assertIn("--hooks-from", res["hooks"]["detail"])

    def test_hooks_from_alone_compares_byte_for_byte(self):
        src = hook_source(self.tmp / "src", ["a.sh"])
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        (repo / ".claude/hooks/a.sh").write_bytes((src / "hooks/a.sh").read_bytes() + b"# comment\n")
        res = self.run_lone(str(repo), "--hooks-from", str(src))
        self.assertEqual(res["hooks"]["status"], "drift")
        self.assertIn("byte for byte", res["hooks"]["detail"])
        self.assertTrue((repo / ".claude/hooks/test-a.sh").exists())


class DevShHooks(Case):
    """./dev.sh hooks: a hook registered in settings.json is ok; one only in the
    settings proposal is PENDING (Jacob's to apply), never a silent pass; one in
    neither is FAIL. Run on a copy of dev.sh in a fixture folder."""

    def folder(self, settings, proposal=None):
        d = self.tmp / "f"
        (d / ".claude/hooks").mkdir(parents=True)
        shutil.copy2(ROOT / "dev.sh", d / "dev.sh")
        for n in ("x.sh", "test-x.sh"):
            (d / ".claude/hooks" / n).write_text("#!/bin/sh\nexit 0\n")
            (d / ".claude/hooks" / n).chmod(0o755)
        reg = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                              "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/x.sh"}]}]}}
        (d / ".claude/settings.json").write_text(json.dumps(reg if settings else {"hooks": {}}))
        if proposal:
            (d / ".claude/settings.proposed.json").write_text(json.dumps(reg))
        r = subprocess.run(["./dev.sh", "hooks"], cwd=d, capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_registered_is_ok(self):
        code, out = self.folder(settings=True)
        self.assertEqual(code, 0, out)
        self.assertNotIn("PENDING x.sh", out)
        self.assertIn("(0 of them only in the proposal", out)

    def test_only_in_the_proposal_is_pending_and_said(self):
        code, out = self.folder(settings=False, proposal=True)
        self.assertEqual(code, 0, out)
        self.assertIn("PENDING x.sh is registered only in .claude/settings.proposed.json", out)
        self.assertIn("1 of them only in the proposal", out)

    def test_in_neither_fails(self):
        code, out = self.folder(settings=False)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL  x.sh is not registered", out)


class Listing(Case):
    """What setup takes from the dependency's listing, and what it refuses."""

    def test_a_row_outside_the_source_refuses_the_listing(self):
        from setuplib.core import _listing_files
        src = self.tmp / "src"
        (src / "hooks").mkdir(parents=True)
        (self.tmp / "outside.sh").write_text("exit 0\n")
        row = {"name": "x.sh", "path": "../outside.sh", "applies_to": "all", "dest": ".claude/hooks",
               "registered": True, "executable": True, "test": None, "test_installed": False}
        files, why = _listing_files([row], src)
        self.assertIsNone(files)
        self.assertIn("is not a file inside", why)
        row["path"] = "hooks/x.sh"
        (src / "hooks/x.sh").write_text("exit 0\n")
        files, why = _listing_files([row], src)  # the same row inside: accepted
        self.assertIsNone(why)

    def test_a_comparator_that_does_not_load_fails_the_line(self):
        if HOOKS_CLI is None:
            self.skipTest("lone clone: no listing, so byte for byte is the stated rule")
        from unittest import mock
        from setuplib import core
        repo = git_repo(self.tmp / "r")
        s = core.Setup(repo, label="r", name="r", dry_run=True, dir_base=self.tmp)
        with mock.patch.object(core.deps, "comparator", return_value=(None, "planted: did not load")):
            res = s.c_hooks()
        self.assertEqual(res.status, "failed")
        self.assertIn("planted: did not load", res.detail)
        self.assertFalse((repo / ".claude").exists())
