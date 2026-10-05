"""PLAN-repo-setup.md §7.11: the data component. A repo whose cli.json declares an
`import` verb and whose store is absent gets its store from its export in the data
repo: setup runs `<cli> import`, then `<cli> verify --json`, with DATA_REPO (the data
repo's root, from --data-repo or the environment) passed through. The line is
`installed` only when the store is on disk afterwards and every verified item is
`same`. An existing store is never dropped; DATA_REPO unset is needs-jacob, never an
empty store that looks installed.

The store CLI here is tests/fake_store.py; the live class at the bottom holds the
contract to the shared checks (accessor on the cli.json, stores-exported on the
generated store), run as a subprocess, never imported."""
import json
import os
import shutil
import subprocess
import unittest

from tests.helpers import ROOT, Case, git_repo, snapshot, workspace_cli
from tests.test_node import commit_all, write_node

FAKE = ROOT / "tests" / "fake_store.py"
CHECKS_CLI = workspace_cli("checks")[1]
VERBS = ["import", "export", "verify"]
ROWS = {"a": 1, "b": [2, 3]}


def store_repo(path, store="data/store.db", verbs=VERBS, cli="tool"):
    """A repo with the fake store CLI and a cli.json naming it; the store git-ignored."""
    repo = git_repo(path)
    shutil.copy(FAKE, repo / "tool")
    os.chmod(repo / "tool", 0o755)
    (repo / "cli.json").write_text(json.dumps({"store": store, "cli": cli, "verbs": verbs}, indent=2) + "\n")
    (repo / ".gitignore").write_text("data/\n")
    commit_all(repo, "a store CLI")
    return repo


def export(data, name, rows=ROWS):
    d = data / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "items.json").write_text(json.dumps(rows))
    return data


