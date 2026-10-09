"""This repo's own `./dev.sh check` records a pass for the git pre-commit gate (the
githooks component's `.githooks/check-pass`) only when every gate is green, on the
tree it took before the first gate, and never lets the recording change the check's
own result or its --json document.

Run end to end on a copy of dev.sh with its gates swapped for one canned gate and
`.githooks/check-pass` for a fake that logs its calls (the real suite would run this
test inside itself). No override exists in dev.sh for this: the copy is rewritten,
and the test fails if the line it rewrites moved."""
import json
import shutil
import subprocess

from tests.helpers import ROOT, Case

GATES = "GATES=(test hooks files audit self mutants)\n"
DISPATCH = 'case "${1:-}" in\n'
CANNED = ('cmd_canned() { echo gate >>"$LOG"; [ "$GATE_EXIT" = 0 ] && echo "  ok    canned" '
          '|| echo "  FAIL  canned"; return "$GATE_EXIT"; }\n')
# The fake prints to stdout on record, as the real one may: in --json that must not
# reach the document.
FAKE = """#!/usr/bin/env bash
echo "$*" >>"$LOG"
case "$1" in
  tree) [ -n "$FAKE_TREE" ] && echo "$FAKE_TREE"; exit 0 ;;
  record) echo "check-pass: recorded"; exit "$FAKE_RECORD_EXIT" ;;
esac
exit 2
"""


class RecordPass(Case):
    def setUp(self):
        super().setUp()
        d = self.dir = self.tmp / "copy"
        (d / "devtools").mkdir(parents=True)
        shutil.copy(ROOT / "devtools" / "checkjson.py", d / "devtools")
        text = (ROOT / "dev.sh").read_text()
        self.assertEqual((text.count(GATES), text.count(DISPATCH)), (1, 1), "dev.sh moved: update this test")
        (d / "dev.sh").write_text(text.replace(GATES, "GATES=(canned)\n").replace(DISPATCH, CANNED + DISPATCH))
        (d / "dev.sh").chmod(0o755)
        (d / ".githooks").mkdir()
        (d / ".githooks" / "check-pass").write_text(FAKE)
        (d / ".githooks" / "check-pass").chmod(0o755)
        self.log = self.tmp / "calls.log"

    def check(self, *args, gate=0, tree="TREE1", record=0):
        self.log.write_text("")
        env = dict(self.env, LOG=str(self.log), GATE_EXIT=str(gate), FAKE_TREE=tree,
                   FAKE_RECORD_EXIT=str(record))
        r = subprocess.run(["./dev.sh", "check", *args], cwd=self.dir, env=env,
                           capture_output=True, text=True)
        return r, self.log.read_text().splitlines()

    def test_green_records_the_tree_taken_before_the_first_gate(self):
        r, calls = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate", "record --from TREE1"])

    def test_red_records_nothing(self):
        r, calls = self.check(gate=1)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate"])

    def test_json_green_records_and_keeps_stdout_one_document(self):
        r, calls = self.check("--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate", "record --from TREE1"])
        self.assertIs(json.loads(r.stdout)["ok"], True)
        self.assertIn("check-pass: recorded", r.stderr)

    def test_json_red_records_nothing(self):
        r, calls = self.check("--json", gate=1)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate"])
        self.assertIs(json.loads(r.stdout)["ok"], False)

    def test_no_tree_records_nothing(self):
        """check-pass could not read the tree: nothing to record against, never `--from ''`."""
        for args in ((), ("--json",)):
            r, calls = self.check(*args, tree="")
            self.assertEqual(r.returncode, 0, args)
            self.assertEqual(calls, ["tree", "gate"], args)

    def test_a_failed_record_says_so_and_leaves_the_check_green(self):
        r, calls = self.check(record=1)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate", "record --from TREE1"])
        self.assertIn("check: green, but the pass was not recorded", r.stdout)

    def test_without_check_pass_the_check_runs_and_records_nothing(self):
        (self.dir / ".githooks" / "check-pass").unlink()
        r, calls = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["gate"])
        self.assertIn("check: all 1 gates green", r.stdout)
