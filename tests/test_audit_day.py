"""`setup audit-day` (PLAN-check-progress.md §13 step 4): each repo with commits since
its last audit gets the full check once, the range and each part's result recorded,
failures filed through todo detect. The plan's gates: an unchanged repo is skipped; a
repo with two new commits is audited once, over both; a failing part becomes one item
that names the range (live: the real store CLI, a fixture detector list). Plus a held
full-run lock and a progress file that is not this run's --full record (never read as
a result), a record path git does not ignore, the dry run, and the statuses
documented == emitted.

The fixture repos run the shared runner itself (the parts dependency's source, which
must know --full), so the progress file read is the real runner's, not a copy of its
shape."""
import fcntl
import json
import os
import re
import unittest

from setuplib import core
from tests.helpers import ROOT, SETUP, Case, commit_all, git, git_repo, workspace_cli

AD = core.load_spec()["audit_day"]
_, TODO = workspace_cli("todo")


def runner_source():
    """The parts runner setup renders, when it is there and knows --full; else None."""
    src, _, _ = core.Setup(ROOT, label=".", name="t", dry_run=True)._runner_source("parts")
    if src is None or "--full" not in src.read_text():
        return None
    return src


RUNNER = runner_source()

PART = """#!/bin/sh
echo "$1" >> "$AD_PARTS_LOG"
if [ "$1" = "${AD_FAIL:-}" ]; then echo "FAIL $1: the planted failure"; exit 1; fi
exit 0
"""
DEV = """#!/bin/sh
echo run >> "$AD_RUNS"
[ "$1" = check ] || exit 2
shift
[ -n "${AD_DROP_FULL:-}" ] && set --
exec python3 devtools/parts.py run check.parts.json "$@"
"""


@unittest.skipIf(RUNNER is None, "no parts runner source that knows --full (a lone clone, or the runner is older)")
class Base(Case):
    def setUp(self):
        super().setUp()
        self.ws = self.tmp / "ws"
        self.ws.mkdir()
        (self.ws / "CLAUDE.md").write_text("# fixture workspace\n")
        self.runs, self.plog = self.tmp / "runs.log", self.tmp / "parts.log"
        self.env.update({"AD_RUNS": str(self.runs), "AD_PARTS_LOG": str(self.plog),
                         "PARTS_FULL_LOCK": str(self.tmp / "full.lock")})
        for k in ("PROGRESS_FILE", "CHECK_PARTS", "AD_FAIL", "AD_DROP_FULL", "TODO_DETECTORS"):
            self.env.pop(k, None)

    def repo(self, name, ignore=".progress/\n"):
        r = git_repo(self.ws / name)
        (r / "devtools").mkdir()
        (r / "devtools" / "parts.py").write_bytes(RUNNER.read_bytes())
        (r / "check.parts.json").write_text(json.dumps({"parts": [
            {"name": n, "run": f"./p.sh {n}", "files": ["p.sh"], "timeout_s": 60} for n in ("a", "b")]}))
        for f, body in (("p.sh", PART), ("dev.sh", DEV)):
            (r / f).write_text(body)
            (r / f).chmod(0o755)
        (r / ".gitignore").write_text(ignore)
        commit_all(r, "the fixture repo")
        return r

    def commit(self, r, n):
        for i in range(n):
            (r / "work.txt").write_text(f"{i}\n" + ((r / "work.txt").read_text() if (r / "work.txt").exists() else ""))
            commit_all(r, f"work {i}")
        return self.head(r)

    def head(self, r):
        return git(["rev-parse", "HEAD"], r).stdout.strip()

    def audit(self, *args, code=None):
        r = self.run_setup("audit-day", "--json", *args, cwd=self.ws)
        if code is not None:
            self.assertEqual(r.returncode, code, r.stdout[-800:] + r.stderr[-800:])
        doc = json.loads(r.stdout)
        return r.returncode, {x["path"]: x for x in doc["repos"]}, doc

    def count(self):
        return len(self.runs.read_text().splitlines()) if self.runs.exists() else 0

    def record(self, r):
        p = r / AD["record"]
        return json.loads(p.read_text()) if p.exists() else None


