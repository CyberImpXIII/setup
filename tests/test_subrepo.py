"""The workspace top: a folder that is no git work tree, whose .claude/ is its own
local repo. `--only hooks` renders the hook copies there and commits them in that
repo, paths relative to it; every other run is refused as before, and the clean-tree
rule (PLAN-architecture §11 S2) and --rebuild's guard read that repo."""
from tests.helpers import Case, commit_all, git, git_repo, hook_listing, snapshot


class SubRepo(Case):
    def setUp(self):
        super().setUp()
        if hook_listing() is None:
            self.skipTest("lone clone: no hooks dependency")
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        (self.ws / "notes.md").write_text("the workspace's own file\n")
        self.repo = git_repo(self.ws / ".claude")
        (self.repo / ".gitignore").write_text("settings.proposed.json\n")  # as a local .claude repo keeps it
        commit_all(self.repo, "ignore the proposal")
        self.hook = next(rel for rel, _ in hook_listing() if rel.endswith("/no-inline-blobs.sh"))

    def log(self):
        return git(["log", "--format=%s"], self.repo).stdout.split("\n")

    def test_only_hooks_renders_and_commits_in_the_claude_repo(self):
        code, res = self.run_json("ws", "--only", "hooks")
        self.assertEqual(code, 0, res)
        self.assertEqual(res["commit"]["status"], "installed", res["commit"]["detail"])
        self.assertIn("in its .claude/ repo", res["commit"]["detail"])
        self.assertTrue((self.ws / self.hook).is_file())
        committed = git(["show", "--name-only", "--format=", "HEAD"], self.repo).stdout.split()
        want = sorted(rel[len(".claude/"):] for rel, _ in hook_listing())
        self.assertEqual(sorted(committed), want)
        self.assertEqual(git(["status", "--porcelain"], self.repo).stdout.strip(), "")
        self.assertNotEqual(git(["rev-parse", "--show-toplevel"], self.ws).returncode, 0,
                            "the workspace top is still no repo")
        self.assertEqual(self.log()[0], "setup: render %d file(s) into ws" % len(want))

    def test_any_other_run_is_refused_and_names_the_way(self):
        before = snapshot(self.ws)
        for args in ([], ["--only", "parts"]):
            r = self.run_setup("ws", *args)
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn("its .claude/ is its own repo", r.stderr)
        self.assertEqual(snapshot(self.ws), before)

    def test_a_dirty_claude_repo_is_refused_and_nothing_written(self):
        (self.repo / "scratch.txt").write_text("someone's work\n")
        before = snapshot(self.ws)
        r = self.run_setup("ws", "--only", "hooks")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(".claude/scratch.txt", r.stderr)
        self.assertEqual(snapshot(self.ws), before)

    def test_rebuild_guard_reads_the_claude_repo(self):
        self.assertEqual(self.run_setup("ws", "--only", "hooks").returncode, 0)
        f = self.ws / self.hook
        f.write_text("#!/bin/sh\necho drifted\n")
        commit_all(self.repo, "a drifted copy, committed")
        f.write_text("#!/bin/sh\necho drifted, uncommitted\n")
        r = self.run_setup("ws", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(self.hook, r.stderr)
        git(["checkout", "--", self.hook[len(".claude/"):]], self.repo)
        code, res = self.run_json("ws", "--only", "hooks", "--rebuild")
        self.assertEqual(res["commit"]["status"], "installed", res["commit"]["detail"])
        self.assertNotEqual(f.read_text(), "#!/bin/sh\necho drifted\n")
        self.assertEqual(git(["show", "--name-only", "--format=", "HEAD"], self.repo).stdout.split(),
                         [self.hook[len(".claude/"):]])
