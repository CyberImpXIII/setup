"""devtools/mutate.py, the one mutant runner (the `mutate` component renders it
into every repo that keeps mutants): it removes its copies however a run ends,
refuses an argument it does not know (an unknown `--help` once ran every mutant,
and a SIGTERM to that run left ~124 copies under .mutants/), applies every edit
of a mutant's `edits` list (and a read-only file's), and calls a mutant whose
string moved STALE. Each case runs a copy of the runner in a fixture tree of its
own, so nothing here depends on this repo's files."""
import json
import os
import shutil
import signal
import subprocess
import sys
import time

from tests.helpers import ROOT, Case

SOURCE = ROOT / "devtools" / "mutate.py"


class Runner(Case):
    def setUp(self):
        super().setUp()
        self.tree = self.tmp / "tree"
        (self.tree / "devtools").mkdir(parents=True)
        shutil.copy2(SOURCE, self.tree / "devtools" / "mutate.py")
        (self.tree / "a.txt").write_text("alpha\n")
        (self.tree / "b.txt").write_text("beta\n")
        self.work = self.tmp / "work"

    def mutants(self, *ms):
        path = self.tmp / "mutants.json"
        path.write_text(json.dumps({"mutants": list(ms)}))
        return path

    def mutate(self, *args, timeout=120):
        return subprocess.run([sys.executable, str(self.tree / "devtools" / "mutate.py"), *map(str, args),
                               "--work", str(self.work)], capture_output=True, text=True, timeout=timeout)

    def leftovers(self):
        return sorted(p.name for p in self.work.glob("run-*")) if self.work.exists() else []

    def test_sigterm_mid_run_stops_the_commands_and_removes_the_copies(self):
        # The baseline copy runs this first: it marks that it started, then outlasts the test.
        path = self.mutants({"id": "one", "file": "a.txt", "old": "alpha", "new": "x",
                             "run": ["sh", "-c", "touch started; exec sleep 120"]})
        p = subprocess.Popen([sys.executable, str(self.tree / "devtools" / "mutate.py"), str(path),
                              "--work", str(self.work)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.time() + 60
            while not list(self.work.glob("run-*/base0/started")):
                self.assertIsNone(p.poll(), "mutate.py ended before its command started")
                self.assertLess(time.time(), deadline, "the baseline command never started")
                time.sleep(0.2)
            self.assertEqual(len(self.leftovers()), 1)
            p.send_signal(signal.SIGTERM)
            out, err = p.communicate(timeout=30)  # far less than the sleep: the command was stopped, not waited for
        finally:
            if p.poll() is None:
                p.kill()
            p.communicate()
        self.assertEqual(p.returncode, 128 + signal.SIGTERM, out + err)
        self.assertEqual(self.leftovers(), [])

    def test_an_unknown_argument_is_refused_and_runs_nothing(self):
        path = self.mutants({"id": "one", "file": "a.txt", "old": "alpha", "new": "x", "run": ["true"]})
        for args in (["--help"], [path, "--help"], [path, "--only"], [path, "extra.json"]):
            with self.subTest(args=args):
                r = self.mutate(*args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("usage: devtools/mutate.py", r.stderr)
                self.assertFalse(self.work.exists(), "a refused run made a work folder")

    def test_a_known_run_still_runs_and_cleans_up(self):
        # The control for the two above: the same file, run properly, does run (and `true` survives).
        r = self.mutate(self.mutants({"id": "one", "file": "a.txt", "old": "alpha", "new": "x", "run": ["true"]}),
                        "--only", "one")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("SURVIVED  one", r.stdout)
        self.assertEqual(self.leftovers(), [])

    # red only when both files were edited: a gate guarded twice over
    BOTH = ["sh", "-c", "! { grep -q '^x$' a.txt && grep -q '^y$' b.txt; }"]

    def test_every_edit_of_a_mutant_is_applied(self):
        both = {"id": "both", "edits": [{"file": "a.txt", "old": "alpha", "new": "x"},
                                        {"file": "b.txt", "old": "beta", "new": "y"}], "run": self.BOTH}
        one = {"id": "one", "edits": [{"file": "a.txt", "old": "alpha", "new": "x"}], "run": self.BOTH}
        r = self.mutate(self.mutants(both, one))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertNotIn("both", r.stdout.replace("mutants:", ""), "both edits applied: red, not listed")
        self.assertIn("SURVIVED  one", r.stdout)  # the counterfactual: one edit alone leaves it green
        self.assertIn("mutants: 1 of 2 red", r.stdout)

    def test_a_string_that_moved_is_stale(self):
        m = {"id": "moved", "edits": [{"file": "a.txt", "old": "alpha", "new": "x"},
                                      {"file": "b.txt", "old": "gamma", "new": "y"}], "run": self.BOTH}
        r = self.mutate(self.mutants(m))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("STALE     moved: b.txt: the string to replace occurs 0 times", r.stdout)

    def test_a_read_only_file_is_edited_and_keeps_its_mode(self):
        (self.tree / "b.txt").chmod(0o444)
        check = ["sh", "-c", "grep -q '^y$' b.txt && test ! -w b.txt && exit 1; exit 0"]
        r = self.mutate(self.mutants({"id": "ro", "file": "b.txt", "old": "beta", "new": "y", "run": check}))
        self.assertEqual((r.returncode, r.stdout.strip().splitlines()[-1]),
                         (0, "mutants: 1 of 1 red, every gate shown able to fail"), r.stdout + r.stderr)

    def test_the_source_parses_and_is_executable(self):
        self.assertTrue(os.access(SOURCE, os.X_OK), f"{SOURCE} is not executable")
        compile(SOURCE.read_text(), str(SOURCE), "exec")  # a SyntaxError fails the test
