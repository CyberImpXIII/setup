"""`setup fanout <component>` (PLAN-workspace-audit §3.2 option 2): one shared change
rendered into every repo that declares the component, each repo's check run, and a
commit only after it passes, naming the source commit. The plan's gates: three repos,
one red, gives two commits and one named failure; a run with nothing to render
commits nothing; `hooks copies` agrees after a hooks fan-out (live). Plus every
refusal, the dry run, the declaring files (components.json `fanout`) held to what
setup renders, and the status vocabulary documented == emitted."""
import json
import re
import subprocess

from setuplib import core, fanout
from tests.helpers import ROOT, Case, commit_all, git, git_repo, hook_listing, hook_source, snapshot, workspace_cli

FO = core.load_spec()["fanout"]


class Base(Case):
    def setUp(self):
        super().setUp()
        self.log = self.tmp / "checks-ran.log"
        self.env["FANOUT_TEST_LOG"] = str(self.log)
        self.src = hook_source(git_repo(self.tmp / "hooksrc", commit=False) / "source", ["alpha.sh"])
        commit_all(self.src.parent, "the hook source")
        self.src_head = git(["rev-parse", "HEAD"], self.src.parent).stdout.strip()

    def repo(self, name, check_exit=0, declare=True):
        """A repo that declares the hooks (its own hook beside where the copies go), a
        .gitignore for the proposal, and a dev.sh that logs it ran (outside the repo)
        and exits `check_exit`."""
        r = git_repo(self.tmp / name)
        if declare:
            (r / ".claude" / "hooks").mkdir(parents=True)
            (r / ".claude" / "hooks" / "own.sh").write_text("#!/bin/sh\n# the owner's own hook\nexit 0\n")
        (r / ".gitignore").write_text(".claude/settings.proposed.json\n")
        (r / "dev.sh").write_text(f'#!/bin/sh\necho "{name}" >> "$FANOUT_TEST_LOG"\n'
                                  f'[ {check_exit} = 0 ] || echo "FAIL the planted check is red"\nexit {check_exit}\n')
        (r / "dev.sh").chmod(0o755)
        commit_all(r, "the owner's repo")
        return r

    def fan(self, *args, component="hooks"):
        r = self.run_setup("fanout", component, "--hooks-from", str(self.src), *args)
        return r

    def fan_json(self, *args, component="hooks"):
        r = self.fan(*args, "--json", component=component)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return r.returncode, json.loads(r.stdout)

    def ran(self):
        return self.log.read_text().split() if self.log.exists() else []

    def head(self, repo):
        return git(["rev-parse", "HEAD"], repo).stdout.strip()

    def dirty(self, repo):
        return sorted(line[3:] for line in git(["status", "--porcelain", "--untracked-files=all"], repo)
                      .stdout.splitlines())


