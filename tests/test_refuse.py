"""PLAN-repo-setup §3 "Fails safely": a refused path exits non-zero, says why, and
writes nothing, there or anywhere around it."""
from tests.helpers import Case, git_repo, snapshot


class Refuse(Case):
    def assertRefused(self, *args, why):
        before = snapshot(self.tmp)
        r = self.run_setup(*args)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("refused", r.stderr)
        self.assertIn(why, r.stderr)
        self.assertIn("Nothing was written", r.stderr)
        self.assertEqual(snapshot(self.tmp), before)

    def test_non_empty_folder_that_is_not_a_repo(self):
        (self.tmp / "folder").mkdir()
        (self.tmp / "folder/notes.txt").write_text("someone's\n")
        self.assertRefused("folder", why="is not a git work tree")

    def test_subfolder_of_a_repo(self):
        repo = git_repo(self.tmp / "r")
        (repo / "sub").mkdir()
        (repo / "sub/f").write_text("x\n")
        self.assertRefused("r/sub", why="not its top level")

    def test_new_path_inside_a_repo_would_nest(self):
        git_repo(self.tmp / "r")
        self.assertRefused("r/newrepo", why="would nest")
        self.assertFalse((self.tmp / "r/newrepo").exists())

    def test_missing_parent(self):
        self.assertRefused("no/such/parent/x", why="does not exist")

    def test_a_file(self):
        (self.tmp / "afile").write_text("x\n")
        self.assertRefused("afile", why="not a directory")

    def test_private_without_github_is_a_usage_error(self):
        r = self.run_setup("fresh", "--private")
        self.assertEqual(r.returncode, 2)
        self.assertFalse((self.tmp / "fresh").exists())

    def test_dry_run_is_refused_the_same_way(self):
        (self.tmp / "folder").mkdir()
        (self.tmp / "folder/notes.txt").write_text("x\n")
        self.assertRefused("folder", "--dry-run", why="is not a git work tree")

    def test_an_empty_folder_is_accepted_as_new(self):
        (self.tmp / "empty").mkdir()
        code, res = self.run_json("empty")
        self.assertEqual((code, res["repo"]["status"]), (0, "installed"))
