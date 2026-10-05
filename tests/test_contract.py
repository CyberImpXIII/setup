"""PLAN-routing-tree.md §14.8: the contract files are setup components, each with a
shared check beside it, and setup runs those checks itself as its last step.

  services  services.json, the skeleton: the repo's name and its `check` entry
  cli       cli.json is never written (no skeleton passes its schema; see below)
  params    checks.json, the baseline: no parameter set, so every check's default
  registry  in a node run, registry.proposed.json: the union of the node's and its
            children's services.json, for Jacob to apply (as the settings proposal)
  gates     with --checks CLI, after everything is rendered: `<CLI> run <path>`,
            whose result is this line; a contract gate the CLI does not list fails

The skeletons are held to the shared schemas by the live tests at the bottom, which
run the shared checks CLI as a subprocess (never imported); the gates component's
own cases (a missing gate, an error, no JSON) use tests/fake_checks.py."""
import json
import os
import subprocess
import unittest

from setuplib import core
from tests.helpers import ROOT, Case, git, git_repo, snapshot, workspace_cli
from tests.test_node import ID, commit_all, write_node

CHECKS_CLI = workspace_cli("checks")[1]
FAKE = ROOT / "tests" / "fake_checks.py"
SPEC = core.load_spec()
GATES = next(c for c in SPEC["components"] if c["name"] == "gates")["contract"]


def skeleton(name):
    return {"name": name, "services": [{"service": "check", "run": "dev.sh", "verbs": ["check"]}]}


def load(p):
    return json.loads(p.read_text())


def name_registry(top, children=("alpha", "beta")):
    """Jacob's step: registry.json (already in place) named in node.json, both
    committed by name (never add -A over the nested child repos)."""
    write_node(top, children=children, record=["registry.json"], registry="registry.json", commit=False)
    for args in (["add", "node.json", "registry.json"], [*ID, "commit", "-q", "-m", "registry"]):
        r = git(args, top)
        assert r.returncode == 0, r.stderr + r.stdout


class Contract(Case):
    def test_a_new_repo_gets_the_services_skeleton_committed(self):
        code, res = self.run_json("fresh")
        self.assertEqual((code, res["services"]["status"]), (0, "installed"))
        repo = self.tmp / "fresh"
        self.assertEqual(load(repo / "services.json"), skeleton("fresh"))
        self.assertIn("services.json", git(["ls-files"], repo).stdout.split())

    def test_the_skeleton_takes_the_name_given(self):
        self.run_json("fresh", "--name", 'odd "name"')
        self.assertEqual(load(self.tmp / "fresh/services.json")["name"], 'odd "name"')

    def test_an_existing_services_json_is_the_owners(self):
        repo = git_repo(self.tmp / "r")
        mine = '{"name": "r", "services": [], "tags": ["x"]}\n'
        (repo / "services.json").write_text(mine)
        _, res = self.run_json("r")
        self.assertEqual(res["services"]["status"], "unchanged")
        self.assertEqual((repo / "services.json").read_text(), mine)

    def test_checks_json_is_the_baseline_and_an_existing_one_is_kept(self):
        _, res = self.run_json("fresh")
        self.assertEqual(res["params"]["status"], "installed")
        doc = load(self.tmp / "fresh/checks.json")
        self.assertTrue(doc and all(k.startswith("_") for k in doc), doc)
        self.assertIn("checks.json", git(["ls-files"], self.tmp / "fresh").stdout.split())
        repo = git_repo(self.tmp / "r")
        (repo / "checks.json").write_text('{"todo-valid": {}}\n')
        _, res = self.run_json("r")
        self.assertEqual(res["params"]["status"], "unchanged")
        self.assertEqual((repo / "checks.json").read_text(), '{"todo-valid": {}}\n')

    def test_cli_json_is_never_written(self):
        _, res = self.run_json("fresh")
        self.assertEqual(res["cli"]["status"], "none")
        self.assertFalse((self.tmp / "fresh/cli.json").exists())
        repo = git_repo(self.tmp / "r")
        (repo / "cli.json").write_text("{}\n")
        _, res = self.run_json("r")
        self.assertEqual(res["cli"]["status"], "unchanged")
        self.assertEqual((repo / "cli.json").read_text(), "{}\n")

    def test_a_dry_run_writes_no_contract_file(self):
        repo = git_repo(self.tmp / "r")
        before = snapshot(repo)
        _, res = self.run_json("r", "--dry-run")
        self.assertEqual((res["services"]["status"], res["params"]["status"]), ("installed", "installed"))
        self.assertEqual(snapshot(repo), before)

    def test_the_registry_proposal_is_ignored_by_the_baseline(self):
        self.run_json("fresh")
        r = git(["check-ignore", "-q", "registry.proposed.json"], self.tmp / "fresh")
        self.assertEqual(r.returncode, 0)