class ThreeRepos(Base):
    """The plan's gate: three repos, one whose check fails."""

    def setUp(self):
        super().setUp()
        self.a, self.b, self.c = self.repo("a"), self.repo("b"), self.repo("c", check_exit=1)
        self.heads = {n: self.head(r) for n, r in (("a", self.a), ("b", self.b), ("c", self.c))}

    def test_two_commits_and_one_named_failure(self):
        code, doc = self.fan_json()
        self.assertEqual(code, 1, doc)
        by = {r["path"]: r for r in doc["repos"]}
        self.assertEqual({k: v["status"] for k, v in by.items()}, {"a": "committed", "b": "committed", "c": "failed"})
        self.assertIs(doc["ok"], False)
        self.assertEqual(doc["source"]["commit"], self.src_head)
        for name, repo in (("a", self.a), ("b", self.b)):
            self.assertNotEqual(self.head(repo), self.heads[name])
            msg = git(["log", "-1", "--format=%B"], repo).stdout
            self.assertIn(f"source commit: {self.src_head}", msg)
            committed = git(["show", "--name-only", "--format=", "HEAD"], repo).stdout.split()
            self.assertEqual(sorted(committed), sorted(by[name]["written"]), "exactly the rendered files")
            self.assertTrue(by[name]["written"])
            self.assertEqual(self.dirty(repo), [], "nothing left behind but the ignored proposal")
            self.assertIn(by[name]["commit"], by[name]["detail"])
        c = by["c"]
        self.assertEqual(self.head(self.c), self.heads["c"], "a red check commits nothing")
        self.assertIn("check red", c["detail"])
        self.assertIn("FAIL the planted check is red", c["detail"])
        self.assertEqual(self.dirty(self.c), sorted(c["written"]), "the render left written, uncommitted, named")
        self.assertEqual(sorted(self.ran()), ["a", "b", "c"], "every repo's own check ran")

    def test_the_text_summary_names_the_failure(self):
        r = self.fan()
        self.assertEqual(r.returncode, 1, r.stderr)
        last = r.stdout.strip().splitlines()[-1]
        self.assertIn(f"from {self.src.parent}@{self.src_head[:12]}", last)
        self.assertIn("2 committed", last)
        self.assertIn("1 failed", last)
        self.assertTrue(last.endswith("failed: c"), last)

    def test_a_second_run_renders_nothing_and_commits_nothing(self):
        self.fan_json()
        git(["checkout", "-q", "--", "."], self.c)
        git(["clean", "-qfd"], self.c)
        (self.c / "dev.sh").write_text('#!/bin/sh\necho c >> "$FANOUT_TEST_LOG"\nexit 0\n')
        commit_all(self.c, "c's check fixed")
        self.fan_json()  # c now commits too
        heads = {n: self.head(r) for n, r in (("a", self.a), ("b", self.b), ("c", self.c))}
        self.log.unlink()
        code, doc = self.fan_json()
        self.assertEqual(code, 0, doc)
        self.assertEqual({r["path"]: r["status"] for r in doc["repos"]},
                         {"a": "unchanged", "b": "unchanged", "c": "unchanged"})
        self.assertEqual({n: self.head(r) for n, r in (("a", self.a), ("b", self.b), ("c", self.c))}, heads)
        self.assertEqual(self.ran(), [], "nothing to render: no check run")

    def test_repos_limits_the_run_and_names_an_undeclared_one(self):
        self.repo("plain", declare=False)
        code, doc = self.fan_json("--repos", "a", "plain")
        self.assertEqual({r["path"]: r["status"] for r in doc["repos"]}, {"a": "committed", "plain": "undeclared"})
        self.assertEqual(self.head(self.b), self.heads["b"], "a repo --repos leaves out is not touched")
        self.assertEqual(code, 0)

    def test_a_discovered_undeclared_repo_is_counted_not_listed(self):
        self.repo("plain", declare=False)
        r = self.fan()
        self.assertNotIn("plain", [line.split()[1] for line in r.stdout.splitlines() if line.startswith("  ")])
        # plain, and the hook source's own repo (it holds no .claude/hooks)
        self.assertIn("2 other repo(s) do not declare it", r.stdout)

    def test_a_dry_run_writes_nothing_and_runs_no_check(self):
        before = {n: snapshot(r) for n, r in (("a", self.a), ("b", self.b), ("c", self.c))}
        code, doc = self.fan_json("--dry-run")
        self.assertEqual(code, 0, doc)
        self.assertEqual({r["status"] for r in doc["repos"]}, {"would-commit"})
        self.assertTrue(all(r["written"] for r in doc["repos"]))
        self.assertEqual({n: snapshot(r) for n, r in (("a", self.a), ("b", self.b), ("c", self.c))}, before)
        self.assertEqual(self.ran(), [])

    def test_agent_names_the_trailer_a_commit_msg_hook_wants(self):
        hook = self.a / ".git" / "hooks" / "commit-msg"
        hook.write_text('#!/bin/sh\ngrep -q "^Agent: setup$" "$1" || { echo "no Agent trailer" >&2; exit 1; }\n')
        hook.chmod(0o755)
        _, doc = self.fan_json("--repos", "a")
        a = doc["repos"][0]
        self.assertEqual(a["status"], "failed", a)
        self.assertIn("the commit was refused", a["detail"])
        self.assertIn("no Agent trailer", a["detail"])
        self.assertEqual(self.dirty(self.a), sorted(a["written"]), "left written and unstaged, named")
        self.assertEqual(git(["diff", "--cached", "--name-only"], self.a).stdout, "")
        git(["checkout", "-q", "--", "."], self.a)
        git(["clean", "-qfd"], self.a)
        _, doc = self.fan_json("--repos", "a", "--agent", "setup")
        self.assertEqual(doc["repos"][0]["status"], "committed", doc)
        self.assertIn("Agent: setup", git(["log", "-1", "--format=%B"], self.a).stdout)


