"""This repo's own `./dev.sh check` records a pass for the git pre-commit gate (the
githooks component's `.githooks/check-pass`) only when every part passed, on the
tree it took before the first part, and never lets the recording change the check's
own result or its --json document. A part that said UNCHECKED, a run of other parts
(CHECK_PARTS) and a run of some parts (--only) record nothing; a --resume records
where it resumed from (`--resumed-from K/N`).

Run end to end on a copy of dev.sh and the shared runner (devtools/parts.py) beside a
one-part check.parts.json whose part exits as each case says, with
`.githooks/check-pass` swapped for a fake that logs its calls (the real suite would
run this test inside itself). Nothing in dev.sh is rewritten: the copy's own parts
file is the canned one."""
import json
import shutil
import subprocess

from tests.helpers import ROOT, Case

PART = 'echo gate >>"$LOG"; [ "$GATE_EXIT" = 0 ] && echo "  ok    canned" || echo "  FAIL  canned"; exit "$GATE_EXIT"\n'
PARTS = {"parts": [{"name": "canned", "run": "sh canned.sh", "files": ["canned.sh"], "timeout_s": 60}]}
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
WAIT = 120  # one canned part: a run past this is a hang, a failure of its own


class RecordPass(Case):
    def setUp(self):
        super().setUp()
        d = self.dir = self.tmp / "copy"
        (d / "devtools").mkdir(parents=True)
        shutil.copy(ROOT / "dev.sh", d / "dev.sh")
        shutil.copy(ROOT / "devtools" / "parts.py", d / "devtools" / "parts.py")
        (d / "check.parts.json").write_text(json.dumps(PARTS))
        (d / "canned.sh").write_text(PART)
        (d / ".githooks").mkdir()
        (d / ".githooks" / "check-pass").write_text(FAKE)
        (d / ".githooks" / "check-pass").chmod(0o755)
        self.log = self.tmp / "calls.log"

    def check(self, *args, gate=0, tree="TREE1", record=0, **extra):
        self.log.write_text("")
        env = dict(self.env, LOG=str(self.log), GATE_EXIT=str(gate), FAKE_TREE=tree,
                   FAKE_RECORD_EXIT=str(record), **extra)
        r = subprocess.run(["./dev.sh", "check", *args], cwd=self.dir, env=env,
                           capture_output=True, text=True, timeout=WAIT)
        return r, self.log.read_text().splitlines()

    def test_green_records_the_tree_taken_before_the_first_part(self):
        r, calls = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate", "record --from TREE1"])
        self.assertIn("check: 1 of 1 passed", r.stdout)

    def test_red_records_nothing(self):
        r, calls = self.check(gate=1)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "gate"])
        self.assertNotIn("check: green", r.stderr)  # a red run is never called green

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
        self.assertNotIn("check: green", r.stderr)
        self.assertIs(json.loads(r.stdout)["ok"], False)

    def test_an_unchecked_part_is_green_by_the_schema_but_records_nothing(self):
        for args in ((), ("--json",)):
            r, calls = self.check(*args, gate=3)
            self.assertEqual(r.returncode, 0, args)
            self.assertEqual(calls, ["tree", "gate"], args)
            self.assertIn("not every part passed", r.stderr, args)

    def test_other_parts_or_some_parts_record_nothing(self):
        r, calls = self.check(CHECK_PARTS=str(self.dir / "check.parts.json"))
        self.assertEqual((r.returncode, calls), (0, ["gate"]), r.stdout + r.stderr)
        r, calls = self.check("--only", "canned")
        self.assertEqual((r.returncode, calls), (0, ["gate"]), r.stdout + r.stderr)

    def test_a_resume_records_where_it_resumed_from(self):
        self.check()
        r, calls = self.check("--resume")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["tree", "record --from TREE1 --resumed-from 1/1"])
        (self.dir / "canned.sh").write_text(PART + "# changed\n")
        r, calls = self.check("--resume")
        self.assertEqual(calls, ["tree", "gate", "record --from TREE1"], r.stdout + r.stderr)

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
        self.assertIn("check: green, but the pass was not recorded", r.stderr)

    def test_without_check_pass_the_check_runs_and_records_nothing(self):
        (self.dir / ".githooks" / "check-pass").unlink()
        r, calls = self.check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(calls, ["gate"])
        self.assertIn("check: 1 of 1 passed", r.stdout)