class Registry(Case):
    def node(self, children=("alpha", "beta"), **extra):
        self.run_json("top")
        top = self.tmp / "top"
        write_node(top, children=children, **extra)
        return top

    def run_node(self, *args):
        r = self.run_setup("top", "--node", "--json", *args)
        self.assertIn(r.returncode, (0, 1), r.stderr)
        doc = json.loads(r.stdout)
        return r.returncode, {x["component"]: x for x in doc["results"]}

    def test_none_outside_a_node_run(self):
        _, res = self.run_json("fresh")
        self.assertEqual(res["registry"]["status"], "none")
        self.assertFalse((self.tmp / "fresh/registry.proposed.json").exists())

    def test_the_proposal_is_the_union_of_every_services_json(self):
        top = self.node()
        self.run_node()
        alpha = load(top / "alpha/services.json")
        alpha["tags"] = ["alpha-tag"]
        (top / "alpha/services.json").write_text(json.dumps(alpha))
        code, res = self.run_node()
        self.assertEqual((code, res["registry"]["status"]), (0, "needs-jacob"))
        self.assertEqual(load(top / "registry.proposed.json"), {"services": {
            ".": skeleton("top"), "alpha": alpha, "beta": skeleton("beta")}})
        self.assertIn("no `registry`", res["registry"]["detail"])

    def test_a_live_registry_equal_to_the_union_is_unchanged_and_not_proposed(self):
        top = self.node()
        self.run_node()
        (top / "registry.json").write_text((top / "registry.proposed.json").read_text())
        (top / "registry.proposed.json").unlink()
        name_registry(top)
        code, res = self.run_node()
        self.assertEqual((code, res["registry"]["status"]), (0, "unchanged"))
        self.assertFalse((top / "registry.proposed.json").exists())

    def test_a_live_registry_that_differs_is_proposed_with_the_rows_named(self):
        top = self.node()
        (top / "registry.json").write_text(json.dumps({"services": {".": skeleton("top"), "gone": {}}}))
        name_registry(top)
        code, res = self.run_node()
        self.assertEqual((code, res["registry"]["status"]), (0, "needs-jacob"))
        for row in ("alpha", "beta", "gone"):
            self.assertIn(f"`{row}`", res["registry"]["detail"])
        self.assertNotIn("`.`", res["registry"]["detail"])
        self.assertIn("cp registry.proposed.json registry.json", res["registry"]["detail"])

    def test_a_child_services_json_that_does_not_parse_fails_and_proposes_nothing(self):
        top = self.node()
        self.run_node()
        (top / "registry.proposed.json").unlink()
        (top / "beta/services.json").write_text("{not json")
        code, res = self.run_node()
        self.assertEqual((code, res["registry"]["status"]), (1, "failed"))
        self.assertIn("beta/services.json", res["registry"]["detail"])
        self.assertFalse((top / "registry.proposed.json").exists())

    def test_a_dry_run_counts_the_skeleton_a_new_child_would_get_and_writes_nothing(self):
        top = self.node()
        before = snapshot(top)
        _, res = self.run_node("--dry-run")
        self.assertEqual(res["registry"]["status"], "needs-jacob")
        self.assertIn("would write", res["registry"]["detail"])
        self.assertIn("3 row(s)", res["registry"]["detail"])
        self.assertEqual(snapshot(top), before)

    def test_a_node_with_no_children_and_no_registry_has_nothing_to_hold(self):
        top = self.node(children=())
        _, res = self.run_node()
        self.assertEqual(res["registry"]["status"], "none")
        self.assertFalse((top / "registry.proposed.json").exists())