class Refusals(Base):
    def setUp(self):
        super().setUp()
        self.a = self.repo("a")

    def test_a_dirty_tree_fails_and_nothing_is_written(self):
        (self.a / "notes.md").write_text("the owner's uncommitted work\n")
        before = snapshot(self.a)
        code, doc = self.fan_json()
        self.assertEqual(code, 1)
        self.assertEqual(doc["repos"][0]["status"], "failed")
        self.assertIn("the tree is not clean (notes.md)", doc["repos"][0]["detail"])
        self.assertEqual(snapshot(self.a), before)
        self.assertEqual(self.ran(), [])

    def test_drift_fails_without_rebuild_and_is_overwritten_with_it(self):
        self.fan_json()
        copy = next(p for p in (self.a / ".claude" / "hooks").iterdir() if p.name == "alpha.sh")
        copy.write_text("#!/bin/sh\necho drifted logic\nexit 1\n")
        commit_all(self.a, "a drifted copy")
        head, before = self.head(self.a), snapshot(self.a)
        code, doc = self.fan_json()
        self.assertEqual((code, doc["repos"][0]["status"]), (1, "failed"), doc)
        self.assertIn("--rebuild overwrites a drifted copy", doc["repos"][0]["detail"])
        self.assertEqual((self.head(self.a), snapshot(self.a)), (head, before))
        code, doc = self.fan_json("--rebuild")
        self.assertEqual((code, doc["repos"][0]["status"]), (0, "committed"), doc)
        self.assertNotIn("drifted logic", copy.read_text())

    def test_an_uncommitted_source_is_refused_before_any_repo(self):
        (self.src / "hooks" / "alpha.sh").write_text("#!/bin/sh\n# hooks: applies_to=all\necho unreviewed\n")
        before = snapshot(self.a)
        r = self.fan()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("holds uncommitted changes", r.stderr)
        self.assertEqual(snapshot(self.a), before)

    def test_a_source_in_no_work_tree_is_refused(self):
        loose = hook_source(self.tmp / "loose", ["alpha.sh"])
        r = self.run_setup("fanout", "hooks", "--hooks-from", str(loose))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("is in no git work tree", r.stderr)

    def test_a_component_not_for_fanout_is_refused(self):
        r = self.run_setup("fanout", "todo")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("not a fanout component", r.stderr)

    def test_a_path_that_is_no_work_tree_top_fails_named(self):
        (self.a / "sub").mkdir()
        code, doc = self.fan_json("--repos", str(self.a / "sub"))
        self.assertEqual((code, doc["repos"][0]["status"]), (1, "failed"))
        self.assertIn("is not the top of a git work tree", doc["repos"][0]["detail"])

    def test_a_check_past_its_timeout_fails(self):
        (self.a / "dev.sh").write_text("#!/bin/sh\nsleep 30\n")
        commit_all(self.a, "a slow check")
        code, doc = self.fan_json("--check-timeout", "1")
        self.assertEqual(code, 1)
        self.assertIn("did not finish in 1s", doc["repos"][0]["detail"])