class Gates(Base):
    def test_an_unchanged_repo_is_skipped(self):
        r = self.repo("r")
        _, out, _ = self.audit(code=0)
        self.assertEqual((out["r"]["status"], self.count()), ("passed", 1), out)
        before = (r / AD["record"]).read_bytes()
        _, out, _ = self.audit(code=0)
        self.assertEqual(out["r"]["status"], "unchanged", out)
        self.assertEqual(self.count(), 1, "the check ran for a repo with no new commit")
        self.assertEqual((r / AD["record"]).read_bytes(), before)
        # the counterfactual: one commit, and it runs again
        c1 = self.commit(r, 1)
        _, out, _ = self.audit(code=0)
        self.assertEqual((out["r"]["status"], self.count()), ("passed", 2), out)
        self.assertEqual(self.record(r)["audited"]["to"], c1)

    def test_two_new_commits_are_audited_once_over_both(self):
        r = self.repo("r")
        self.audit(code=0)
        c0 = self.head(r)
        c2 = self.commit(r, 2)
        self.plog.unlink()
        _, out, _ = self.audit(code=0)
        self.assertEqual(self.count(), 2, "one run for the first audit, exactly one for both new commits")
        self.assertEqual(sorted(self.plog.read_text().split()), ["a", "b"], "each part once")
        rec = self.record(r)
        self.assertEqual(rec["audited"], {"from": c0, "to": c2, "commits": 2})
        self.assertEqual(out["r"]["range"], rec["audited"])
        self.assertEqual(rec["result"], "passed")
        self.assertEqual([(p["name"], p["result"]) for p in rec["parts"]], [("a", "passed"), ("b", "passed")])
        self.assertTrue(all(isinstance(p["s"], float) for p in rec["parts"]), rec["parts"])
        self.assertIn(f"{c0[:12]}..{c2[:12]} (2 commits)", out["r"]["detail"])

    @unittest.skipIf(TODO is None, "no store CLI beside this tool (a lone clone)")
    def test_a_failing_part_becomes_one_item_that_names_the_range(self):
        r = self.repo("r")
        # detect runs from the root's own store (the workspace top's); the finding is filed in r's
        for where, prefix, repo in ((self.ws, "ws", "ws"), (r, "rr", "r")):
            init = self.cli(TODO, "-C", where, "--root", self.ws, "init", "--prefix", prefix, "--repo", repo)
            self.assertEqual(init.returncode, 0, init.stderr)
        commit_all(r, "the store")
        dets = self.tmp / "dets.json"
        dets.write_text(json.dumps([{"id": AD["detector"], "doc": "fixture: setup audit-day's findings",
                                     "command": [str(SETUP), "audit-day", "--findings", "--root", "{root}",
                                                 "--todo", "{todo}"],
                                     "kind": "stall", "waits_on": None, "cadence_hours": 24, "audits": "steps"}]))
        self.env["TODO_DETECTORS"] = str(dets)
        self.audit("--todo", str(TODO), code=0)
        c0 = self.head(r)
        self.assertEqual(self.items(r), [], "a green audit files nothing")
        c2 = self.commit(r, 2)
        self.env["AD_FAIL"] = "b"
        _, out, doc = self.audit("--todo", str(TODO), code=0)
        self.assertEqual(out["r"]["status"], "red", out)
        self.assertTrue(doc["filed"]["ok"], doc["filed"])
        items = self.items(r)
        self.assertEqual([i["detector"]["subject"] for i in items], ["full part b failed"], items)
        self.assertIn(f"{c0[:12]}..{c2[:12]} (2 commits)", items[0]["evidence"])
        # filed again (the record unchanged): still one item, not two
        _, out, doc = self.audit("--todo", str(TODO), code=0)
        self.assertEqual(out["r"]["status"], "unchanged")
        self.assertEqual(len(self.items(r)), 1, self.items(r))

    def cli(self, *argv):
        import subprocess
        return subprocess.run([str(a) for a in argv], capture_output=True, text=True, env=self.env, timeout=300)

    def items(self, r):
        """The audit-day detector's open items r's store lists; each must sit in r's own
        store (and the workspace top's store holds none: filed by repo, not where
        detect ran)."""
        top = self.cli(TODO, "-C", self.ws, "--root", self.ws, "list", "--json")
        self.assertEqual(top.returncode, 0, top.stderr)
        self.assertEqual([i for i in json.loads(top.stdout)["items"] if i["record"].get("detector")], [])
        res = self.cli(TODO, "-C", r, "--root", self.ws, "list", "--json")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = [i for i in json.loads(res.stdout)["items"]
               if (i["record"].get("detector") or {}).get("id") == AD["detector"]]
        self.assertEqual({i["store"] for i in out} - {str(r)}, set(), "filed outside r's store")
        return [i["record"] for i in out]


