"""The agent component's roster line: its "repo" says what the target is now.
github.com/<slug> with an origin, "local, no remote yet" for a git repo with
no origin (the roster's own wording), "none yet" only when there is no repo.

Its "dir" is the target relative to the folder the roster's dirs are relative
to (the working folder, or --relative-to), normalised whatever was typed; a
target outside that folder has no roster dir, so "dir" (and every field built
from it) is null, never the path as typed."""
import json

from tests.helpers import Case, git, git_repo


class Agent(Case):
    def entry(self, res):
        detail = res["agent"]["detail"]
        return json.loads(detail[detail.index("{"):])

    def repo_field(self, res):
        return self.entry(res)["repo"]

    def test_git_repo_without_origin_is_local_no_remote_yet(self):
        git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--dry-run")
        self.assertEqual(self.repo_field(res), "local, no remote yet")

    def test_new_folder_after_a_real_run_is_local_no_remote_yet(self):
        _, res = self.run_json("fresh")
        self.assertEqual(res["repo"]["status"], "installed")
        self.assertEqual(self.repo_field(res), "local, no remote yet")

    def test_no_repo_yet_is_none_yet(self):
        _, res = self.run_json("fresh", "--dry-run")
        self.assertFalse((self.tmp / "fresh").exists())
        self.assertEqual(self.repo_field(res), "none yet")

    def test_git_repo_with_origin_names_it(self):
        repo = git_repo(self.tmp / "r")
        git(["remote", "add", "origin", "https://github.com/someone/r.git"], repo)
        _, res = self.run_json("r", "--dry-run")
        self.assertEqual(self.repo_field(res), "github.com/someone/r")


class AgentDir(Case):
    def setUp(self):
        super().setUp()
        git_repo(self.tmp / "sub" / "r")
        (self.tmp / "elsewhere").mkdir()

    def entry(self, *args, cwd=None):
        _, res = self.run_json(*args, "--dry-run", cwd=cwd)
        detail = res["agent"]["detail"]
        return json.loads(detail[detail.index("{"):]), detail

    def test_dir_is_normalised_however_the_path_is_typed(self):
        for typed in ["sub/r", "./sub/r/", "sub/../sub/r", "sub//r", str(self.tmp / "sub" / "r")]:
            entry, _ = self.entry(typed)
            self.assertEqual((entry["dir"], entry["start_here"]), ("sub/r", "sub/r/CLAUDE.md"), typed)

    def test_target_outside_the_base_has_a_null_dir_not_the_typed_path(self):
        entry, detail = self.entry("../sub/r", cwd=self.tmp / "elsewhere")
        self.assertIsNone(entry["dir"])
        self.assertIsNone(entry["start_here"])
        self.assertEqual(entry["precommit"], "./dev.sh check")  # fields not built from dir are kept
        self.assertIn("--relative-to", detail)

    def test_relative_to_sets_the_base(self):
        # the flag changes the output: same target, two bases, two dirs
        cwd = self.tmp / "elsewhere"
        self.assertEqual(self.entry("../sub/r", "--relative-to", "..", cwd=cwd)[0]["dir"], "sub/r")
        self.assertEqual(self.entry("../sub/r", "--relative-to", str(self.tmp / "sub"), cwd=cwd)[0]["dir"], "r")

    def test_target_equal_to_the_base_is_dot(self):
        self.assertEqual(self.entry(".", cwd=self.tmp / "sub" / "r")[0]["dir"], ".")

    def test_relative_to_that_is_not_a_folder_is_a_usage_error(self):
        r = self.run_setup("sub/r", "--dry-run", "--relative-to", "nope")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("--relative-to nope is not a folder", r.stderr)
