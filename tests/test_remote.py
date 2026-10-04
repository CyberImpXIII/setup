"""--github, against tests/fake_gh.py (never a real GitHub). Public by default,
--private on request, never into an existing repo, and the result is verified
(origin set, pushed sha == HEAD, visibility as asked), not taken from gh's exit."""
from tests.helpers import Case, git, git_repo


class Remote(Case):
    def calls(self):
        p = self.tmp / "_github/calls.log"
        return p.read_text().splitlines() if p.exists() else []

    def test_github_is_public_by_default_and_verified(self):
        code, res = self.run_json("fresh", "--github")
        self.assertEqual(code, 0, res)
        self.assertEqual(res["remote"]["status"], "installed")
        self.assertIn("github.com/fakeowner/fresh (public)", res["remote"]["detail"])
        self.assertTrue(any(c.startswith("repo create fakeowner/fresh --public") for c in self.calls()))
        head = git(["rev-parse", "HEAD"], self.tmp / "fresh").stdout.strip()
        self.assertIn(head[:7], res["remote"]["detail"])
        self.assertIn('"repo": "github.com/fakeowner/fresh"', res["agent"]["detail"])

    def test_private_on_request(self):
        code, res = self.run_json("fresh", "--github", "--private", "--owner", "someone")
        self.assertEqual(code, 0, res)
        self.assertIn("github.com/someone/fresh (private)", res["remote"]["detail"])
        self.assertTrue(any(c.startswith("repo create someone/fresh --private") for c in self.calls()))

    def test_existing_github_repo_is_never_pushed_into(self):
        self.run_json("a", "--github", "--name", "same")
        code, res = self.run_json("b", "--github", "--name", "same")
        self.assertEqual((code, res["remote"]["status"]), (1, "failed"))
        self.assertIn("already exists", res["remote"]["detail"])
        self.assertEqual(sum(c.startswith("repo create") for c in self.calls()), 1)

    def test_gh_that_reports_success_but_did_nothing_is_caught(self):
        self.env["FAKE_GH_LIE"] = "1"
        code, res = self.run_json("fresh", "--github")
        self.assertEqual((code, res["remote"]["status"]), (1, "failed"))
        self.assertIn("no origin", res["remote"]["detail"])

    def test_wrong_visibility_is_caught(self):
        self.env["FAKE_GH_VIS"] = "private"
        code, res = self.run_json("fresh", "--github")
        self.assertEqual((code, res["remote"]["status"]), (1, "failed"))
        self.assertIn("is private, asked for public", res["remote"]["detail"])

    def test_existing_origin_is_unchanged(self):
        self.run_json("fresh", "--github")
        code, res = self.run_json("fresh", "--github")
        self.assertEqual((code, res["remote"]["status"]), (0, "unchanged"))
        self.assertEqual(sum(c.startswith("repo create") for c in self.calls()), 1)

    def test_existing_repo_without_commits_is_not_pushed(self):
        git_repo(self.tmp / "r", commit=False)
        code, res = self.run_json("r", "--github")
        self.assertEqual((code, res["remote"]["status"]), (1, "failed"))
        self.assertIn("no commits", res["remote"]["detail"])

    def test_no_flag_no_remote(self):
        code, res = self.run_json("fresh")
        self.assertEqual(res["remote"]["status"], "none")
        self.assertEqual([c for c in self.calls() if c.startswith("repo")], [])
