"""The githooks component (PLAN-hard-gates.md §2, §3 rows 3 and 6, §6, §7 phase 2,
§7a, §8 answer 2; PLAN-check-progress.md §9.2).

Two halves. Setup's: the three hooks installed if absent and never overwritten,
core.hooksPath set only when nothing would be refused for want of wiring, never over
another one, needs-jacob until the stamp and ledger hooks are registered. The
hooks' own: real commits in fixture repos with core.hooksPath set, inside a
session (CLAUDECODE set) and outside one, against the recorded check pass and a
stand-in checks CLI (tests/fake_checks.py); the live case holds the pre-commit's
reading of `one no-secrets` to the real shared checks CLI."""
import json
import os
import subprocess
import unittest

from setuplib import core
from tests.helpers import ROOT, Case, git, git_repo, snapshot, workspace_cli

SPEC = next(c for c in core.load_spec()["components"] if c["name"] == "githooks")
DIR = SPEC["dir"]
FAKE_CHECKS = ROOT / "tests" / "fake_checks.py"
RECORDS = "#!/usr/bin/env bash\n# the repo's check: gates elided\n" + SPEC["record"] + "\n"


class Base(Case):
    def setUp(self):
        super().setUp()
        self.env.pop("CLAUDECODE", None)  # each commit below says whether it is a session's
        self.checks_spec = self.tmp / "checks.json"
        self.ok_secrets()
        self.env["FAKE_CHECKS"] = str(self.checks_spec)
        self.env["FAKE_CHECKS_LOG"] = str(self.tmp / "checks.log")

    def ok_secrets(self, status="ok", raw=None):
        doc = {"gates": [], "results": [], "one": [{"check": "no-secrets", "status": status,
                                                    "lines": [] if status == "ok" else ["x.env: a *.env file"]}]}
        if raw is not None:
            doc["raw"] = raw
        self.checks_spec.write_text(json.dumps(doc))

    def source(self, stamp=True, ledger=True):
        """A hook source registering the stamp and ledger hooks (or not)."""
        src = self.tmp / f"src-{stamp}-{ledger}"
        (src / "hooks").mkdir(parents=True, exist_ok=True)
        pre, post = [], []
        for name, want, groups in (("git-stamp.sh", stamp, pre), ("write-ledger.sh", ledger, post)):
            (src / "hooks" / name).write_text("#!/bin/sh\nexit 0\n")
            os.chmod(src / "hooks" / name, 0o755)
            if want:
                groups.append({"hooks": [{"type": "command",
                                          "command": f"$CLAUDE_PROJECT_DIR/.claude/hooks/{name}"}]})
        pre and pre[0].update({"matcher": "Bash"})
        post and post[0].update({"matcher": "Write|Edit|Bash"})
        hooks = {k: v for k, v in (("PreToolUse", pre), ("PostToolUse", post)) if v}
        (src / "settings.json").write_text(json.dumps({"hooks": hooks}, indent=2) + "\n")
        return src

    def ready_repo(self, name="r", dev=RECORDS, wired=True, src=None):
        """An existing repo whose check records its pass and whose settings run the stamp."""
        src = src or self.source()
        repo = git_repo(self.tmp / name)
        (repo / "dev.sh").write_text(dev)
        os.chmod(repo / "dev.sh", 0o755)
        if wired:
            (repo / ".claude").mkdir(exist_ok=True)
            (repo / ".claude/settings.json").write_text((src / "settings.json").read_text())
        return repo, src

    def setup(self, name, src, *extra, checks=True):
        args = [name, "--hooks-from", str(src), *extra]
        if checks:
            args += ["--checks", str(FAKE_CHECKS)]
        return self.run_json(*args)

    def hooks_path(self, repo):
        return git(["config", "--get", "core.hooksPath"], repo).stdout.strip() or None