class Data(Case):
    def setUp(self):
        super().setUp()
        self.log = self.tmp / "store.log"
        self.env["FAKE_STORE_LOG"] = str(self.log)
        self.data = export(self.tmp / "datarepo", "r")
        self.repo = store_repo(self.tmp / "r")

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def store(self):
        p = self.repo / "data/store.db"
        return json.loads(p.read_text()) if p.exists() else None

    def with_data(self, *args):
        self.env["DATA_REPO"] = str(self.data)
        return self.run_json("r", *args)

    # ---- the store emerges ------------------------------------------------

    def test_an_absent_store_is_imported_and_verified(self):
        code, res = self.with_data()
        self.assertEqual((code, res["data"]["status"]), (0, "installed"), res["data"])
        self.assertEqual(self.store(), ROWS)
        self.assertEqual([c["argv"] for c in self.calls()], [["import"], ["verify", "--json"]])
        self.assertEqual({c["DATA_REPO"] for c in self.calls()}, {str(self.data)})
        self.assertIn("2 item(s) same", res["data"]["detail"])

    def test_the_flag_names_the_data_repo_and_a_relative_one_is_resolved(self):
        self.env["DATA_REPO"] = str(self.tmp / "elsewhere")
        code, res = self.run_json("r", "--data-repo", "datarepo")
        self.assertEqual((code, res["data"]["status"]), (0, "installed"), res["data"])
        self.assertEqual({c["DATA_REPO"] for c in self.calls()}, {str(self.data)})

    def test_the_store_is_not_committed(self):
        self.with_data()
        self.assertIsNotNone(self.store())
        r = subprocess.run(["git", "log", "--all", "--name-only", "--format="], cwd=self.repo,
                           capture_output=True, text=True)
        self.assertNotIn("data/store.db", r.stdout.split())

    # ---- nothing to do, or not setup's to do --------------------------------

    def test_no_cli_json_is_none(self):
        git_repo(self.tmp / "plain")
        self.env["DATA_REPO"] = str(self.data)
        _, res = self.run_json("plain")
        self.assertEqual(res["data"]["status"], "none")

    def test_an_existing_store_is_never_dropped(self):
        (self.repo / "data").mkdir()
        (self.repo / "data/store.db").write_text('{"mine": 0}')
        code, res = self.with_data()
        self.assertEqual((code, res["data"]["status"]), (0, "unchanged"), res["data"])
        self.assertEqual(self.store(), {"mine": 0})
        self.assertEqual(self.calls(), [])

    def test_data_repo_unset_is_needs_jacob_and_no_store(self):
        self.env.pop("DATA_REPO", None)
        code, res = self.run_json("r")
        self.assertEqual((code, res["data"]["status"]), (0, "needs-jacob"), res["data"])
        self.assertIn("DATA_REPO", res["data"]["detail"])
        self.assertIsNone(self.store())
        self.assertEqual(self.calls(), [])

    def test_data_repo_not_a_folder_is_needs_jacob(self):
        code, res = self.run_json("r", "--data-repo", "no-such-folder")
        self.assertEqual((code, res["data"]["status"]), (0, "needs-jacob"), res["data"])
        self.assertIn("not a folder", res["data"]["detail"])
        self.assertEqual(self.calls(), [])

    def test_the_detail_names_the_key_never_the_path(self):
        _, res = self.with_data()
        self.assertNotIn(str(self.data), res["data"]["detail"])

    def test_a_store_partly_present_is_needs_owner(self):
        repo = store_repo(self.tmp / "two", store=["data/store.db", "data/other.db"])
        (repo / "data").mkdir()
        (repo / "data/other.db").write_text("{}")
        self.env["DATA_REPO"] = str(self.data)
        code, res = self.run_json("two")
        self.assertEqual((code, res["data"]["status"]), (0, "needs-owner"), res["data"])
        self.assertIn("data/store.db", res["data"]["detail"])
        self.assertEqual(self.calls(), [])

    def test_a_glob_store_with_a_match_is_present(self):
        repo = store_repo(self.tmp / "glob", store="data/*.db")
        (repo / "data").mkdir()
        (repo / "data/x.db").write_text("{}")
        self.env["DATA_REPO"] = str(self.data)
        _, res = self.run_json("glob")
        self.assertEqual(res["data"]["status"], "unchanged")

    def test_no_import_verb_is_none(self):
        store_repo(self.tmp / "ro", verbs=["verify"])
        self.env["DATA_REPO"] = str(self.data)
        _, res = self.run_json("ro")
        self.assertEqual(res["data"]["status"], "none")
        self.assertEqual(self.calls(), [])

    def test_import_without_verify_is_never_run(self):
        store_repo(self.tmp / "nv", verbs=["import"])
        self.env["DATA_REPO"] = str(self.data)
        _, res = self.run_json("nv")
        self.assertEqual(res["data"]["status"], "needs-owner")
        self.assertIn("verify", res["data"]["detail"])
        self.assertEqual(self.calls(), [])

    def test_a_dry_run_runs_nothing(self):
        before = snapshot(self.repo)
        code, res = self.with_data("--dry-run")
        self.assertEqual((code, res["data"]["status"]), (0, "installed"))
        self.assertIn("would", res["data"]["detail"])
        self.assertEqual(self.calls(), [])
        self.assertEqual(snapshot(self.repo), before)

    # ---- the owner's cli.json, refused before anything runs -----------------

    def refuses(self, doc, why):
        (self.repo / "cli.json").write_text(doc if isinstance(doc, str) else json.dumps(doc))
        commit_all(self.repo, "edit cli.json")
        code, res = self.with_data()
        self.assertEqual((code, res["data"]["status"]), (1, "drift"), res["data"])
        self.assertIn(why, res["data"]["detail"])
        self.assertEqual(self.calls(), [])

    def test_cli_json_not_json_is_drift(self):
        self.refuses("{", "does not parse")

    def test_cli_json_without_its_fields_is_drift(self):
        self.refuses({"store": "data/store.db", "verbs": VERBS}, "no `cli`")
        self.refuses({"store": [], "cli": "tool", "verbs": VERBS}, "no `store`")

    def test_a_cli_outside_the_repo_is_never_run(self):
        self.refuses({"store": "data/store.db", "cli": "../r/tool", "verbs": VERBS}, "../r/tool: not a relative")

    def test_an_absolute_cli_is_never_run(self):
        self.refuses({"store": "data/store.db", "cli": str(self.repo / "tool"), "verbs": VERBS}, "not a relative")

    def test_a_store_outside_the_repo_is_drift(self):
        self.refuses({"store": "../elsewhere.db", "cli": "tool", "verbs": VERBS}, "../elsewhere.db: not a relative")

    # ---- the reported result, not the exit code ---------------------------

    def broken(self, mode, status, why):
        self.env["FAKE_STORE_MODE"] = mode
        code, res = self.with_data()
        self.assertEqual((code, res["data"]["status"]), (1 if status == "failed" else 0, status), res["data"])
        self.assertIn(why, res["data"]["detail"])
        return res

    def test_import_failing_is_failed(self):
        self.broken("fail", "failed", "cannot read the export")

    def test_import_that_writes_nothing_is_failed(self):
        self.broken("lie", "failed", "no store")

    def test_a_differing_item_is_failed(self):
        self.broken("differs", "failed", "differs")

    def test_a_verify_with_no_items_is_failed(self):
        self.broken("empty", "failed", "verify")

    def test_a_verify_exiting_non_zero_over_all_same_is_failed(self):
        self.broken("exit", "failed", "exited 1")

    def test_an_item_that_cannot_be_compared_is_never_a_pass(self):
        res = self.broken("unavailable", "needs-jacob", "unavailable")
        self.assertIn("never a pass", res["data"]["detail"])

    # ---- a node passes the data repo to its children -------------------------

    def test_a_node_child_gets_its_store(self):
        top = git_repo(self.tmp / "top")
        shutil.move(str(self.repo), str(top / "alpha"))
        export(self.data, "alpha")
        write_node(top, children=["alpha"])
        self.env["DATA_REPO"] = str(self.data)
        r = self.run_setup("top", "--node", "--json")
        doc = json.loads(r.stdout)
        (kid,) = doc["children"]
        line = next(x for x in kid["results"] if x["component"] == "data")
        self.assertEqual(line["status"], "installed", line)
        self.assertEqual(json.loads((top / "alpha/data/store.db").read_text()), ROWS)


