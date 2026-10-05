"""The hooks component and user scope: a shared hook the user settings already run
(in place, from its one source) is neither copied into the repo nor registered in
its settings proposal, or it would run twice; the hooks line says
"covered by user scope: <files>".

The input is the JSON the shared hooks source prints for its copies (`hooks copies
<top> --json`), given with --user-scope FILE; setup reads only its `user_scope`
object and never the user settings themselves. The coverage rule is the one the
shared checks' hooks-installed reads from the same report: a hook is covered when
every `kind: source` row naming it (as `file`, or as its `test`) has `registered:
true`. `registered: null` or a `user_scope.error` is unknown, never covered; a
missing user settings file is not covered, never an error."""
import json
import os
import subprocess
import unittest
from pathlib import Path

from tests.helpers import ROOT, Case, git_repo

SRC = ROOT / ".claude/hooks"
HOOKS = sorted(p.name for p in SRC.glob("*.sh") if not p.name.startswith("test-"))
BLOBS = "no-inline-blobs.sh"


def row(name, registered, kind="source"):
    return {"file": f".claude/hooks/{name}", "kind": kind, "test": f".claude/hooks/test-{name}",
            "event": "PreToolUse", "matcher": "Bash", "command": f"/src/hooks/{name}",
            "registered": registered}


