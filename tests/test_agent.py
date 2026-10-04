"""The agent component's roster line: its "repo" says what the target is now.
github.com/<slug> with an origin, "local, no remote yet" for a git repo with
no origin (the roster's own wording), "none yet" only when there is no repo."""
from tests.helpers import Case, git, git_repo


class Agent(Case):
    def repo_field(self, res):
        detail = res["agent"]["detail"]
        self.assertIn('"repo": ', detail)
        return detail.split('"repo": "', 1)[1].split('"', 1)[0]

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
