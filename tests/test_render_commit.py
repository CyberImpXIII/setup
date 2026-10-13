"""PLAN-architecture.md §11 S2: in a repo setup did not create, the renderer commits
what it renders in the same run, or writes nothing. A tree with changes is refused
before any write when the run would render; settings.json rides along only when it
is byte for byte its proposal (Jacob, 2026-10-12); a commit the repo's git hooks
refuse leaves the render written for its owner. Planted repos, the hook source a planted folder."""
import json

from tests.helpers import Case, git, git_repo, hook_source, snapshot


class RenderCommit(Case):
    def setUp(self):
        super().setUp()
        self.repo = git_repo(self.tmp / "r")
        self.src = hook_source(self.tmp / "src", ["a.sh", "b.sh"])

    def run_hooks(self, *extra):
        return self.run_setup("r", "--hooks-from", str(self.src), "--only", "hooks", "--json", *extra)

    def status(self):
        return git(["status", "--porcelain", "--untracked-files=all"], self.repo).stdout.splitlines()

    def test_a_clean_tree_gets_its_render_committed_exactly(self):
        r = self.run_hooks()
        doc = {x["component"]: x for x in json.loads(r.stdout)["results"]}
        self.assertEqual(doc["commit"]["status"], "installed", doc["commit"])
        committed = sorted(git(["show", "--name-only", "--format=", "HEAD"], self.repo).stdout.split())
        self.assertEqual(committed, sorted(x["path"] for x in json.loads(r.stdout)["hook_files"]))
        self.assertEqual(git(["log", "-1", "--format=%s"], self.repo).stdout.strip(),
                         f"setup: render {len(committed)} file(s) into r")
        # nothing left uncommitted but setup's own proposal, which it never commits
        self.assertEqual(self.status(), ["?? .claude/settings.proposed.json"])

    def test_a_dirty_tree_is_refused_and_nothing_is_written(self):
        (self.repo / "notes.txt").write_text("someone's work in progress\n")
        before = snapshot(self.repo)
        r = self.run_hooks()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("the tree is not clean (notes.txt)", r.stderr)
        self.assertEqual(snapshot(self.repo), before)

    def test_a_dirty_tree_with_nothing_to_render_is_not_refused(self):
        self.run_hooks()  # rendered and committed
        (self.repo / "notes.txt").write_text("someone's work in progress\n")
        r = self.run_hooks()
        self.assertEqual(r.returncode, 0, r.stderr)
        doc = {x["component"]: x for x in json.loads(r.stdout)["results"]}
        self.assertEqual(doc["commit"]["status"], "none", doc["commit"])

    def test_a_dry_run_on_a_dirty_tree_says_the_real_run_would_be_refused(self):
        (self.repo / "notes.txt").write_text("x\n")
        before = snapshot(self.repo)
        r = self.run_hooks("--dry-run")
        doc = {x["component"]: x for x in json.loads(r.stdout)["results"]}
        self.assertEqual(doc["commit"]["status"], "needs-owner", doc["commit"])
        self.assertIn("would be refused", doc["commit"]["detail"])
        self.assertEqual(snapshot(self.repo), before)

    def plant_settings(self, live_equals_proposal):
        """A committed settings.json, then changed: equal to the proposal setup will
        write, or not."""
        self.run_setup("r", "--hooks-from", str(self.src), "--only", "hooks", "--dry-run")
        (self.repo / ".claude").mkdir(exist_ok=True)
        (self.repo / ".claude/settings.json").write_text("{}\n")
        git(["add", ".claude/settings.json"], self.repo)
        git(["commit", "-q", "-m", "settings"], self.repo)
        self.run_hooks()  # renders, commits, writes the proposal
        prop = (self.repo / ".claude/settings.proposed.json").read_text()
        # the next render: a hook copy drifts in a commit, so the run has something to render
        (self.repo / ".claude/hooks/a.sh").unlink()
        git(["commit", "-q", "-am", "a.sh gone"], self.repo)
        (self.repo / ".claude/settings.json").write_text(prop if live_equals_proposal else '{"x": 1}\n')

    def test_settings_equal_to_its_proposal_is_committed_with_the_render(self):
        self.plant_settings(True)
        r = self.run_hooks()
        self.assertEqual(r.returncode, 0, r.stderr)
        committed = git(["show", "--name-only", "--format=", "HEAD"], self.repo).stdout.split()
        self.assertIn(".claude/settings.json", committed)
        self.assertIn(".claude/hooks/a.sh", committed)
        self.assertEqual(self.status(), ["?? .claude/settings.proposed.json"])

    def test_settings_differing_from_its_proposal_stays_jacobs_and_refuses(self):
        self.plant_settings(False)
        before = snapshot(self.repo)
        r = self.run_hooks()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(".claude/settings.json", r.stderr)
        self.assertEqual(snapshot(self.repo), before)

    def test_a_commit_the_repos_git_hooks_refuse_leaves_the_render_for_its_owner(self):
        """The repo's gates decide: the render stays written and unstaged, needs-owner
        (a rollback meant no render could land in a gated repo; TODO.md S2 (1))."""
        hooks = self.tmp / "gate"
        hooks.mkdir()
        (hooks / "pre-commit").write_text("#!/bin/sh\necho 'refused by the planted gate' >&2\nexit 1\n")
        (hooks / "pre-commit").chmod(0o755)
        git(["config", "core.hooksPath", str(hooks)], self.repo)
        head = git(["rev-parse", "HEAD"], self.repo).stdout
        r = self.run_hooks()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        res = {x["component"]: x for x in doc["results"]}
        self.assertEqual(res["commit"]["status"], "needs-owner", res["commit"])
        self.assertIn("refused by the planted gate", res["commit"]["detail"])
        self.assertIn("left written and unstaged", res["commit"]["detail"])
        self.assertEqual(git(["rev-parse", "HEAD"], self.repo).stdout, head)
        self.assertEqual(git(["diff", "--cached", "--name-only"], self.repo).stdout, "")
        rendered = sorted(x["path"] for x in doc["hook_files"])
        self.assertTrue(rendered and all((self.repo / p).is_file() for p in rendered), rendered)
        # the next run renders nothing more into that tree, so it is not refused
        self.assertEqual(self.run_hooks().returncode, 0)
