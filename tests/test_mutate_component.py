"""The mutate component: the one mutant runner (this repo's devtools/mutate.py,
as its HEAD holds it, mode included) rendered into each repo that keeps a
devtools/mutants.json, compared by meaning (setuplib/pymeaning.py) like the
parts runner. The pairs: no mutants declared (none) against declared (installed);
a comment-only edit (refreshed) against a code edit (drift, kept); a plain run
(kept) against --rebuild (rewritten); a committed source edit (rendered) against
an uncommitted one (named, not rendered). The source is a fixture: this tool
copied into a scratch workspace and committed there, so nothing depends on this
repo's own commit state."""
import importlib.util
import json
import shutil
import subprocess

from setuplib import core
from tests.helpers import ROOT, Case, commit_all, git, git_repo, snapshot

SPEC = core.load_spec()
MUTATE = next(c for c in SPEC["components"] if c["name"] == "mutate")
REL, WHEN = MUTATE["file"], MUTATE["when"]
IGNORE = shutil.ignore_patterns(".git", ".mutants", ".progress", "__pycache__")


class Fixture(Case):
    def setUp(self):
        super().setUp()
        self.tool = self.tmp / "ws" / "tools" / "setup"
        shutil.copytree(ROOT, self.tool, ignore=IGNORE)
        git_repo(self.tool, commit=False)
        commit_all(self.tool, "the tool, committed")
        self.body = (self.tool / MUTATE["source"]).read_bytes()
        self.repo = git_repo(self.tmp / "r")

    def mutate(self, *args, target="r"):
        r = subprocess.run([str(self.tool / "setup"), target, "--only", "mutate", *args, "--json"], cwd=self.tmp,
                           env=self.env, capture_output=True, text=True)
        self.assertIn(r.returncode, (0, 1), r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual([x["component"] for x in doc["results"]], ["mutate", "commit"])
        return r.returncode, doc["results"][0]

    def declare(self):
        (self.repo / WHEN).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / WHEN).write_text('{"mutants": []}\n')
        commit_all(self.repo, "mutants declared")

    def plant(self, data, commit=True):
        f = self.repo / REL
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
        if commit:
            commit_all(self.repo, "a copy, as found")
        return f

    def snap(self):
        s = snapshot(self.repo)
        s.pop(".git/index", None)  # git status may refresh the stat cache: git's bookkeeping, not a write
        return s

    def test_no_mutants_declared_is_none_and_writes_nothing(self):
        before = self.snap()
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (0, "none"), res["detail"])
        self.assertIn(f"no {WHEN}", res["detail"])
        self.assertEqual(self.snap(), before)

    def test_declared_and_absent_is_installed_with_its_mode_then_unchanged(self):
        self.declare()
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        copy = self.repo / REL
        self.assertEqual(copy.read_bytes(), self.body)
        self.assertTrue(copy.stat().st_mode & 0o100, "the committed mode is kept")
        self.assertEqual(git(["show", "--name-only", "--format=", "HEAD"], self.repo).stdout.split(), [REL])
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (0, "unchanged"), res["detail"])

    def test_a_comment_only_difference_is_refreshed(self):
        self.declare()
        f = self.plant(self.body.replace(b"\n", b"\n# an older header line\n", 1))
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertIn("header refreshed", res["detail"])
        self.assertEqual(f.read_bytes(), self.body)

    def test_a_code_difference_is_drift_kept_until_rebuild(self):
        self.declare()
        drifted = self.body + b"\nDRIFTED = 1\n"
        f = self.plant(drifted)
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (1, "drift"), res["detail"])
        self.assertIn(f"{REL}: its meaning differs from the source", res["detail"])
        self.assertEqual(f.read_bytes(), drifted)
        code, res = self.mutate("--rebuild")
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertIn("--rebuild rewrote", res["detail"])
        self.assertEqual(f.read_bytes(), self.body)

    def test_a_present_copy_is_compared_without_mutants_declared(self):
        # the mutants file gates installing a copy, never reading one that is there
        self.plant(self.body + b"\nDRIFTED = 1\n")
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (1, "drift"), res["detail"])

    def test_rebuild_refuses_an_uncommitted_differing_copy(self):
        self.declare()
        self.plant(self.body + b"\nDRIFTED = 1\n")
        f = self.plant(self.body + b"\nDRIFTED = 2\n", commit=False)
        before = self.snap()
        for args in (["--only", "mutate", "--rebuild"], ["--rebuild", "--no-commit"]):
            with self.subTest(args=args):
                r = subprocess.run([str(self.tool / "setup"), "r", *args], cwd=self.tmp, env=self.env,
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn(REL, r.stderr)
                self.assertEqual(self.snap(), before)
        self.assertEqual(f.read_bytes(), self.body + b"\nDRIFTED = 2\n")

    def test_an_ignored_copy_is_refused_by_the_rebuild_guard(self):
        # the tree is clean to git (the clean-tree rule lets it through): only --rebuild's guard sees it
        self.declare()
        f = self.plant(self.body + b"\nDRIFTED = 1\n", commit=False)
        (self.repo / ".gitignore").write_text(REL + "\n")
        commit_all(self.repo, "ignore the copy")
        r = subprocess.run([str(self.tool / "setup"), "r", "--only", "mutate", "--rebuild"], cwd=self.tmp,
                           env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--rebuild would overwrite rendered copies holding changes git does not", r.stderr)
        self.assertIn(REL, r.stderr)
        self.assertEqual(f.read_bytes(), self.body + b"\nDRIFTED = 1\n")

    def test_an_uncommitted_source_edit_is_named_and_not_rendered(self):
        self.declare()
        src = self.tool / MUTATE["source"]
        src.write_bytes(self.body + b"\nWIP = 1\n")  # the owner's work in progress
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertEqual((self.repo / REL).read_bytes(), self.body)
        self.assertIn("uncommitted changes are its owner's, not rendered", res["detail"])
        commit_all(self.tool, "the edit, committed")  # the counterfactual: committed, it is what renders
        code, res = self.mutate("--rebuild")
        self.assertEqual((code, res["status"]), (0, "installed"), res["detail"])
        self.assertEqual((self.repo / REL).read_bytes(), self.body + b"\nWIP = 1\n")

    def test_the_source_repo_gets_none(self):
        code, res = self.mutate("--dry-run", target=str(self.tool))
        self.assertEqual((code, res["status"]), (0, "none"), res["detail"])
        self.assertIn("runner's source", res["detail"])

    def test_a_tool_in_no_work_tree_fails_and_writes_nothing(self):
        self.declare()
        shutil.rmtree(self.tool / ".git")
        before = self.snap()
        code, res = self.mutate()
        self.assertEqual((code, res["status"]), (1, "failed"), res["detail"])
        self.assertIn("no runner to render", res["detail"])
        self.assertEqual(self.snap(), before)


class Spec(Case):
    def test_the_mutants_file_is_the_one_the_runner_reads_by_default(self):
        # the component installs where the runner would find its mutants with no argument
        spec = importlib.util.spec_from_file_location("mutate_probe", ROOT / MUTATE["source"])
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.parse([])[0], mod.ROOT / WHEN)

    def test_the_source_is_this_repos_own_runner_at_the_rendered_path(self):
        # this repo runs its source where every copy sits: dev.sh's `mutants` arm calls it there
        self.assertEqual(MUTATE["source"], REL)
        self.assertIn(f"python3 {REL}", (ROOT / "dev.sh").read_text())

    def test_rebuild_accepts_only_mutate(self):
        repo = git_repo(self.tmp / "r")
        r = self.run_setup("r", "--only", "mutate", "--rebuild", "--dry-run")
        self.assertNotEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(repo.is_dir())
