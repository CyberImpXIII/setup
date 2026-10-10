"""--rebuild without --node (PLAN-repo-setup §7.12, Jacob's yes of 2026-10-05): a hook
copy whose logic drifted from the source is overwritten from it, in any repo, with a
line per file saying how it differed. The fixture pair: a repo holding a drifted copy,
committed; a plain run leaves it byte-unchanged and says drift, --rebuild rewrites it
and says so, and a second run is clean. Only a file the listing renders into a folder
directly under .claude/ (the hooks and their libraries), never settings.json or a repo's own .githooks/pre-commit, and refused (nothing
written) while a copy it would overwrite holds changes git does not have."""
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

from setuplib import core
from tests.helpers import ROOT, SETUP, Case, git, git_repo, hook_listing, hook_source, snapshot

LISTING = hook_listing()
SPEC = core.load_spec()
REBUILD = next(c for c in SPEC["components"] if c["name"] == "hooks")["rebuild"]


def commit_all(repo, msg):
    git(["add", "-A"], repo)
    r = git(["commit", "-q", "-m", msg], repo)
    assert r.returncode == 0, r.stderr + r.stdout


class Fixture(Case):
    """A repo setup did not create, holding the rendered copies, committed, then three
    copies changed the way other repos' copies drift (a logic edit, a header-only edit,
    one deleted) plus the owner's own settings.json and .githooks/pre-commit, committed."""

    def setUp(self):
        super().setUp()
        if LISTING is None:
            self.skipTest("lone clone: no hooks dependency (LoneClone below covers --hooks-from)")
        self.repo = git_repo(self.tmp / "r")
        self.doc("--only", "hooks")
        commit_all(self.repo, "copies")
        src = dict(LISTING)
        self.logic = next(r for r in src if r.endswith("/no-inline-blobs.sh"))
        # a library: a listed file outside the hooks' own folder
        self.header = next(r for r in src if Path(r).parent != Path(self.logic).parent)
        self.missing = next(r for r in src if Path(r).name.startswith("test-") and r != self.logic)
        self.src = src
        (self.repo / self.logic).write_bytes(src[self.logic].read_bytes() + b"echo drifted logic\n")
        (self.repo / self.header).write_bytes(
            src[self.header].read_bytes().replace(b"\n", b"\n# an older header line\n", 1))
        (self.repo / self.missing).unlink()
        self.own = {".claude/settings.json": '{"permissions": {"allow": ["Bash(ls:*)"]}}\n',
                    ".githooks/pre-commit": "#!/bin/sh\n# the owner's own gate\nexit 0\n"}
        for rel, text in self.own.items():
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text(text)
        commit_all(self.repo, "drifted, as found in the wild")
        self.drifted = (self.repo / self.logic).read_bytes()

    def doc(self, *args):
        r = self.run_setup("r", *args, "--json")
        self.assertIn(r.returncode, (0, 1), r.stderr)
        d = json.loads(r.stdout)
        return r.returncode, {x["component"]: x for x in d["results"]}, d["hook_files"]

    def line(self, lines, rel):
        got = [x for x in lines if x["path"] == rel]
        self.assertEqual(len(got), 1, lines)
        return got[0]["kind"], got[0]["action"]

    def assert_own_untouched(self):
        for rel, text in self.own.items():
            self.assertEqual((self.repo / rel).read_text(), text, rel)

    def test_plain_run_leaves_the_drifted_copy_and_says_drift(self):
        code, res, lines = self.doc()
        self.assertEqual((code, res["hooks"]["status"]), (1, "drift"))
        self.assertIn(f"{self.logic}: its logic differs", res["hooks"]["detail"])
        self.assertEqual((self.repo / self.logic).read_bytes(), self.drifted)
        self.assertEqual(self.line(lines, self.logic), ("logic", "kept"))
        self.assertEqual(self.line(lines, self.header), ("header-only", "refreshed"))
        self.assertEqual(self.line(lines, self.missing), ("missing", "installed"))
        self.assert_own_untouched()

    def test_rebuild_rewrites_it_reports_it_and_a_second_run_is_clean(self):
        code, res, lines = self.doc("--rebuild")
        self.assertNotIn(res["hooks"]["status"], ("drift", "failed"), res["hooks"]["detail"])
        self.assertIn(f"--rebuild rewrote from the source (the copy differed in logic or mode): {self.logic}",
                      res["hooks"]["detail"])
        self.assertEqual(self.line(lines, self.logic), ("logic", "rewritten"))
        self.assertEqual(self.line(lines, self.header), ("header-only", "refreshed"))
        self.assertEqual(self.line(lines, self.missing), ("missing", "installed"))
        self.assertEqual(len(lines), 3, lines)  # nothing else differed, nothing else reported
        for rel in (self.logic, self.header, self.missing):
            self.assertEqual((self.repo / rel).read_bytes(), self.src[rel].read_bytes(), rel)
        self.assert_own_untouched()  # settings.json and the repo's own pre-commit: never
        self.assertEqual(git(["log", "-1", "--format=%s"], self.repo).stdout.strip(),
                         "drifted, as found in the wild", "setup never commits in a repo it did not create")
        # the second run: plain, nothing differs, nothing reported, exit 0
        code, res, lines = self.doc("--only", "hooks")
        self.assertEqual((code, lines), (0, []))
        self.assertIn(f"0 installed, 0 header refreshed, {len(LISTING)} unchanged of {len(LISTING)}",
                      res["hooks"]["detail"])
        # and a second --rebuild before the owner commits: the rewritten copies equal the
        # source, so nothing is lost and nothing refused
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_the_text_report_names_each_file_and_its_kind(self):
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"(?m)^    hooks rewritten\s+" + re.escape(self.logic) + r"  \(logic\)$")
        self.assertRegex(r.stdout, r"(?m)^    hooks refreshed\s+" + re.escape(self.header) + r"  \(header-only\)$")
        self.assertRegex(r.stdout, r"(?m)^    hooks installed\s+" + re.escape(self.missing) + r"  \(missing\)$")
        self.assertIn("(rebuild: drifted copies overwritten)", r.stdout)

    def test_uncommitted_changes_refuse_and_nothing_is_written(self):
        (self.repo / self.logic).write_bytes(self.drifted + b"echo the owner's uncommitted work\n")
        before = snapshot(self.repo)
        r = self.run_setup("r", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(self.logic, r.stderr)
        self.assertIn("--overwrite-uncommitted", r.stderr)
        self.assertNotIn(self.header, r.stderr)  # committed: not named
        self.assertEqual(snapshot(self.repo), before)
        r = self.run_setup("r", "--rebuild", "--dry-run")  # a dry run predicts the refusal
        self.assertEqual(r.returncode, 2, r.stdout)
        # told otherwise: overwritten
        code, res, lines = self.doc("--only", "hooks", "--rebuild", "--overwrite-uncommitted")
        self.assertEqual(self.line(lines, self.logic), ("logic", "rewritten"))
        self.assertEqual((self.repo / self.logic).read_bytes(), self.src[self.logic].read_bytes())

    def test_untracked_and_ignored_copies_count_as_uncommitted(self):
        git(["rm", "-q", "--cached", self.logic], self.repo)
        self.assertEqual(git(["commit", "-q", "-m", "untrack"], self.repo).returncode, 0)
        self.assertIn("?? " + self.logic, git(["status", "--porcelain"], self.repo).stdout)
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(self.logic, r.stderr)
        (self.repo / ".gitignore").write_text(self.logic + "\n")
        commit_all(self.repo, "ignore it")
        self.assertEqual(git(["check-ignore", self.logic], self.repo).returncode, 0)
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(self.logic, r.stderr)
        self.assertEqual((self.repo / self.logic).read_bytes(), self.drifted)

    def test_a_file_setup_does_not_render_never_blocks_and_is_kept(self):
        mine = self.repo / ".claude/hooks/mine.sh"
        mine.write_text("#!/bin/sh\n# the owner's, uncommitted\n")
        code, res, lines = self.doc("--only", "hooks", "--rebuild")
        self.assertEqual(code, 0, res["hooks"]["detail"])
        self.assertEqual(mine.read_text(), "#!/bin/sh\n# the owner's, uncommitted\n")
        self.assertNotIn(".claude/hooks/mine.sh", [x["path"] for x in lines])

    def test_rebuild_dry_run_writes_nothing_and_says_so(self):
        before = snapshot(self.repo)
        code, res, lines = self.doc("--rebuild", "--dry-run")
        self.assertEqual(snapshot(self.repo), before)
        self.assertEqual(self.line(lines, self.logic), ("logic", "rewritten"))
        self.assertIn("--rebuild would rewrite", res["hooks"]["detail"])
        self.assertTrue(all(x["detail"] == "dry run, not written" for x in lines), lines)

    def test_a_mode_only_difference_is_kept_then_rewritten(self):
        (self.repo / self.logic).write_bytes(self.src[self.logic].read_bytes())
        (self.repo / self.logic).chmod(0o644)
        commit_all(self.repo, "not executable")
        code, res, lines = self.doc("--only", "hooks")
        self.assertEqual((code, self.line(lines, self.logic)), (1, ("mode", "kept")))
        code, res, lines = self.doc("--only", "hooks", "--rebuild")
        self.assertEqual(self.line(lines, self.logic), ("mode", "rewritten"))
        self.assertTrue((self.repo / self.logic).stat().st_mode & 0o100)

    def test_outside_the_scope_a_drifted_copy_is_kept_under_rebuild(self):
        # the scope is data: with its root moved elsewhere, the drifted hook is kept
        spec = copy.deepcopy(SPEC)
        hooks = next(c for c in spec["components"] if c["name"] == "hooks")
        hooks["rebuild"]["scope_root"] = "elsewhere"
        s = core.Setup(self.repo, label="r", name="r", dry_run=False, dir_base=self.tmp, spec=spec,
                       hooks_rebuild=True)
        s.is_new = False
        res = s.c_hooks()
        why = "outside the --rebuild scope (a folder directly under elsewhere/): drift, byte-unchanged"
        self.assertEqual(res.status, "drift", res.detail)
        self.assertIn(why, res.detail)
        self.assertEqual((self.repo / self.logic).read_bytes(), self.drifted)
        self.assertIn({"path": self.logic, "kind": "logic", "action": "kept", "detail": why}, s.hook_lines)


class Scope(Case):
    def test_only_a_folder_directly_under_the_root(self):
        root = REBUILD["scope_root"]
        self.assertEqual(root, ".claude")
        for rel in (".claude/hooks/x.sh", ".claude/any/y.sh", ".claude/hooks/test-x.sh"):
            self.assertTrue(core._in_scope(rel, root), rel)
        for rel in (".claude/settings.json", ".claude/settings.proposed.json", ".githooks/pre-commit",
                    ".claude/hooks/sub/a.sh", "hooks/x.sh", "dev.sh", "x/.claude/hooks/a.sh"):
            self.assertFalse(core._in_scope(rel, root), rel)

    def test_every_file_the_listing_renders_is_in_scope(self):
        # the seam: a destination the hooks tool adds outside the scope would leave its
        # drifted copies un-rebuildable while --rebuild looked done
        if LISTING is None:
            self.skipTest("lone clone: no hooks dependency to list")
        out = [rel for rel in dict(LISTING) if not core._in_scope(rel, REBUILD["scope_root"])]
        self.assertEqual(out, [])


class Usage(Case):
    def test_flags_that_mean_nothing_are_usage_errors(self):
        git_repo(self.tmp / "r")
        for args in (["--overwrite-uncommitted"], ["--node", "--rebuild", "--overwrite-uncommitted"],
                     ["--rebuild", "--only", "todo"]):
            self.assertEqual(self.run_setup("r", *args).returncode, 2, args)


class Vocabulary(Case):
    """The kinds and actions components.json declares are exactly the ones core.py
    emits, both ways, and `setup components` and --help show them."""

    def test_declared_equals_emitted(self):
        src = (ROOT / "setuplib" / "core.py").read_text()
        kinds = set(re.findall(r'\bkind = "([a-z-]+)"', src))
        actions = set(re.findall(r'\baction = "([a-z-]+)"', src))
        self.assertEqual(re.findall(r"_hook_line\(rel, (\S+?), (\S+?),", src), [("kind", "action")] * 4,
                         "every per-file line is emitted from the two variables this test reads")
        self.assertEqual(kinds, set(REBUILD["kinds"]))
        self.assertEqual(actions, set(REBUILD["actions"]))

    def test_components_and_help_show_it(self):
        out = self.run_setup("components").stdout
        for k in [*REBUILD["kinds"], *REBUILD["actions"]]:
            self.assertRegex(out, r"(?m)^    " + re.escape(k) + r"\s")
        helptext = subprocess.run([str(SETUP), "--help"], capture_output=True, text=True).stdout
        self.assertIn("setup <repo> --only hooks --rebuild", helptext)
        self.assertIn("--overwrite-uncommitted", helptext)


class LoneClone(Case):
    """Without the hooks dependency (--hooks-from DIR, byte for byte) a differing copy
    is kind `bytes`: kept by a plain run, rewritten by --rebuild."""

    def test_bytes_kind_kept_then_rewritten(self):
        tool = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, tool, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__"))
        git_repo(tool, commit=False)
        src = hook_source(self.tmp / "src", ["a.sh"])
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        for n in ("a.sh", "test-a.sh"):
            shutil.copy2(src / "hooks" / n, repo / ".claude/hooks" / n)
        (repo / ".claude/hooks/a.sh").write_bytes((src / "hooks/a.sh").read_bytes() + b"echo mine\n")
        commit_all(repo, "drifted")

        def run(*args):
            r = subprocess.run([str(tool / "setup"), str(repo), "--only", "hooks", "--hooks-from", str(src),
                                *args, "--json"], cwd=self.tmp, env=self.env, capture_output=True, text=True)
            self.assertIn(r.returncode, (0, 1), r.stderr)
            return [(x["path"], x["kind"], x["action"]) for x in json.loads(r.stdout)["hook_files"]]

        self.assertEqual(run(), [(".claude/hooks/a.sh", "bytes", "kept")])
        self.assertEqual(run("--rebuild"), [(".claude/hooks/a.sh", "bytes", "rewritten")])
        self.assertEqual((repo / ".claude/hooks/a.sh").read_bytes(), (src / "hooks/a.sh").read_bytes())
        self.assertEqual(run(), [])