@unittest.skipIf(CHECKS_CLI is None, "no shared checks CLI in a workspace around this tool (a lone clone)")
class LiveData(Case):
    """The contract the store CLIs consume, held to the shared checks: the fixture's
    cli.json passes accessor, and the store setup generated passes stores-exported."""

    def one(self, gate, repo):
        r = subprocess.run([str(CHECKS_CLI), "one", gate, str(repo), "--json"],
                           capture_output=True, text=True, env=self.env)
        (res,) = json.loads(r.stdout)["results"]
        return res

    def test_the_generated_store_passes_the_shared_gates(self):
        data = export(self.tmp / "datarepo", "r")
        repo = store_repo(self.tmp / "r")
        self.env["DATA_REPO"] = str(data)
        code, res = self.run_json("r")
        self.assertEqual((code, res["data"]["status"]), (0, "installed"), res["data"])
        self.assertEqual(self.one("accessor", repo)["status"], "ok")
        self.assertEqual(self.one("stores-exported", repo)["status"], "ok")

    def test_a_store_changed_without_its_export_is_red_there(self):
        data = export(self.tmp / "datarepo", "r")
        repo = store_repo(self.tmp / "r")
        self.env["DATA_REPO"] = str(data)
        self.run_json("r")
        (repo / "data/store.db").write_text(json.dumps({**ROWS, "a": 9}))
        self.assertEqual(self.one("stores-exported", repo)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
