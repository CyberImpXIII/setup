"""`./dev.sh check --json` in the one schema every repo prints (the shared checks
tool holds it, schema/check-json.schema.json): the stub setup installs, and this
repo's own (devtools/checkjson.py, called by dev.sh).

Anywhere: each output equals its reviewed fixture in tests/fixtures/, and the
exit code agrees with `ok`. In the workspace: the real validator (`check-json`,
run through the shared checks CLI on a scratch repo, as a subprocess) passes
each output, and fails the old `{"ok", "error"}` shape, the counterfactual that
shows it is judging. No copy of the schema or its validator lives here: the
fixtures are what this repo holds, the validator is what proves them."""
import json
import shutil
import subprocess
import unittest

from tests.helpers import ROOT, Case, git_repo, workspace_cli

FIX = ROOT / "tests" / "fixtures"
HELPER = ROOT / "devtools" / "checkjson.py"
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


def red_rows(tmp):
    """Canned gate outputs, one of each finding kind devtools/checkjson.py reads."""
    outs = {
        "test": "..F.E\n" + "=" * 20 + "\nFAIL: test_check_stub_fails_by_name "
                "(tests.test_fixture.Fixture.test_check_stub_fails_by_name)\nTraceback: x\n"
                "ERROR: test_gone (tests.test_nowhere.Gone.test_gone)\nRan 5 tests\nFAILED (failures=1, errors=1)\n",
        "hooks": "  ok    hooks: 3 hooks\n",
        "files": "",
        "audit": f"  FAIL  {ROOT}/setuplib/core.py:12: repo name x\n  FAIL  /elsewhere/y.py:3: repo name x\n"
                 "  UNCHECKED: no sibling git repos within 2 folders\n",
        "self": "  ok    self: 10 unchanged\n",
        "mutants": "  SURVIVED  some-id: a gate stayed green\n  BASELINE-RED  python3 -m x exits 1 unmutated: a\n"
                   "mutants: 1 of 2 red, 2 problem(s)\n",
    }
    codes = {"test": 1, "hooks": 0, "files": 1, "audit": 1, "self": 0, "mutants": 1}
    roles = {"audit": "audit", "mutants": "tests"}
    rows = []
    for g, text in outs.items():
        (tmp / g).write_text(text)
        rows.append(f"{g}:{roles.get(g, 'code')}:{codes[g]}:{tmp / g}")
    return rows


class Own(Case, Live):
    """This repo's own --json: every gate a check, each finding line a failure."""

    def helper(self, rows):
        return subprocess.run([str(HELPER), *rows], capture_output=True, text=True)

    def test_red_report_is_the_fixture(self):
        r = self.helper(red_rows(self.tmp))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(json.loads(r.stdout), fixture("own-check-red.json"))

    def test_green_report_is_the_fixture(self):
        (self.tmp / "out").write_text("  FAIL  ignored: the gate exited 0\n")
        r = self.helper([f"{g}:code:0:{self.tmp / 'out'}" for g in ("test", "files")])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), fixture("own-check-green.json"))

    def test_no_gates_or_a_bad_row_is_refused_not_reported(self):
        for rows in ([], ["test:code:x:/dev/null"], ["test::0:/dev/null"]):
            r = self.helper(rows)
            self.assertEqual((r.returncode, r.stdout), (64, ""), rows)

    def test_dev_sh_wires_each_gate_through_the_helper(self):
        """dev.sh's own check --json, end to end, with its gates swapped for canned
        ones in a copy (the real suite would run this test inside itself)."""
        d = self.tmp / "copy"
        (d / "devtools").mkdir(parents=True)
        shutil.copy(HELPER, d / "devtools")
        text = (ROOT / "dev.sh").read_text()
        gates, dispatch = "GATES=(test hooks files audit self mutants)\n", 'case "${1:-}" in\n'
        self.assertEqual((text.count(gates), text.count(dispatch)), (1, 1), "dev.sh moved: update this test")
        # a gate assigning names the loop uses (cmd_hooks once leaked `out` this way,
        # emptying every later gate's findings) must change nothing outside itself
        canned = ('cmd_files() { capdir=/nonexistent; dest=/dev/null; out=x; rows=(); json=0\n'
                  '  echo "  FAIL  templates/dev.sh missing"; return 1; }\n'
                  'cmd_audit() { echo "  FAIL  $PWD/setup:7: repo name x"; return 1; }\n'
                  'cmd_mutants() { echo "  ok"; }\n')
        text = text.replace(gates, "GATES=(files audit mutants)\n").replace(dispatch, canned + dispatch)
        (d / "dev.sh").write_text(text)
        (d / "dev.sh").chmod(0o755)
        r = subprocess.run(["./dev.sh", "check", "--json"], cwd=d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        doc = json.loads(r.stdout)
        self.assertEqual([(c["name"], c["status"], [(f["message"], f["file"], f["line"], f["role"])
                                                    for f in c["failures"]]) for c in doc["checks"]], [
            ("files", "fail", [("templates/dev.sh missing", None, None, "code")]),
            ("audit", "fail", [("setup:7: repo name x", "setup", 7, "audit")]),
            ("mutants", "ok", [])])
        self.assertIs(doc["ok"], False)

    @unittest.skipIf(CHECKS_CLI is None, LONE)
    def test_reports_pass_the_validator(self):
        red = self.helper(red_rows(self.tmp))
        (self.tmp / "g").write_text("")
        green = self.helper([f"test:code:0:{self.tmp / 'g'}"])
        for name, r in (("red", red), ("green", green)):
            self.assertEqual(self.validate(self.printing(name, r.stdout, r.returncode)), ("ok", []), name)


if __name__ == "__main__":
    unittest.main()