class Gates(Case):
    """The gates component against the stand-in CLI."""

    def fake(self, gates=GATES, results=(), **extra):
        spec = self.tmp / "fake.json"
        spec.write_text(json.dumps({"gates": list(gates), "results": list(results), **extra}))
        self.env.update({"FAKE_CHECKS": str(spec), "FAKE_CHECKS_LOG": str(self.tmp / "fake.log")})
        return ["--checks", str(FAKE)]

    def calls(self):
        p = self.tmp / "fake.log"
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def ok(self, *names):
        return [{"check": n, "status": "ok", "lines": []} for n in names]

    def test_without_the_flag_nothing_runs(self):
        self.fake()
        _, res = self.run_json("fresh")
        self.assertEqual(res["gates"]["status"], "none")
        self.assertEqual(self.calls(), [])

    def test_a_dry_run_runs_nothing(self):
        args = self.fake(results=self.ok(*GATES))
        _, res = self.run_json("fresh", "--dry-run", *args)
        self.assertEqual(res["gates"]["status"], "none")
        self.assertEqual(self.calls(), [])

    def test_runs_last_after_the_render_list_then_run(self):
        args = self.fake(results=self.ok(*GATES))
        code, res = self.run_json("fresh", *args)
        self.assertEqual((code, res["gates"]["status"]), (0, "unchanged"))
        calls = self.calls()
        self.assertEqual([c["argv"] for c in calls],
                         [["list", "--json"], ["run", str(self.tmp / "fresh"), "--json"]])
        self.assertTrue({"services.json", "checks.json", "dev.sh"} <= set(calls[1]["files"]))
        self.assertEqual(list(res)[-1], "gates")

    def test_a_contract_gate_the_cli_lacks_fails_by_name_and_the_rest_still_run(self):
        args = self.fake(gates=GATES[1:], results=self.ok(*GATES[1:]))
        code, res = self.run_json("fresh", *args)
        self.assertEqual((code, res["gates"]["status"]), (1, "failed"))
        self.assertIn(GATES[0], res["gates"]["detail"])
        self.assertEqual(len(self.calls()), 2)

    def test_a_contract_gate_run_leaves_out_is_run_by_name_after_it(self):
        args = self.fake(results=self.ok(*GATES[1:]), one=self.ok(GATES[0]))
        code, res = self.run_json("fresh", *args)
        self.assertEqual((code, res["gates"]["status"]), (0, "unchanged"), res["gates"])
        self.assertEqual([c["argv"][0] for c in self.calls()], ["list", "run", "one"])
        self.assertEqual(self.calls()[2]["argv"], ["one", GATES[0], str(self.tmp / "fresh"), "--json"])

    def test_a_contract_gate_that_reports_nothing_is_named(self):
        args = self.fake(results=self.ok(*GATES[1:]))
        code, res = self.run_json("fresh", *args)
        self.assertEqual((code, res["gates"]["status"]), (1, "failed"))
        self.assertIn(f"reported nothing: {GATES[0]}", res["gates"]["detail"])

    def test_a_contract_gate_run_by_name_that_fails_is_drift(self):
        rows = [{"check": GATES[0], "status": "fail", "lines": ["bad shape"]}]
        code, res = self.run_json("fresh", *self.fake(results=self.ok(*GATES[1:]), one=rows))
        self.assertEqual((code, res["gates"]["status"]), (1, "drift"))
        self.assertIn(f"{GATES[0]}: bad shape", res["gates"]["detail"])

    def test_a_failing_check_is_drift_with_its_first_line(self):
        rows = self.ok(*GATES) + [{"check": "extra", "status": "fail", "lines": ["first finding", "second"]}]
        code, res = self.run_json("fresh", *self.fake(results=rows))
        self.assertEqual((code, res["gates"]["status"]), (1, "drift"))
        self.assertIn("extra: first finding", res["gates"]["detail"])

    def test_an_error_or_a_fault_fails(self):
        for i, extra in enumerate(({"results": self.ok(*GATES) + [{"check": "x", "status": "error", "lines": ["boom"]}]},
                                   {"results": self.ok(*GATES), "faults": ["x.py: no header"]})):
            with self.subTest(extra=extra):
                code, res = self.run_json(f"f{i}", *self.fake(**extra))
                self.assertEqual((code, res["gates"]["status"]), (1, "failed"))

    def test_unchecked_is_named_and_not_a_pass_line(self):
        rows = self.ok(*GATES[1:]) + [{"check": GATES[0], "status": "unchecked", "lines": ["no input"]}]
        code, res = self.run_json("fresh", *self.fake(results=rows))
        self.assertEqual((code, res["gates"]["status"]), (0, "unchanged"))
        self.assertIn(f"unchecked: {GATES[0]}", res["gates"]["detail"])

    def test_output_that_is_not_json_fails(self):
        code, res = self.run_json("fresh", *self.fake(raw="Traceback: nope"))
        self.assertEqual((code, res["gates"]["status"]), (1, "failed"))
        self.assertIn("no JSON", res["gates"]["detail"])

    def test_a_cli_that_is_not_there_fails(self):
        code, res = self.run_json("fresh", "--checks", str(self.tmp / "nope"))
        self.assertEqual((code, res["gates"]["status"]), (1, "failed"))

    def test_children_run_their_own_gates(self):
        args = self.fake(results=self.ok(*GATES))
        self.run_json("top")
        write_node(self.tmp / "top", children=["alpha"])
        r = self.run_setup("top", "--node", "--json", *args)
        doc = json.loads(r.stdout)
        ran = [c["argv"][1] for c in self.calls() if c["argv"][0] == "run"]
        self.assertEqual(ran, [str(self.tmp / "top/alpha"), str(self.tmp / "top")])
        (kid,) = doc["children"]
        self.assertEqual({x["component"]: x["status"] for x in kid["results"]}["gates"], "unchanged")

    def test_a_rebuild_runs_no_gates(self):
        args = self.fake(results=self.ok(*GATES))
        self.run_json("top")
        write_node(self.tmp / "top")
        self.run_setup(".", "--node", "--rebuild", *args, cwd=self.tmp / "top")
        self.assertEqual(self.calls(), [])

    def test_the_contract_list_names_components_and_gates_once(self):
        self.assertEqual(len(GATES), len(set(GATES)))
        self.assertTrue(GATES)