class UserScope(Case):
    def report(self, registered=None, exists=True, error=None, rows=None, **override):
        """A `hooks copies --json` report whose user_scope registers `registered`
        ({hook name: true|false|null}); every other shared hook is registered: false."""
        registered = registered or {}
        if rows is None:
            rows = [row(n, registered.get(n, False)) for n in HOOKS]
        us = {"settings": "/home/u/.claude/settings.json", "exists": exists, "error": error,
              "source": "/src", "ok": False, "hooks": rows, "left_per_repo": []}
        us.update(override)
        f = self.tmp / f"copies-{len(list(self.tmp.glob('copies-*')))}.json"
        f.write_text(json.dumps({"root": "/ws", "ok": False, "locations": [], "unresolved": [],
                                 "user_scope": us}))
        return str(f)

    def copies(self, repo):
        d = repo / ".claude/hooks"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def proposed(self, repo):
        f = repo / ".claude/settings.proposed.json"
        if not f.exists():
            return None
        prop = json.loads(f.read_text())
        return sorted(h["command"].rsplit("/", 1)[1] for groups in prop.get("hooks", {}).values()
                      for g in groups for h in g.get("hooks", []))

    def per_repo_settings(self, repo):
        """The repo's settings.json as setup's own proposal would make it today (every
        shared hook registered per repo), plus a setting of the owner's."""
        (repo / ".claude").mkdir(exist_ok=True)
        own = json.loads((repo / ".claude/settings.proposed.json").read_text())
        own["permissions"] = {"allow": ["Bash(ls:*)"]}
        (repo / ".claude/settings.json").write_text(json.dumps(own))
        (repo / ".claude/settings.proposed.json").unlink()
        return own

    # ---- covered vs not: the input changes the output -----------------------

    def test_covered_hook_is_neither_copied_nor_proposed_and_the_line_says_so(self):
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--user-scope", self.report({BLOBS: True}))
        self.assertNotIn(BLOBS, self.copies(repo))
        self.assertNotIn(f"test-{BLOBS}", self.copies(repo))
        others = [n for n in HOOKS if n != BLOBS]
        self.assertTrue(others)
        for n in others:
            self.assertIn(n, self.copies(repo))
        self.assertEqual(self.proposed(repo), others)
        self.assertIn(f"covered by user scope: {BLOBS}, test-{BLOBS}", res["hooks"]["detail"])
        self.assertNotEqual(res["hooks"]["status"], "failed")

    def test_not_covered_is_unchanged_behaviour(self):
        # counterfactual of the test above: the same report with registered: false
        plain = git_repo(self.tmp / "plain")
        _, base = self.run_json("plain")
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--user-scope", self.report({BLOBS: False}))
        self.assertEqual(self.copies(repo), self.copies(plain))
        self.assertIn(BLOBS, self.copies(repo))
        self.assertEqual(self.proposed(repo), self.proposed(plain))
        self.assertIn(BLOBS, self.proposed(repo))
        self.assertEqual(res["hooks"]["status"], base["hooks"]["status"])
        self.assertNotIn("covered by user scope:", res["hooks"]["detail"])

    def test_without_the_report_user_scope_is_not_checked_and_said(self):
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r")
        self.assertIn(BLOBS, self.copies(repo))
        self.assertIn("user scope not checked", res["hooks"]["detail"])

    def test_every_hook_covered_writes_no_copy_and_no_proposal(self):
        repo = git_repo(self.tmp / "r")
        code, res = self.run_json("r", "--user-scope", self.report({n: True for n in HOOKS}))
        self.assertEqual(self.copies(repo), [])
        self.assertIsNone(self.proposed(repo))
        self.assertEqual(res["hooks"]["status"], "unchanged")

    # ---- unknown is never covered ----------------------------------------------

    def test_registered_null_is_unknown_never_covered(self):
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--user-scope", self.report({BLOBS: None}))
        self.assertIn(BLOBS, self.copies(repo))
        self.assertIn(BLOBS, self.proposed(repo))
        self.assertIn("could not tell", res["hooks"]["detail"])
        self.assertNotIn("covered by user scope:", res["hooks"]["detail"])

    def test_user_scope_error_is_unknown_never_covered(self):
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--user-scope", self.report({BLOBS: True}, error="settings.json does not parse"))
        self.assertIn(BLOBS, self.copies(repo))
        self.assertIn("could not tell", res["hooks"]["detail"])
        self.assertIn("does not parse", res["hooks"]["detail"])

    def test_missing_user_settings_is_not_covered_and_not_an_error(self):
        repo = git_repo(self.tmp / "r")
        code, res = self.run_json("r", "--user-scope", self.report({BLOBS: True}, exists=False))
        self.assertIn(BLOBS, self.copies(repo))
        self.assertNotEqual(res["hooks"]["status"], "failed")
        self.assertIn("no user settings file", res["hooks"]["detail"])

    def test_one_row_not_registered_means_not_covered(self):
        # two source rows for one file (two events): both must register it
        repo = git_repo(self.tmp / "r")
        rows = [row(n, n == BLOBS) for n in HOOKS] + [row(BLOBS, False)]
        self.run_json("r", "--user-scope", self.report(rows=rows))
        self.assertIn(BLOBS, self.copies(repo))

    def test_a_plugin_row_does_not_cover_a_shared_hook(self):
        repo = git_repo(self.tmp / "r")
        rows = [row(n, False) for n in HOOKS if n != BLOBS] + [row(BLOBS, True, kind="plugin")]
        self.run_json("r", "--user-scope", self.report(rows=rows))
        self.assertIn(BLOBS, self.copies(repo))

    def test_malformed_report_fails_and_covers_nothing(self):
        repo = git_repo(self.tmp / "r")
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps({"locations": []}))
        code, res = self.run_json("r", "--user-scope", str(bad))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertIn(BLOBS, self.copies(repo))
        self.assertIn("user_scope", res["hooks"]["detail"])
        rows = [row(n, "yes") for n in HOOKS]  # registered must be true|false|null
        code, res = self.run_json("r", "--user-scope", self.report(rows=rows))
        self.assertEqual(res["hooks"]["status"], "failed")

    def test_unreadable_report_fails(self):
        git_repo(self.tmp / "r")
        (self.tmp / "bad.json").write_text("{not json")
        code, res = self.run_json("r", "--user-scope", str(self.tmp / "bad.json"))
        self.assertEqual((code, res["hooks"]["status"]), (1, "failed"))
        self.assertIn("unreadable", res["hooks"]["detail"])

    # ---- existing per-repo copies and registrations -----------------------------

    def test_existing_copy_of_a_covered_hook_is_kept_and_its_registration_dropped_from_the_proposal(self):
        repo = git_repo(self.tmp / "r")
        self.run_json("r")  # the per-repo baseline as it is today
        own = self.per_repo_settings(repo)
        _, res = self.run_json("r")
        self.assertEqual(res["hooks"]["status"], "unchanged")  # baseline: nothing to propose
        before =(repo / ".claude/hooks" / BLOBS).read_bytes()
        _, res = self.run_json("r", "--user-scope", self.report({BLOBS: True}))
        # the copy is never deleted
        self.assertEqual((repo / ".claude/hooks" / BLOBS).read_bytes(), before)
        # the proposal stops registering it per repo; everything else of the owner's kept
        self.assertEqual(self.proposed(repo), [n for n in HOOKS if n != BLOBS])
        prop = json.loads((repo / ".claude/settings.proposed.json").read_text())
        self.assertEqual(prop["permissions"], own["permissions"])
        self.assertEqual(res["hooks"]["status"], "needs-jacob")
        self.assertIn("runs twice", res["hooks"]["detail"])
        # settings.json itself is Jacob's: untouched
        self.assertEqual(json.loads((repo / ".claude/settings.json").read_text()), own)

    def test_drifted_copy_of_a_covered_hook_is_not_drift_and_is_kept(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        mine = repo / ".claude/hooks" / BLOBS
        mine.write_text("#!/bin/sh\nold\n")
        mine.chmod(0o755)
        code, res = self.run_json("r", "--user-scope", self.report({BLOBS: True}))
        self.assertNotEqual(res["hooks"]["status"], "drift")
        self.assertEqual(mine.read_text(), "#!/bin/sh\nold\n")
        self.assertIn(f"covered by user scope: {BLOBS}", res["hooks"]["detail"])
        # counterfactual: not covered, the same copy is drift
        code, res = self.run_json("r", "--user-scope", self.report({BLOBS: False}))
        self.assertEqual(res["hooks"]["status"], "drift")

    def test_not_executable_copy_of_a_covered_hook_is_still_drift(self):
        repo = git_repo(self.tmp / "r")
        (repo / ".claude/hooks").mkdir(parents=True)
        mine = repo / ".claude/hooks" / BLOBS
        mine.write_bytes((SRC / BLOBS).read_bytes())
        mine.chmod(0o644)
        code, res = self.run_json("r", "--user-scope", self.report({BLOBS: True}))
        self.assertEqual((code, res["hooks"]["status"]), (1, "drift"))
        self.assertIn("not executable", res["hooks"]["detail"])

    def test_dry_run_writes_nothing(self):
        repo = git_repo(self.tmp / "r")
        _, res = self.run_json("r", "--dry-run", "--user-scope", self.report({BLOBS: True}))
        self.assertFalse((repo / ".claude").exists())
        self.assertIn(f"covered by user scope: {BLOBS}", res["hooks"]["detail"])


def workspace_hooks_cli():
    """The shared hooks source's CLI in the workspace around this tool, or None (a lone clone)."""
    for top in ROOT.parents:
        cli = top / "tools" / "hooks" / "hooks"
        if os.access(cli, os.X_OK):
            return top, cli
    return None, None


TOP, HOOKS_CLI = workspace_hooks_cli()


@unittest.skipIf(HOOKS_CLI is None, "no shared hooks CLI in a workspace around this tool (a lone clone)")
class Live(Case):
    """The seam itself: the report the real `hooks copies --json` prints, from user
    settings in a scratch file (never the user's own), read by setup end to end."""

    def report(self, settings):
        r = subprocess.run([str(HOOKS_CLI), "copies", str(TOP), "--json", "--settings", str(settings)],
                           capture_output=True, text=True, env=self.env)
        doc = json.loads(r.stdout)  # exit 1 on any repo's drift; the report is what is read
        f = self.tmp / f"copies-{settings.stem}.json"
        f.write_text(json.dumps(doc))
        return doc["user_scope"], str(f)

    def test_live_report_covered_and_not(self):
        self.env["HOME"] = str(self.tmp)  # nothing here may reach the user's own settings
        empty = self.tmp / "empty.json"
        empty.write_text("{}")
        prop = self.tmp / "proposal.json"
        r = subprocess.run([str(HOOKS_CLI), "userscope", "--out", str(prop), "--settings", str(empty)],
                           capture_output=True, text=True, env=self.env)
        self.assertTrue(prop.exists(), r.stdout + r.stderr)
        us, wired = self.report(prop)
        covered = sorted(Path(h["file"]).name for h in us["hooks"]
                         if h["kind"] == "source" and h["registered"] and Path(h["file"]).name in HOOKS)
        self.assertTrue(covered, us)  # the source's hooks setup installs, by name
        repo = git_repo(self.tmp / "on")
        _, res = self.run_json("on", "--user-scope", wired)
        for n in covered:
            self.assertNotIn(n, [p.name for p in (repo / ".claude/hooks").glob("*.sh")]
                             if (repo / ".claude/hooks").is_dir() else [])
            self.assertIn(n, res["hooks"]["detail"].split("covered by user scope: ", 1)[1])
        # counterfactual: the same tool, user settings registering nothing
        _, unwired = self.report(empty)
        repo = git_repo(self.tmp / "off")
        _, res = self.run_json("off", "--user-scope", unwired)
        for n in covered:
            self.assertTrue((repo / ".claude/hooks" / n).exists())
        self.assertNotIn("covered by user scope:", res["hooks"]["detail"])