class NotRun(Base):
    def test_a_held_lock_runs_nothing_and_keeps_the_range(self):
        r = self.repo("r")
        self.audit(code=0)
        c0 = self.head(r)
        c1 = self.commit(r, 1)
        fd = os.open(self.env["PARTS_FULL_LOCK"], os.O_RDWR | os.O_CREAT)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _, out, _ = self.audit(code=1)
        finally:
            os.close(fd)
        self.assertEqual(out["r"]["status"], "not-run", out)
        self.assertIn("exit 3", out["r"]["detail"])
        rec = self.record(r)
        self.assertEqual(rec["audited"]["to"], c0, "a run that audited nothing advanced the range")
        self.assertEqual(rec["last"]["status"], "not-run")
        _, out, _ = self.audit(code=0)
        self.assertEqual((out["r"]["status"], self.record(r)["audited"]), ("passed", {"from": c0, "to": c1, "commits": 1}))

    def test_a_run_without_full_is_never_read_as_the_audit(self):
        r = self.repo("r")
        self.env["AD_DROP_FULL"] = "1"
        _, out, _ = self.audit(code=1)
        self.assertEqual(out["r"]["status"], "not-run", out)
        self.assertIn("not a --full run's", out["r"]["detail"])
        self.assertNotIn("audited", self.record(r))

    def test_a_record_git_does_not_ignore_is_never_written(self):
        r = self.repo("r", ignore="")
        _, out, _ = self.audit(code=1)
        self.assertEqual(out["r"]["status"], "not-run", out)
        self.assertIn("git does not ignore", out["r"]["detail"])
        self.assertEqual((self.count(), self.record(r)), (0, None))

    def test_dry_run_runs_and_writes_nothing(self):
        r = self.repo("r")
        _, out, _ = self.audit("--dry-run", code=0)
        self.assertEqual(out["r"]["status"], "would-run", out)
        self.assertEqual((self.count(), self.record(r)), (0, None))


class Vocabulary(Case):
    def test_statuses_documented_equal_emitted(self):
        src = (ROOT / "setuplib" / "auditday.py").read_text()
        emitted = set(re.findall(r'Outcome\(label, "([a-z-]+)"', src)) | set(re.findall(r'keep\("([a-z-]+)"', src))
        emitted |= set(re.search(r'result = "([a-z-]+)" if .* else "([a-z-]+)"', src).groups())
        self.assertEqual(sorted(emitted), sorted(AD["statuses"]))

    def test_findings_wants_the_store_cli(self):
        r = self.run_setup("audit-day", "--findings")
        self.assertEqual(r.returncode, 2)
        self.assertIn("--todo CLI", r.stderr)