class Rules(Base):
    """The rules block: a block behind the template is updated and committed, naming
    this tool's commit; a CLAUDE.md with no block is not a declaring repo."""

    def test_a_block_behind_the_template_is_updated_and_committed(self):
        if git(["status", "--porcelain", "--", "templates/shared-rules.md"], ROOT).stdout.strip():
            self.skipTest("templates/shared-rules.md holds uncommitted changes: fanout refuses it (Refusals)")
        old = "an older rule\n"
        behind = self.repo("behind", declare=False)
        (behind / "CLAUDE.md").write_text(f"# behind\n\n<!-- shared:rules@{core.sha12(old)} -->\n{old}"
                                          "<!-- /shared -->\n\nits own rule\n")
        commit_all(behind, "an old block")
        hand = self.repo("hand", declare=False)
        (hand / "CLAUDE.md").write_text("# hand\n\na hand copy of the rules\n")
        commit_all(hand, "a hand copy")
        code, doc = self.fan_json("--repos", "behind", "hand", component="rules")
        by = {r["path"]: r for r in doc["repos"]}
        self.assertEqual({k: v["status"] for k, v in by.items()}, {"behind": "committed", "hand": "undeclared"}, doc)
        self.assertEqual(code, 0)
        self.assertEqual(by["behind"]["written"], ["CLAUDE.md"])
        text = (behind / "CLAUDE.md").read_text()
        self.assertIn((ROOT / "templates" / "shared-rules.md").read_text(), text)
        self.assertTrue(text.endswith("its own rule\n"), "only the block changes")
        msg = git(["log", "-1", "--format=%B"], behind).stdout
        self.assertIn(f"source commit: {git(['rev-parse', 'HEAD'], ROOT).stdout.strip()}", msg)
        self.assertEqual(doc["source"]["path"], str(core._toplevel(ROOT)))


class Parts(Base):
    """The runner copy: rendered as its repo's HEAD holds it, the commit named."""

    def test_a_drifted_runner_needs_rebuild_then_is_committed_then_unchanged(self):
        where = fanout_parts_source()
        if where is None:
            self.skipTest("lone clone: no parts runner source")
        r = self.repo("p", declare=False)
        (r / "devtools").mkdir()
        (r / "devtools" / "parts.py").write_text("print('an old runner')\n")
        commit_all(r, "an old runner")
        code, doc = self.fan_json("--repos", "p", component="parts")
        self.assertEqual((code, doc["repos"][0]["status"]), (1, "failed"), doc)
        code, doc = self.fan_json("--repos", "p", "--rebuild", component="parts")
        self.assertEqual((code, doc["repos"][0]["status"]), (0, "committed"), doc)
        head = git(["rev-parse", "HEAD"], where).stdout.strip()
        self.assertEqual(doc["source"]["commit"], head)
        self.assertIn(f"source commit: {head}", git(["log", "-1", "--format=%B"], r).stdout)
        self.assertEqual((r / "devtools" / "parts.py").read_bytes(),
                         git_show(where, rel_in(where)), "the runner as HEAD holds it")
        code, doc = self.fan_json("--repos", "p", component="parts")
        self.assertEqual((code, doc["repos"][0]["status"]), (0, "unchanged"), doc)


def rel_in(where):
    """The runner's path in its repo, as setup resolves it."""
    s = core.Setup(ROOT, label=".", name="probe", dry_run=True)
    src, w, _ = s._parts_source()
    return src.resolve().relative_to(w.resolve()).as_posix()


def git_show(where, rel):
    return subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=where, capture_output=True).stdout


class SubRepo(Base):
    """The workspace top's shape: a folder in no work tree whose `.claude/` is one."""

    def test_hooks_render_into_the_folder_and_commit_in_its_claude_repo(self):
        top = self.tmp / "top"
        sub = git_repo(top / ".claude", commit=False)
        (sub / "hooks").mkdir()
        (sub / "hooks" / "own.sh").write_text("#!/bin/sh\nexit 0\n")
        (sub / ".gitignore").write_text("settings.proposed.json\n")
        # the check is the committing repo's: the .claude repo's own dev.sh
        (sub / "dev.sh").write_text('#!/bin/sh\necho top >> "$FANOUT_TEST_LOG"\n')
        (sub / "dev.sh").chmod(0o755)
        commit_all(sub, "the sub repo")
        code, doc = self.fan_json("--repos", str(sub))
        r = doc["repos"][0]
        self.assertEqual((code, r["path"], r["status"]), (0, "top", "committed"), doc)
        self.assertEqual(self.ran(), ["top"])
        committed = git(["show", "--name-only", "--format=", "HEAD"], sub).stdout.split()
        self.assertTrue(r["written"])
        self.assertEqual(sorted(p.removeprefix(".claude/") for p in r["written"]), sorted(committed))


