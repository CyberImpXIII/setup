"""--no-commit: an existing repo's render written and left uncommitted, every path
named, for the owner to commit with its own work in one commit. The way out of a
repo whose pre-commit wants the render (stale hook copies red) while its tree holds
finished work (so a committing render is refused as dirty). A dirty tree is let
through; a path the run would write that holds uncommitted changes is not."""
from tests.helpers import Case, commit_all, git, git_repo, hook_listing, snapshot


class NoCommit(Case):
    def setUp(self):
        super().setUp()
        if hook_listing() is None:
            self.skipTest("lone clone: no hooks dependency")
        self.repo = git_repo(self.tmp / "r")
        self.hook = next(rel for rel, _ in hook_listing() if rel.endswith("/no-inline-blobs.sh"))
        (self.repo / self.hook).parent.mkdir(parents=True)
        (self.repo / self.hook).write_text("#!/bin/sh\necho a stale copy\n")
        commit_all(self.repo, "a stale hook copy, committed")
        # the owner's finished work, not committed: a change and a new file
        (self.repo / "README").write_text("the owner's change\n")
        (self.repo / "notes.md").write_text("the owner's new file\n")
        self.head = git(["rev-parse", "HEAD"], self.repo).stdout

    def test_renders_into_a_dirty_tree_commits_nothing_and_names_each_path(self):
        code, res = self.run_json("r", "--only", "hooks", "--rebuild", "--no-commit")
        self.assertEqual(code, 0, res)
        c = res["commit"]
        self.assertEqual(c["status"], "needs-owner", c)
        self.assertEqual(git(["rev-parse", "HEAD"], self.repo).stdout, self.head, "no commit made")
        self.assertEqual(git(["diff", "--cached", "--name-only"], self.repo).stdout, "", "nothing staged")
        self.assertEqual((self.repo / "README").read_text(), "the owner's change\n")
        self.assertEqual((self.repo / "notes.md").read_text(), "the owner's new file\n")
        self.assertNotEqual((self.repo / self.hook).read_text(), "#!/bin/sh\necho a stale copy\n")
        named, _, never = c["detail"].split(": ", 1)[1].partition("; also written, never to be committed: ")
        listed = named.split(": ", 1)[1].split(", ") + never.split(", ")
        changed = {l[3:] for l in git(["status", "--porcelain", "--untracked-files=all"], self.repo)
                   .stdout.splitlines()} - {"README", "notes.md"}
        self.assertEqual(sorted(listed), sorted(changed), "every path written is named, and only those")
        self.assertEqual(never, ".claude/settings.proposed.json")
        self.assertIn(self.hook, listed)

    def test_without_it_the_same_tree_is_refused(self):
        before = snapshot(self.repo)
        r = self.run_setup("r", "--only", "hooks", "--rebuild")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("the tree is not clean", r.stderr)
        self.assertEqual(snapshot(self.repo), before)

    def test_a_path_it_would_write_with_uncommitted_changes_is_refused(self):
        # a copy equal to the source but for a comment is rewritten ("header refreshed"):
        # its uncommitted comment would be lost
        src = dict(hook_listing())[self.hook]
        (self.repo / self.hook).write_bytes(src.read_bytes())
        commit_all(self.repo, "the copy, current")
        (self.repo / self.hook).write_bytes(src.read_bytes() + b"# the owner's uncommitted note\n")
        before = snapshot(self.repo)
        r = self.run_setup("r", "--only", "hooks", "--no-commit")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn(self.hook, r.stderr)
        self.assertIn("would lose them", r.stderr)
        self.assertEqual(snapshot(self.repo), before)
        _, dry = self.run_json("r", "--only", "hooks", "--no-commit", "--dry-run")
        self.assertIn("a real run would be refused", dry["commit"]["detail"])
        self.assertEqual(snapshot(self.repo), before)

    def test_a_dry_run_names_the_paths_and_writes_nothing(self):
        before = snapshot(self.repo)
        _, res = self.run_json("r", "--only", "hooks", "--rebuild", "--no-commit", "--dry-run")
        self.assertIn("would be written", res["commit"]["detail"])
        self.assertIn(self.hook, res["commit"]["detail"])
        self.assertEqual(snapshot(self.repo), before)

    def test_refused_on_a_new_folder_and_with_node(self):
        r = self.run_setup("new", "--no-commit")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("is not one yet", r.stderr)
        self.assertFalse((self.tmp / "new").exists())
        r = self.run_setup("r", "--node", "--no-commit")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("not with --node", r.stderr)
