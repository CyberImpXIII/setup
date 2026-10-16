"""`./dev.sh check --json` in the one schema every repo prints (the shared checks
tool holds it, schema/check-json.schema.json): the stub setup installs, and this
repo's own (the shared runner devtools/parts.py over check.parts.json, called by
dev.sh: one check per part).

Anywhere: each output equals its reviewed fixture in tests/fixtures/, and the
exit code agrees with `ok`. In the workspace: the real validator (`check-json`,
run through the shared checks CLI on a scratch repo, as a subprocess) passes
each output, and fails the old `{"ok", "error"}` shape, the counterfactual that
shows it is judging. No copy of the schema or its validator lives here: the
fixtures are what this repo holds, the validator is what proves them."""
import json
import subprocess
import unittest

from tests.helpers import ROOT, Case, git_repo, workspace_cli

FIX = ROOT / "tests" / "fixtures"
_, CHECKS_CLI = workspace_cli("checks")
LONE = "no shared checks CLI in a workspace around this tool (a lone clone)"
# The validator sets this while it runs a repo's suite, and answers UNCHECKED to any
# run nested inside it. Its guard, its decision: a nested run here is skipped, saying so.
GUARD = "CHECKS_CHECK_JSON_ACTIVE"


def fixture(name):
    return json.loads((FIX / name).read_text())


class Live:
    def validate(self, repo):
        """(status, finding lines) of the real check-json on `repo`."""
        r = subprocess.run([str(CHECKS_CLI), "one", "check-json", str(repo), "--json"],
                           capture_output=True, text=True, env=self.env)
        results = json.loads(r.stdout)["results"]
        self.assertEqual([x["check"] for x in results], ["check-json"], r.stdout)
        if results[0]["status"] == "unchecked" and self.env.get(GUARD):
            self.skipTest("nested inside a check-json run, which answers UNCHECKED here by design")
        return results[0]["status"], results[0]["lines"]

    def printing(self, name, text, code):
        """A scratch repo whose `./dev.sh check --json` prints `text` and exits `code`."""
        repo = git_repo(self.tmp / name, commit=False)
        (repo / "payload.json").write_text(text)
        (repo / "dev.sh").write_text("#!/usr/bin/env bash\n# check --json: prints payload.json, canned\n"
                                     f"cat payload.json\nexit {code}\n")
        (repo / "dev.sh").chmod(0o755)
        return repo


class Stub(Case, Live):
    """The stub setup installs: a schema-valid red report until the owner fills it in."""

    def fresh_check(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        r = subprocess.run(["./dev.sh", "check", "--json"], cwd=repo, capture_output=True, text=True)
        return repo, r

    def test_stub_json_is_the_fixture_and_exits_red(self):
        _, r = self.fresh_check()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(len(r.stdout.strip().splitlines()), 1, r.stdout)  # one document, nothing else
        self.assertEqual(json.loads(r.stdout), fixture("stub-check.json"))

    def test_stub_failure_points_at_the_marker(self):
        repo, r = self.fresh_check()
        marker = next(c["stub_marker"] for c in json.loads((ROOT / "components.json").read_text())["components"]
                      if c["name"] == "check")
        (f,) = json.loads(r.stdout)["checks"][0]["failures"]
        lines = (repo / f["file"]).read_text().splitlines()
        self.assertIn(marker, lines[f["line"] - 1])

    @unittest.skipIf(CHECKS_CLI is None, LONE)
    def test_fresh_stub_passes_the_validator_and_the_old_shape_does_not(self):
        repo, _ = self.fresh_check()
        self.assertEqual(self.validate(repo), ("ok", []))
        old = self.printing("old", '{"ok": false, "error": "not implemented: fill in the contract"}\n', 1)
        status, lines = self.validate(old)
        self.assertEqual(status, "fail")
        self.assertIn("schema: $: missing `checks`", lines)


SUITE_PART = """#!/bin/sh
case "$1" in
  p1) echo "  ok    p1" ;;
  p2) echo "FAIL p2.txt:1 the second part is red"; exit 1 ;;
  p3) echo "UNCHECKED: nothing to judge here"; exit 3 ;;
esac
"""
WAIT = 120  # a three-part canned suite: a run past this is a hang (the real suite ran instead)


def suite(tmp):
    """A three-part suite (ok, fail, unchecked) in its own folder, for CHECK_PARTS."""
    d = tmp / "suite"
    d.mkdir()
    (d / "part.sh").write_text(SUITE_PART)
    for p in ("p1", "p2", "p3"):
        (d / f"{p}.txt").write_text(f"{p}\n")
    (d / "parts.json").write_text(json.dumps({"parts": [
        {"name": p, "run": f"sh part.sh {p}", "files": [f"{p}.txt"], "timeout_s": 60} for p in ("p1", "p2", "p3")]}))
    return d


class Own(Case, Live):
    """This repo's own check is the shared runner's (devtools/parts.py over
    check.parts.json): CHECK_PARTS hands it another suite, which is how the shared
    check-partial gate drives it, and how this runs it without running itself."""

    def own(self, *args):
        d = suite(self.tmp)
        env = dict(self.env, CHECK_PARTS=str(d / "parts.json"), PROGRESS_FILE=str(d / "progress.json"))
        return subprocess.run([str(ROOT / "dev.sh"), "check", *args], cwd=ROOT, env=env,
                              capture_output=True, text=True, timeout=WAIT)

    def test_json_is_one_check_per_part(self):
        r = self.own("--json")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertIs(doc["ok"], False)
        self.assertEqual([(c["name"], c["status"]) for c in doc["checks"]],
                         [("p1", "ok"), ("p2", "fail"), ("p3", "unchecked")])
        (f,) = doc["checks"][1]["failures"]
        self.assertEqual((f["file"], f["line"]), ("p2.txt", 1))

    def test_text_says_n_of_m_and_names_the_failed_part(self):
        r = self.own()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        last = r.stdout.strip().splitlines()[-1]
        self.assertRegex(last, r"^check: 1 of 3 passed; failed: p2 .*; unchecked: p3 ")

    @unittest.skipIf(CHECKS_CLI is None, LONE)
    def test_its_json_passes_the_validator(self):
        r = self.own("--json")
        self.assertEqual(self.validate(self.printing("own", r.stdout, r.returncode)), ("ok", []))


if __name__ == "__main__":
    unittest.main()