@unittest.skipIf(CHECKS_CLI is None, "no shared checks CLI in a workspace around this tool (a lone clone)")
class LiveContract(Case):
    """§14.8's conformance fixture, against the real shared checks: a fresh folder
    after `setup <path>` passes them, and each contract file breaks its own gate."""

    def checks_one(self, name, repo):
        r = subprocess.run([str(CHECKS_CLI), "one", name, str(repo), "--json"],
                           capture_output=True, text=True, env=self.env)
        (res,) = json.loads(r.stdout)["results"]
        return res

    def test_every_contract_gate_exists(self):
        r = subprocess.run([str(CHECKS_CLI), "list", "--json"], capture_output=True, text=True, env=self.env)
        names = {x["name"] for x in json.loads(r.stdout)["checks"]}
        self.assertEqual(sorted(set(GATES) - names), [])

    def test_a_fresh_folder_passes_every_shared_check(self):
        code, res = self.run_json("fresh", "--checks", str(CHECKS_CLI))
        self.assertEqual((code, res["gates"]["status"]), (0, "unchanged"), res["gates"])
        repo = self.tmp / "fresh"
        self.assertEqual(self.checks_one("services-valid", repo)["status"], "ok")
        self.assertEqual(self.checks_one("accessor", repo)["status"], "ok")

    def test_a_verb_the_check_command_does_not_implement_turns_the_line_red(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        doc = load(repo / "services.json")
        doc["services"][0]["verbs"].append("deploy")
        (repo / "services.json").write_text(json.dumps(doc))
        commit_all(repo, "a verb dev.sh lacks")
        code, res = self.run_json("fresh", "--checks", str(CHECKS_CLI))
        self.assertEqual((code, res["gates"]["status"]), (1, "drift"))
        self.assertIn("services-valid", res["gates"]["detail"])

    def test_a_store_without_cli_json_turns_the_line_red(self):
        self.run_json("fresh")
        repo = self.tmp / "fresh"
        (repo / "data.db").write_bytes(b"")
        commit_all(repo, "a store")
        code, res = self.run_json("fresh", "--checks", str(CHECKS_CLI))
        self.assertEqual((code, res["gates"]["status"]), (1, "drift"))
        self.assertIn("accessor", res["gates"]["detail"])

    def test_a_node_tree_passes_once_jacob_applies_the_registry(self):
        self.run_json("top")
        top = self.tmp / "top"
        write_node(top, children=["alpha", "beta"])
        code, doc = self.node_run(top)
        self.assertEqual(code, 1)  # no registry yet: registry-matches is red, and says so
        top_res = {x["component"]: x for x in doc["results"]}
        self.assertEqual(top_res["registry"]["status"], "needs-jacob")
        self.assertEqual(top_res["gates"]["status"], "drift")
        self.assertIn("registry-matches", top_res["gates"]["detail"])
        os.replace(top / "registry.proposed.json", top / "registry.json")  # Jacob's step
        name_registry(top)
        code, doc = self.node_run(top)
        self.assertEqual(code, 0, doc)
        top_res = {x["component"]: x for x in doc["results"]}
        self.assertEqual((top_res["registry"]["status"], top_res["gates"]["status"]), ("unchanged", "unchanged"))
        for kid in doc["children"]:
            self.assertEqual({x["component"]: x["status"] for x in kid["results"]}["gates"], "unchanged", kid)

    def node_run(self, top):
        r = self.run_setup(top.name, "--node", "--json", "--checks", str(CHECKS_CLI))
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return r.returncode, json.loads(r.stdout)
