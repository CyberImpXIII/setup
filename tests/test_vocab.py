"""Documented == implemented, both directions: components, statuses, subcommands,
and the one-writer rule."""
import json
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

    def test_an_arm_without_arguments_refuses_one(self):
        """`./dev.sh test test.x` ran the whole suite while reading as one part
        (2026-10-19): every arm that does not shift its arguments refuses one, exit 2,
        naming check --only, and runs nothing. `files` first: it is the cheap arm, so
        with the guard gone the case fails there without running the suite."""
        src = (ROOT / "dev.sh").read_text()
        dispatch = src[src.rindex('case "${1:-}" in'):]
        bare = re.findall(r"^  ([a-z]+)\)\s+cmd_\w+ ;;", dispatch, re.M)
        guard = re.search(r"^  ([a-z|]+)\)\n    if \[ \$# -gt 1 \]", src, re.M)
        self.assertIsNotNone(guard, "the no-argument guard before the dispatch is gone")
        self.assertEqual(sorted(guard.group(1).split("|")), sorted(bare))
        for arm in sorted(bare, key=lambda a: a != "files"):
            r = subprocess.run(["./dev.sh", arm, "extra"], cwd=ROOT, capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 2, f"{arm}: {r.stdout[-300:]}{r.stderr[-300:]}")
            self.assertIn(f"dev.sh {arm} takes no arguments (given: extra)", r.stderr)
            self.assertIn("./dev.sh check --only <part>", r.stderr)
            self.assertEqual(r.stdout, "")

    def test_check_runs_every_module_and_every_gate_but_plans(self):
        """check.parts.json (what `./dev.sh check` runs): one part per test module, one
        per gate dev.sh dispatches but check, test and plans, and the runner takes it."""
        src = (ROOT / "dev.sh").read_text()
        arms = re.findall(r"^  ([a-z]+)\)", src[src.rindex('case "${1:-}" in'):], re.M)
        parts = json.loads((ROOT / "check.parts.json").read_text())["parts"]
        tests = [p for p in parts if p["name"].startswith("test.")]
        modules = sorted(f.stem for f in (ROOT / "tests").glob("test_*.py"))
        self.assertEqual([(p["name"], p["run"], p["files"]) for p in tests],
                         [(f"test.{m[5:]}", f"python3 -m unittest -v tests.{m}", [f"tests/{m}.py"]) for m in modules])
        gates = [p for p in parts if not p["name"].startswith("test.")]
        self.assertEqual(sorted(p["name"] for p in gates), sorted(set(arms) - {"check", "test", "plans"}))
        self.assertEqual([p["run"] for p in gates], [f"./dev.sh {p['name']}" for p in gates])
        r = subprocess.run(["python3", "devtools/parts.py", "validate", "check.parts.json"], cwd=ROOT,
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, f"ok: {len(parts)} parts\n"), r.stderr)


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
