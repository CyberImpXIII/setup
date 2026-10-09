"""`./dev.sh hooks` reads each hook's own test like a gate: exit 0 passes, exit 3 is
UNCHECKED (the test could not run here, e.g. the troubleshooting and prefer-recipes
tests with no sibling repo above a lone clone), anything else FAILs. UNCHECKED is
named with its reason and makes the gate exit 3: never a pass, never a FAIL; a FAIL
anywhere still makes it 1. Run on a copy of dev.sh beside two planted hooks whose
tests exit as each case says (exit 0/1/3 counterfactuals)."""
import json
import shutil
import subprocess

from tests.helpers import ROOT, Case

TEST = """#!/usr/bin/env bash
code=${%s:-0}
[ "$code" = 3 ] && echo "UNCHECKED: sibling not found above here: the cases did not run"
[ "$code" = 1 ] && echo "FAIL  a case"
exit "$code"
"""


class HooksGate(Case):
    def setUp(self):
        super().setUp()
        d = self.dir = self.tmp / "copy"
        hooks = d / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        shutil.copy(ROOT / "dev.sh", d / "dev.sh")
        groups = []
        for name, var in (("x.sh", "X_EXIT"), ("y.sh", "Y_EXIT")):
            (hooks / name).write_text("#!/usr/bin/env bash\nexit 0\n")
            (hooks / f"test-{name}").write_text(TEST % var)
            for f in (name, f"test-{name}"):
                (hooks / f).chmod(0o755)
            groups.append({"hooks": [{"type": "command", "command": f"bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/{name}"}]})
        (d / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"PreToolUse": groups}}))

    def hooks(self, x=0, y=0):
        env = dict(self.env, X_EXIT=str(x), Y_EXIT=str(y))
        r = subprocess.run(["./dev.sh", "hooks"], cwd=self.dir, env=env, capture_output=True, text=True)
        return r.returncode, r.stdout

    def test_every_test_passing_is_ok(self):
        code, out = self.hooks()
        self.assertEqual(code, 0, out)
        self.assertIn("  ok    hooks: 2 hooks", out)

    def test_a_failing_test_is_fail(self):
        code, out = self.hooks(x=1)
        self.assertEqual(code, 1, out)
        self.assertIn("  FAIL  test-x.sh: exit 1", out)
        self.assertNotIn("ok    hooks", out)

    def test_exit_3_is_unchecked_with_its_reason_never_a_pass(self):
        code, out = self.hooks(x=3)
        self.assertEqual(code, 3, out)
        self.assertIn("  UNCHECKED  test-x.sh: sibling not found above here: the cases did not run", out)
        self.assertNotIn("FAIL", out)
        self.assertNotIn("ok    hooks", out)

    def test_a_fail_beside_an_unchecked_is_still_fail(self):
        code, out = self.hooks(x=3, y=1)
        self.assertEqual(code, 1, out)
        self.assertIn("UNCHECKED  test-x.sh", out)
        self.assertIn("FAIL  test-y.sh: exit 1", out)
