"""The parts component (PLAN-small-tasks §7 step 2): the shared suite runner, the
checks dependency's `runner` (dependencies.json), rendered byte for byte into each
repo at components.json parts.file, and compared with its source by meaning
(setuplib/pymeaning.py: the syntax tree, docstrings included). The fixture pairs:
absent then present; a comment-only edit (refreshed) against a code or docstring
edit (drift, kept); a plain run (kept) against --rebuild (rewritten); committed
(rewritten) against uncommitted (refused). Live where the dependency resolves;
the lone clone is its own case. This repo's own copy agreeing with the source is
held here too (the copies-agree check: drift is a red test)."""
import json
import shutil
import subprocess

from setuplib import audit, core, deps, pymeaning
from tests.helpers import ROOT, Case, git, git_repo, hook_listing, snapshot

SPEC = core.load_spec()
PARTS = next(c for c in SPEC["components"] if c["name"] == "parts")
REL = PARTS["file"]


def runner_source():
    """(source file, dependency folder), or (None, None) in a lone clone."""
    d, why = deps.load()
    if why:
        return None, None
    where, _ = deps.resolve(PARTS["dependency"], deps=d)
    if where is None:
        return None, None
    src, why = deps.runner(PARTS["dependency"], where, d)
    if why:
        raise AssertionError(f"the dependency resolves but its runner does not: {why}")
    return src, where


SRC, WHERE = runner_source()


def commit_all(repo, msg):
    git(["add", "-A"], repo)
    r = git(["commit", "-q", "-m", msg], repo)
    assert r.returncode == 0, r.stderr + r.stdout


