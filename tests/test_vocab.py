"""Documented == implemented, both directions: components, statuses, subcommands,
and the one-writer rule."""
import re
import subprocess

from setuplib import core
from tests.helpers import ROOT, Case


class Vocab(Case):
    def test_components_equal_methods(self):
        declared = [c["name"] for c in core.load_spec()["components"]]
        methods = sorted(m[2:] for m in dir(core.Setup) if m.startswith("c_"))
        self.assertEqual(sorted(declared), methods)
        self.assertEqual(len(declared), len(set(declared)))

    def test_every_component_runs_in_declared_order(self):
        code, res = self.run_json("fresh", "--dry-run")
        self.assertEqual(list(res), [c["name"] for c in core.load_spec()["components"]])

    def test_statuses_declared_equal_statuses_ranked(self):
        self.assertEqual(set(core.load_spec()["statuses"]), set(core.PRECEDENCE))
        self.assertTrue(core.BAD <= set(core.PRECEDENCE))

    def test_every_declared_status_is_emitted_and_nothing_else(self):
        src = (ROOT / "setuplib" / "core.py").read_text()
        literal = set(re.findall(r'Result\("\w+", "([a-z-]+)"[,)]', src))
        literal |= set(re.findall(r'return "([a-z-]+)", ', src))  # _settings' statuses
        derived = {"needs-" + c["needs"] for c in core.load_spec()["components"] if "needs" in c}
        emitted = literal | derived
        self.assertEqual(emitted, set(core.load_spec()["statuses"]))

    def test_usage_lists_exactly_the_subcommands(self):
        r = subprocess.run([str(ROOT / "setup"), "--help"], capture_output=True, text=True)
        listed = re.findall(r"^\s+setup ([a-z]+)\b", r.stdout, re.M)
        src = (ROOT / "setup").read_text()
        handlers = re.findall(r"^def cmd_([a-z]+)\(", src, re.M)
        subs = re.search(r"SUBCOMMANDS = \[(.*?)\]", src).group(1)
        subs = re.findall(r'"([a-z]+)"', subs)
        self.assertEqual(sorted(set(listed)), sorted(subs))
        self.assertEqual(sorted(handlers), sorted(subs + ["setup"]))

    def test_components_subcommand_shows_every_component(self):
        r = self.run_setup("components")
        self.assertEqual(r.returncode, 0)
        for c in core.load_spec()["components"]:
            self.assertRegex(r.stdout, r"(?m)^  " + c["name"] + r"\s")


class DevSh(Case):
    def test_usage_equals_case_arms(self):
        src = (ROOT / "dev.sh").read_text()
        usage = re.search(r"cat <<'EOF'\n(.*?)\nEOF", src, re.S).group(1)
        listed = re.findall(r"^  ([a-z]+)\s", usage, re.M)
        dispatch = src[src.rindex('case "${1:-}" in'):]
        arms = [a for a in re.findall(r"^  ([a-z]+)\)", dispatch, re.M)]
        self.assertEqual(sorted(listed), sorted(arms))
        handlers = re.findall(r"^cmd_([a-z]+)\(\)", src, re.M)
        self.assertEqual(sorted(handlers), sorted(arms))

    def test_check_runs_every_gate_but_plans(self):
        src = (ROOT / "dev.sh").read_text()
        gates = re.search(r"^GATES=\((.*?)\)", src, re.M).group(1).split()
        arms = re.findall(r"^  ([a-z]+)\)", src[src.rindex('case "${1:-}" in'):], re.M)
        self.assertEqual(sorted(gates), sorted(set(arms) - {"check", "plans"}))


# Anything that changes disk or a remote. Only setuplib/fsw.py may contain these.
WRITES = re.compile(r"write_text|write_bytes|\.mkdir\(|chmod|unlink|rmtree|os\.remove|\.rename\(|shutil\."
                    r"|open\([^)]*['\"][wax]"
                    r"|(?:\[\"git\", |_git\(\[)\"(?:init|add|commit|push|tag|reset|checkout|remote\", \"(?:add|set-url))\""
                    r"|(?:\[\"git\", |_git\(\[)\"config\"(?!, \"--(?:get|show-origin)\")"
                    r"|\"repo\", \"(?:create|edit|delete)\"")


class OneWriter(Case):
    def test_no_module_but_fsw_writes(self):
        files = [ROOT / "setup", *sorted((ROOT / "setuplib").glob("*.py"))]
        hits = []
        for f in files:
            if f.name == "fsw.py":
                continue
            for i, line in enumerate(f.read_text().splitlines(), 1):
                if WRITES.search(line):
                    hits.append(f"{f.name}:{i}: {line.strip()}")
        self.assertEqual(hits, [])

    def test_the_pattern_catches_a_write(self):
        for line in ['p.write_text("x")', 'subprocess.run(["git", "commit"])', "open(p, 'w')",
                     "shutil.copy(a, b)", 'run([gh, "repo", "create", s])', '_git(["add", "x"], t)',
                     '_git(["remote", "add", "origin", u], t)', '_git(["config", "core.hooksPath", p], t)',
                     '_git(["config", "--local", "k", v], t)', '["git", "config", "--unset", k]']:
            self.assertRegex(line, WRITES)
        # a read of git config is not a write
        for line in ['_git(["config", "--get", k], t)', '_git(["config", "--show-origin", "--get", k], t)']:
            self.assertNotRegex(line, WRITES)