class Install(Base):
    def test_a_ready_repo_gets_the_hooks_and_core_hooks_path(self):
        repo, src = self.ready_repo()
        code, res = self.setup("r", src)
        line = res["githooks"]
        self.assertEqual(line["status"], "installed", line)
        for f in SPEC["files"]:
            self.assertEqual((repo / DIR / f).read_bytes(), (ROOT / SPEC["templates"] / f).read_bytes())
            self.assertTrue(os.access(repo / DIR / f, os.X_OK), f)
        self.assertEqual(self.hooks_path(repo), DIR)
        self.assertEqual(git(["config", "--get", SPEC["config"]], repo).stdout.strip(), str(FAKE_CHECKS))
        self.assertIn("the gates are on", line["detail"])
        # a second run changes nothing
        before = snapshot(repo)
        _, res = self.setup("r", src)
        self.assertEqual(res["githooks"]["status"], "unchanged", res["githooks"])
        self.assertEqual(snapshot(repo), before)

    def test_a_dry_run_writes_nothing_and_says_what_it_would(self):
        repo, src = self.ready_repo()
        before = snapshot(repo)
        _, res = self.setup("r", src, "--dry-run")
        self.assertEqual(snapshot(repo), before)
        self.assertEqual(res["githooks"]["status"], "installed", res["githooks"])
        self.assertIn("would set core.hooksPath", res["githooks"]["detail"])
        self.assertIsNone(self.hooks_path(repo))

    def test_a_new_repo_commits_the_hooks_and_leaves_them_off(self):
        src = self.source()
        _, res = self.setup("fresh", src)
        repo = self.tmp / "fresh"
        self.assertEqual(res["githooks"]["status"], "installed", res["githooks"])
        tracked = set(git(["ls-files"], repo).stdout.split())
        self.assertTrue({f"{DIR}/{f}" for f in SPEC["files"]} <= tracked, tracked)
        self.assertIsNone(self.hooks_path(repo))
        self.assertIn("stub check", res["githooks"]["detail"])
        # the stub records nothing, so a later run still leaves them off, and says why
        _, res = self.setup("fresh", src)
        self.assertEqual(res["githooks"]["status"], "needs-owner", res["githooks"])
        self.assertIn(SPEC["record"], res["githooks"]["detail"])
        self.assertIsNone(self.hooks_path(repo))

    def unready(self, repo, src, want, text, checks=True):
        _, res = self.setup(repo.name, src, checks=checks)
        line = res["githooks"]
        self.assertEqual(line["status"], want, line)
        self.assertIn(text, line["detail"])
        self.assertIsNone(self.hooks_path(repo), "core.hooksPath set though commits would be refused")

    def test_a_check_that_does_not_record_its_pass_leaves_them_off(self):
        repo, src = self.ready_repo(dev="#!/usr/bin/env bash\necho checked\n")
        self.unready(repo, src, "needs-owner", f"does not run `{SPEC['record']}`")

    def test_no_checks_cli_leaves_them_off(self):
        repo, src = self.ready_repo()
        self.unready(repo, src, "needs-owner", "no runnable checks CLI", checks=False)

    def test_a_checks_cli_that_is_not_executable_fails(self):
        repo, src = self.ready_repo()
        _, res = self.run_json("r", "--hooks-from", str(src), "--checks", str(self.tmp / "nope"))
        self.assertEqual(res["githooks"]["status"], "failed", res["githooks"])
        self.assertIsNone(self.hooks_path(repo))

    def test_an_unregistered_stamp_is_needs_jacob_and_leaves_them_off(self):
        repo, src = self.ready_repo(wired=False)
        self.unready(repo, src, "needs-jacob", "git-stamp.sh is not registered")
        self.assertIn("settings do not run git-stamp.sh", self.setup("r", src)[1]["githooks"]["detail"])

    def test_an_unregistered_ledger_is_needs_jacob_but_the_gates_go_on(self):
        # only the stamp is needed for a commit to pass; the ledger is reported
        full = self.source()
        repo, _ = self.ready_repo(src=self.source(ledger=False))
        _, res = self.setup("r", full)
        self.assertEqual(res["githooks"]["status"], "needs-jacob", res["githooks"])
        self.assertIn("write-ledger.sh (not in .claude/settings.json)", res["githooks"]["detail"])
        self.assertEqual(self.hooks_path(repo), DIR)

    def test_a_source_that_registers_no_stamp_is_never_wired(self):
        repo, _ = self.ready_repo()
        self.unready(repo, self.source(stamp=False), "needs-jacob", "registers none")

    def test_user_scope_running_the_stamp_counts(self):
        repo, src = self.ready_repo(wired=False)
        rows = [{"file": f".claude/hooks/{n}", "kind": "source", "registered": True, "test": None}
                for n in SPEC["hooks"]]
        rep = self.tmp / "copies.json"
        rep.write_text(json.dumps({"user_scope": {"exists": True, "error": None, "hooks": rows}}))
        _, res = self.setup("r", src, "--user-scope", str(rep))
        self.assertNotIn("settings do not run", res["githooks"]["detail"])
        self.assertEqual(self.hooks_path(repo), DIR)

    def test_a_hook_in_the_default_folder_is_never_switched_off(self):
        repo, src = self.ready_repo()
        own = repo / ".git/hooks/pre-commit"
        own.write_text("#!/bin/sh\nexit 0\n")
        os.chmod(own, 0o755)
        self.unready(repo, src, "needs-owner", "would be switched off")

    def test_another_hooks_path_is_drift_never_overridden(self):
        repo, src = self.ready_repo()
        git(["config", "core.hooksPath", "elsewhere"], repo)
        code, res = self.setup("r", src)
        self.assertEqual((code, res["githooks"]["status"]), (1, "drift"), res["githooks"])
        self.assertEqual(self.hooks_path(repo), "elsewhere")

    def test_a_global_hooks_path_is_drift_never_shadowed(self):
        repo, src = self.ready_repo()
        glob = self.tmp / "global.gitconfig"
        glob.write_text("[core]\n\thooksPath = /somewhere/hooks\n")
        self.env["GIT_CONFIG_GLOBAL"] = str(glob)
        code, res = self.setup("r", src)
        self.assertEqual((code, res["githooks"]["status"]), (1, "drift"), res["githooks"])
        self.assertIn("/somewhere/hooks", res["githooks"]["detail"])
        self.assertIsNone(git(["config", "--local", "--get", "core.hooksPath"], repo).stdout.strip() or None)

    def test_a_changed_hook_is_drift_and_kept(self):
        repo, src = self.ready_repo()
        (repo / DIR).mkdir()
        (repo / DIR / "commit-msg").write_text("#!/bin/sh\nexit 0\n")
        os.chmod(repo / DIR / "commit-msg", 0o755)
        code, res = self.setup("r", src)
        self.assertEqual((code, res["githooks"]["status"]), (1, "drift"), res["githooks"])
        self.assertEqual((repo / DIR / "commit-msg").read_text(), "#!/bin/sh\nexit 0\n")
        self.assertIsNone(self.hooks_path(repo))

    def test_active_with_a_check_that_stopped_recording_is_drift(self):
        repo, src = self.ready_repo()
        self.setup("r", src)
        self.assertEqual(self.hooks_path(repo), DIR)
        (repo / "dev.sh").write_text("#!/usr/bin/env bash\necho checked\n")
        code, res = self.setup("r", src)
        self.assertEqual((code, res["githooks"]["status"]), (1, "drift"), res["githooks"])
        self.assertIn("every commit is refused", res["githooks"]["detail"])