class Spec(Case):
    def test_each_fanout_component_is_one_setup_renders(self):
        names = {c["name"] for c in core.load_spec()["components"]}
        self.assertLessEqual(set(FO["declared_by"]), names)

    def test_each_declaring_file_is_what_its_component_renders(self):
        """A new repo setup makes holds each declaring file (and the rules block's
        `contains`): the declaration is read from what setup writes, never a guess."""
        src = hook_source(self.tmp / "hooksrc", ["alpha.sh"])
        r = self.run_setup("new", "--hooks-from", str(src))
        self.assertIn(r.returncode, (0, 1), r.stderr)
        new = self.tmp / "new"
        comps = {c["name"]: c for c in core.load_spec()["components"]}
        for name, d in FO["declared_by"].items():
            if name == "parts" and not (new / d["file"]).exists():
                self.assertIsNone(fanout_parts_source(), "parts rendered nothing while its source resolves")
                continue
            self.assertTrue((new / d["file"]).exists(), f"{name}: {d['file']} not rendered")
            if "contains" in d:
                self.assertIn(d["contains"], (new / d["file"]).read_text())
        self.assertEqual(FO["declared_by"]["parts"]["file"], comps["parts"]["file"])

    def test_statuses_documented_equal_emitted(self):
        text = (ROOT / "setuplib" / "fanout.py").read_text()
        emitted = set(re.findall(r'Outcome\([^,]+, "([a-z-]+)"', text))
        self.assertEqual(emitted, set(FO["statuses"]))

    def test_the_components_subcommand_lists_them(self):
        r = self.run_setup("components")
        for name in FO["declared_by"]:
            self.assertRegex(r.stdout, r"(?m)^  " + name + r"\s")
        for k in FO["statuses"]:
            self.assertRegex(r.stdout, r"(?m)^  " + re.escape(k) + r"\s")


def fanout_parts_source():
    """The parts runner's source as setup resolves it, or None in a lone clone."""
    s = core.Setup(ROOT, label=".", name="probe", dry_run=True)
    where, _, _ = s.render_source("parts")
    return where


class Live(Case):
    """In the workspace: a hooks fan-out from the real source leaves `hooks copies`
    agreeing in the repo it rendered into."""

    def test_hooks_copies_agrees_after_a_hooks_fanout(self):
        top_, hooks_cli = workspace_cli("hooks")
        if hooks_cli is None or hook_listing() is None:
            self.skipTest("lone clone: no hooks dependency")
        src_repo = hooks_cli.parent
        if git(["status", "--porcelain", "--", "source"], src_repo).stdout.strip():
            self.skipTest(f"{src_repo}/source holds uncommitted changes: fanout refuses it (tested in Refusals)")
        top = self.tmp / "ws"
        top.mkdir()
        (top / "CLAUDE.md").write_text("x\n")
        repo = git_repo(top / "r")
        (repo / ".claude" / "hooks").mkdir(parents=True)
        (repo / ".claude" / "hooks" / "own.sh").write_text("#!/bin/sh\nexit 0\n")
        (repo / ".gitignore").write_text(".claude/settings.proposed.json\n")
        (repo / "dev.sh").write_text("#!/bin/sh\nexit 0\n")
        (repo / "dev.sh").chmod(0o755)
        commit_all(repo)
        r = self.run_setup("fanout", "hooks", "--json", cwd=top)
        doc = json.loads(r.stdout)
        self.assertEqual([x["status"] for x in doc["repos"]], ["committed"], doc)
        r = subprocess.run([str(hooks_cli), "copies", str(top), "--json", "--gate", "r"],
                           capture_output=True, text=True)
        rows = [f for loc in json.loads(r.stdout)["locations"] if loc["path"] == "r" for f in loc["files"]]
        self.assertEqual({f["status"] for f in rows}, {"ok"}, [f for f in rows if f["status"] != "ok"])
        self.assertEqual(sorted(f["file"] for f in rows), sorted(rel for rel, _ in hook_listing()))


class Unit(Case):
    def test_work_trees_prunes_and_finds_nested(self):
        git_repo(self.tmp / "a")
        git_repo(self.tmp / "a" / "nested")
        git_repo(self.tmp / "node_modules" / "x")
        found = fanout.work_trees(self.tmp, set(FO["prune"]))
        self.assertEqual([p.relative_to(self.tmp).as_posix() for p in found], ["a", "a/nested"])