class Live(Case):
    def setUp(self):
        super().setUp()
        if SRC is None:
            self.skipTest("lone clone: no checks dependency (LoneClone below covers it)")
        self.repo = git_repo(self.tmp / "r")
        self.body = SRC.read_bytes()

    def parts(self, *args):
        r = self.run_setup("r", "--only", "parts", *args, "--json")
        self.assertIn(r.returncode, (0, 1), r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual([x["component"] for x in doc["results"]], ["parts"])
        return r.returncode, doc["results"][0]

    def snap(self):
        """snapshot of the repo but .git/index: the guard's `git status` may rewrite the
        index's stat cache (a file written in the same second as the index is racily
        clean), which is git's bookkeeping, not a write of setup's. Every other byte,
        the rest of .git included, counts."""
        s = snapshot(self.repo)
        s.pop(".git/index", None)
        return s

    def plant(self, data, commit=True):
        """A copy at the destination holding data, committed (or not)."""
        f = self.repo / REL
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        if commit:
            commit_all(self.repo, "a copy, as found")
        return f

    def test_absent_is_installed_byte_for_byte_then_unchanged(self):
        before = self.snap()
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertEqual((self.repo / REL).read_bytes(), self.body)
        self.assertIn(pymeaning.version(SRC), res["detail"])
        changed = {p for p in set(snapshot(self.repo)) ^ set(before) if not p.startswith(".git/")}
        self.assertEqual(changed, {REL, REL.rsplit("/", 1)[0] + "/"})  # the file and its folder, nothing else
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (0, "unchanged"), res["detail"])

    def test_the_copy_runs_alone(self):
        # the runner imports nothing from beside it: a copy answers its own version
        self.parts()
        r = subprocess.run(["python3", "-I", str(self.repo / REL), "version"], capture_output=True, text=True,
                           cwd=self.repo)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, pymeaning.version(SRC)), r.stderr)

    def test_a_comment_only_difference_is_refreshed(self):
        f = self.plant(self.body.replace(b"\n", b"\n# an older header line\n", 1))
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertIn("header refreshed", res["detail"])
        self.assertEqual(f.read_bytes(), self.body)

    def test_a_code_difference_is_drift_reported_and_kept(self):
        drifted = self.body + b"\nDRIFTED = 1\n"
        f = self.plant(drifted)
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (1, "drift"), res["detail"])
        self.assertIn(f"{REL}: its meaning differs from the source", res["detail"])
        self.assertIn("`--rebuild` overwrites it", res["detail"])
        self.assertEqual(f.read_bytes(), drifted)

    def test_a_docstring_difference_is_drift(self):
        # the runner's usage is its docstring: an edit there is behaviour, not a header
        doc = b'"""parts.py -- '
        self.assertIn(doc, self.body)
        f = self.plant(self.body.replace(doc, b'"""parts.py (an old copy) -- ', 1))
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (1, "drift"), res["detail"])
        self.assertNotEqual(f.read_bytes(), self.body)

    def test_an_older_version_is_named_in_the_drift_line(self):
        v = pymeaning.version(SRC)
        self.plant(self.body.replace(f'VERSION = "{v}"'.encode(), b'VERSION = "0.0.1"', 1))
        code, res = self.parts()
        self.assertEqual(res["status"], "drift", res["detail"])
        self.assertIn("copy 0.0.1", res["detail"])

    def test_rebuild_rewrites_drift_and_never_commits(self):
        f = self.plant(self.body + b"\nDRIFTED = 1\n")
        code, res = self.parts("--rebuild")
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertIn("--rebuild rewrote", res["detail"])
        self.assertEqual(f.read_bytes(), self.body)
        self.assertEqual(git(["log", "-1", "--format=%s"], self.repo).stdout.strip(), "a copy, as found")
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (0, "unchanged"))

    def test_rebuild_dry_run_writes_nothing(self):
        self.plant(self.body + b"\nDRIFTED = 1\n")
        before = self.snap()
        code, res = self.parts("--rebuild", "--dry-run")
        self.assertIn("dry run, not written", res["detail"])
        self.assertEqual(self.snap(), before)

    def test_rebuild_refuses_an_uncommitted_copy_and_writes_nothing(self):
        self.plant(self.body + b"\nDRIFTED = 1\n")
        f = self.plant(self.body + b"\nDRIFTED = 2\n", commit=False)
        before = self.snap()
        r = self.run_setup("r", "--only", "parts", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(REL, r.stderr)
        self.assertEqual(self.snap(), before)
        r = self.run_setup("r", "--rebuild")  # the full run reads it too
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(REL, r.stderr)
        code, res = self.parts("--rebuild", "--overwrite-uncommitted")
        self.assertEqual(res["status"], "installed", res["detail"])
        self.assertEqual(f.read_bytes(), self.body)

    def test_an_untracked_copy_counts_as_uncommitted(self):
        self.plant(self.body + b"\nDRIFTED = 1\n", commit=False)
        r = self.run_setup("r", "--only", "parts", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_a_folder_in_its_place_is_drift_and_kept(self):
        (self.repo / REL).mkdir(parents=True)
        code, res = self.parts()
        self.assertEqual((code, res["status"]), (1, "drift"), res["detail"])
        self.assertTrue((self.repo / REL).is_dir())

    def test_the_source_repo_gets_no_copy(self):
        before = snapshot(WHERE / REL.rsplit("/", 1)[0])
        r = self.run_setup(str(WHERE), "--only", "parts", "--dry-run", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        res = json.loads(r.stdout)["results"][0]
        self.assertEqual(res["status"], "none", res["detail"])
        self.assertIn("runner's source", res["detail"])
        self.assertEqual(snapshot(WHERE / REL.rsplit("/", 1)[0]), before)


class OnlyAndTheGuard(Case):
    """--rebuild reads only what this run renders: a dirty hook copy blocks --only
    hooks, never --only parts; a dirty runner copy blocks --only parts, never --only hooks."""

    def setUp(self):
        super().setUp()
        if SRC is None or hook_listing() is None:
            self.skipTest("lone clone: no dependencies")
        self.repo = git_repo(self.tmp / "r")
        self.assertEqual(self.run_setup("r", "--only", "hooks").returncode, 0)
        self.assertEqual(self.run_setup("r", "--only", "parts").returncode, 0)
        commit_all(self.repo, "copies")
        self.hook = next(rel for rel, _ in hook_listing() if rel.endswith("/no-inline-blobs.sh"))

    def test_a_dirty_hook_copy_blocks_only_the_hooks(self):
        (self.repo / self.hook).write_text("#!/bin/sh\necho the owner's uncommitted work\n")
        (self.repo / REL).write_bytes(SRC.read_bytes() + b"\nDRIFTED = 1\n")
        commit_all(self.repo, "runner drifted, committed")
        (self.repo / self.hook).write_text("#!/bin/sh\necho more uncommitted work\n")
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(self.hook, r.stderr)
        r = self.run_setup("r", "--only", "parts", "--rebuild")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.repo / REL).read_bytes(), SRC.read_bytes())
        self.assertEqual((self.repo / self.hook).read_text(), "#!/bin/sh\necho more uncommitted work\n")

    def test_a_dirty_runner_copy_blocks_only_the_runner(self):
        (self.repo / REL).write_bytes(SRC.read_bytes() + b"\nDRIFTED = 1\n")
        r = self.run_setup("r", "--only", "parts", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_rebuild_with_another_component_is_a_usage_error(self):
        r = self.run_setup("r", "--only", "todo", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)


class LoneClone(Case):
    def test_without_the_dependency_it_fails_and_writes_nothing(self):
        lone = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, lone, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__"))
        repo = git_repo(self.tmp / "r")
        before = snapshot(repo)
        r = subprocess.run([str(lone / "setup"), "r", "--only", "parts", "--json"], cwd=self.tmp,
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stderr)
        res = json.loads(r.stdout)["results"][0]
        self.assertEqual(res["status"], "failed", res["detail"])
        self.assertIn("no runner to render", res["detail"])
        self.assertEqual(snapshot(repo), before)


class ThisRepo(Case):
    def test_this_repos_copy_agrees_with_the_source(self):
        # the copies-agree check for this repo: a runner changed in its source and
        # not re-rendered here is red, by bytes (a header refresh is a re-render too)
        if SRC is None:
            self.skipTest("lone clone: no source to agree with")
        mine = ROOT / REL
        self.assertTrue(mine.is_file(), f"{REL} missing: run ./setup . --only parts")
        self.assertEqual(pymeaning.meaning(mine), pymeaning.meaning(SRC),
                         f"{REL} differs from {SRC} by meaning: ./setup . --only parts --rebuild")
        self.assertEqual(mine.read_bytes(), SRC.read_bytes(), f"{REL}: header differs: ./setup . --only parts")

    def test_the_audits_skip_the_copy_and_read_the_rest(self):
        files = audit.code_files(ROOT)
        self.assertNotIn(ROOT / REL, files)
        self.assertIn(ROOT / "devtools" / "mutate.py", files)  # the counterfactual: its folder is still read
        bare = self.tmp / "bare"  # no components.json: nothing is exempted
        (bare / "devtools").mkdir(parents=True)
        (bare / REL).write_text("x = 1\n")
        self.assertIn(bare / REL, audit.code_files(bare))


class Meaning(Case):
    def write(self, name, text):
        f = self.tmp / name
        f.write_text(text)
        return f

    def test_comments_layout_and_shebang_aside(self):
        a = self.write("a.py", '#!/usr/bin/env python3\n"""Doc."""\nX = 1  # one\n')
        b = self.write("b.py", '"""Doc."""\n\n# a header\nX = (1)\n')
        self.assertEqual(pymeaning.meaning(a), pymeaning.meaning(b))

    def test_a_docstring_or_a_value_is_meaning(self):
        a = self.write("a.py", '"""Doc."""\nX = 1\n')
        self.assertNotEqual(pymeaning.meaning(a), pymeaning.meaning(self.write("b.py", '"""Other."""\nX = 1\n')))
        self.assertNotEqual(pymeaning.meaning(a), pymeaning.meaning(self.write("c.py", '"""Doc."""\nX = 2\n')))

    def test_unparsable_or_missing_is_none_never_equal(self):
        self.assertIsNone(pymeaning.meaning(self.write("bad.py", "def (:\n")))
        self.assertIsNone(pymeaning.meaning(self.tmp / "absent.py"))

    def test_version_is_the_one_literal_or_none(self):
        self.assertEqual(pymeaning.version(self.write("a.py", 'VERSION = "1.2.3"\n')), "1.2.3")
        self.assertIsNone(pymeaning.version(self.write("b.py", 'VERSION = "1"\nVERSION = "2"\n')))
        self.assertIsNone(pymeaning.version(self.write("c.py", "VERSION = compute()\n")))


class Runner(Case):
    def deps_with(self, runner):
        where = self.tmp / "dep"
        (where / "lib").mkdir(parents=True, exist_ok=True)
        return where, {"x": {"path": "dep", "cli": "x", "runner": runner}}

    def test_a_runner_outside_the_dependency_or_absent_is_refused(self):
        where, d = self.deps_with("lib/r.py")
        self.assertIsNone(deps.runner("x", where, d)[0])  # absent
        (where / "lib" / "r.py").write_text("x = 1\n")
        self.assertEqual(deps.runner("x", where, d)[0], (where / "lib" / "r.py").resolve())
        (self.tmp / "outside.py").write_text("x = 1\n")
        (where / "lib" / "link.py").symlink_to(self.tmp / "outside.py")
        where, d = self.deps_with("lib/link.py")
        p, why = deps.runner("x", where, d)
        self.assertIsNone(p)
        self.assertIn("refused", why)

    def test_load_refuses_a_runner_that_climbs_out(self):
        tool = self.tmp / "t"
        tool.mkdir()
        (tool / deps.DEPS_FILE).write_text(json.dumps({"dependencies": {"x": {"path": "a", "cli": "a",
                                                                              "runner": "../r.py"}}}))
        got, why = deps.load(tool)
        self.assertIsNone(got)
        self.assertIn("runner", why)