class Hooks(Base):
    """The hooks themselves, in an activated fixture repo."""

    def setUp(self):
        super().setUp()
        self.repo, src = self.ready_repo()
        _, res = self.setup("r", src)
        self.assertEqual(self.hooks_path(self.repo), DIR, res["githooks"])
        git(["add", "-A"], self.repo)
        r = git(["commit", "-q", "--no-verify", "-m", "base"], self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)

    def sh(self, argv, session=False, **kw):
        env = dict(self.env)
        if session:
            env["CLAUDECODE"] = "1"
        return subprocess.run(argv, cwd=self.repo, env=env, capture_output=True, text=True, **kw)

    def record(self, *args):
        return self.sh([f"{DIR}/check-pass", "record", *args])

    def change(self, text="x\n", rel="file.txt", stage=True):
        (self.repo / rel).write_text(text)
        if stage:
            git(["add", rel], self.repo)

    def commit(self, *extra, session=False):
        return self.sh(["git", "commit", "-q", "-m", "a change", *extra], session=session)

    def last(self):
        return git(["log", "-1", "--format=%B"], self.repo).stdout

    def trailers(self, key):
        r = git(["log", "-1", "--format=%(trailers:key=" + key + ",valueonly)"], self.repo)
        return [x for x in r.stdout.splitlines() if x]

    # -- commit-msg: who made it (§2, §8 answer 2)

    def test_in_a_session_an_unstamped_commit_is_refused(self):
        self.change()
        self.assertEqual(self.record().returncode, 0)
        r = self.commit(session=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("carries no Agent: trailer", r.stderr)
        self.assertEqual(git(["rev-list", "--count", "HEAD"], self.repo).stdout.strip(), "2")

    def test_in_a_session_a_stamped_commit_passes_and_keeps_its_stamp(self):
        self.change()
        self.record()
        r = self.commit("--trailer", "Agent: site-x", "--trailer", "Agent-Id: a1", session=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.trailers("Agent"), ["site-x"])

    def test_in_a_session_agent_jacob_is_refused(self):
        self.change()
        self.record()
        r = self.commit("--trailer", "Agent: jacob", session=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("only Jacob's own terminal commits", r.stderr)

    def test_outside_a_session_the_commit_is_stamped_jacob(self):
        self.change()
        self.record()
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.trailers("Agent"), ["jacob"])

    def test_outside_a_session_an_existing_stamp_is_kept(self):
        self.change()
        self.record()
        self.assertEqual(self.commit("--trailer", "Agent: site-x").returncode, 0)
        self.assertEqual(self.trailers("Agent"), ["site-x"])

    # -- pre-commit: the check pass (§3 row 3, §6)

    def test_no_recorded_pass_is_refused(self):
        (self.repo / ".claude/state/check-pass").unlink(missing_ok=True)
        self.change()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no check pass recorded", r.stderr)

    def test_an_edit_after_the_pass_is_refused_and_a_fresh_pass_accepted(self):
        self.change("one\n")
        self.record()
        self.change("two\n")
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("is not the one ./dev.sh check passed", r.stderr)
        r = self.record()
        self.assertEqual(r.returncode, 0, r.stderr)
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.trailers("check"), ["full"])

    def test_a_change_the_pass_saw_left_unstaged_is_refused(self):
        # strict on purpose: the commit must be exactly what was checked
        self.change("staged\n")
        self.change("not staged\n", rel="other.txt", stage=False)
        self.record()
        self.assertNotEqual(self.commit().returncode, 0)

    def test_the_hooks_state_folder_is_not_part_of_the_tree(self):
        # the ledger and the record itself change after a pass; they never stale it,
        # even where .gitignore does not cover the folder (check-pass's own exclusion)
        gi = self.repo / ".gitignore"
        gi.write_text("".join(l for l in gi.read_text().splitlines(True) if ".claude/state" not in l))
        self.change()
        git(["add", ".gitignore"], self.repo)
        (self.repo / ".claude/state").mkdir(parents=True, exist_ok=True)
        (self.repo / ".claude/state/writes.tsv").write_text("a row\n")  # the ledger, never staged
        self.assertEqual(self.record().returncode, 0)
        (self.repo / ".claude/state/writes.tsv").write_text("a row\nanother\n")
        r = self.commit()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_tree_that_changed_during_the_check_is_not_recorded(self):
        before = self.sh([f"{DIR}/check-pass", "tree"]).stdout.strip()
        self.change()
        r = self.record("--from", before)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("changed while the check ran", r.stderr)
        self.assertNotEqual(self.commit().returncode, 0)
        now = self.sh([f"{DIR}/check-pass", "tree"]).stdout.strip()
        self.assertEqual(self.record("--from", now).returncode, 0)
        self.assertEqual(self.commit().returncode, 0)

    # -- commit-msg: what checked it (PLAN-check-progress §9.2)

    def test_a_resumed_pass_is_findable_from_the_log_alone(self):
        self.change("one\n")
        self.record("--resumed-from", "14/27")
        self.assertEqual(self.commit().returncode, 0)
        resumed = git(["rev-parse", "HEAD"], self.repo).stdout.strip()
        self.assertEqual(len(self.trailers("check")), 1)
        self.assertTrue(self.trailers("check")[0].startswith("resumed from 14/27 (tree "), self.last())
        self.change("two\n")
        self.record()
        self.assertEqual(self.commit().returncode, 0)
        self.assertEqual(self.trailers("check"), ["full"])
        found = git(["log", "--format=%H", "--grep", "check: resumed"], self.repo).stdout.split()
        self.assertEqual(found, [resumed])

    def test_a_commit_of_an_unchecked_tree_says_none(self):
        # the merge path: commit-msg runs without pre-commit; it never claims a check
        self.change("one\n")
        self.record()
        self.change("two\n")
        msg = self.tmp / "msg"
        msg.write_text("a merge\n\ncheck: full\n")
        r = self.sh([f"{DIR}/commit-msg", str(msg)])
        self.assertEqual(r.returncode, 0, r.stderr)
        body = msg.read_text()
        self.assertIn("check: none (tree ", body)
        self.assertNotIn("check: full", body)
        self.assertIn("Agent: jacob", body)

    def test_a_bad_resumed_from_records_nothing(self):
        self.change()
        r = self.record("--resumed-from", "most")
        self.assertEqual(r.returncode, 2)
        self.assertNotEqual(self.commit().returncode, 0)

    # -- pre-commit: no-secrets (§3 row 6)

    def test_no_secrets_failing_is_refused(self):
        self.ok_secrets("fail")
        self.change()
        self.record()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no-secrets is fail", r.stderr)
        self.assertIn("x.env", r.stderr)

    def test_no_secrets_unreadable_is_refused(self):
        # not JSON, JSON of another shape, and a report of another check: none is a pass
        for raw in ("not json", json.dumps({"results": []}),
                    json.dumps({"results": [{"check": "other", "status": "ok", "lines": []}]})):
            with self.subTest(raw=raw):
                self.ok_secrets(raw=raw)
                self.change(raw)
                self.record()
                r = self.commit()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("no-secrets is unreadable", r.stderr)

    def test_no_checks_cli_configured_is_refused(self):
        git(["config", "--unset", SPEC["config"]], self.repo)
        self.change()
        self.record()
        r = self.commit()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no runnable shared checks CLI", r.stderr)

    def test_the_pre_commit_asks_for_no_secrets_on_this_repo(self):
        self.change()
        self.record()
        self.assertEqual(self.commit().returncode, 0)
        calls = [json.loads(x)["argv"] for x in (self.tmp / "checks.log").read_text().splitlines()]
        self.assertIn(["one", "no-secrets", str(self.repo), "--json"], calls)


class LiveNoSecrets(Base):
    """The pre-commit reads `one no-secrets <top> --json` from the real shared checks
    CLI: a clean repo commits, one tracking a .env is refused. Skipped in a lone clone."""

    def setUp(self):
        super().setUp()
        _, self.cli = workspace_cli("checks")
        if self.cli is None:
            raise unittest.SkipTest("no shared checks CLI around this clone")

    def test_the_real_report_is_read(self):
        repo, src = self.ready_repo()
        _, res = self.run_json("r", "--hooks-from", str(src), "--checks", str(self.cli))
        self.assertEqual(self.hooks_path(repo), DIR, res["githooks"])
        git(["add", "-A"], repo)
        git(["commit", "-q", "--no-verify", "-m", "base"], repo)

        def attempt(rel):
            (repo / rel).write_text("x\n")
            git(["add", "-f", rel], repo)
            subprocess.run([f"{DIR}/check-pass", "record"], cwd=repo, env=self.env, capture_output=True)
            return subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=repo, env=self.env,
                                  capture_output=True, text=True)

        r = attempt("plain.txt")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = attempt("local.env")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no-secrets is fail", r.stderr)
