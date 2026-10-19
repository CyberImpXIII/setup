"""PLAN-repo-setup §7.5 and §7.10: a node is a repo with a node.json naming its
generated files, its record files, its children, and the command that re-renders it.
The shape is the shared checks' (their rendered-matches and regenerate read it too):
the live tests at the bottom hold setup's reading and theirs together.

`setup <path> --node` sets the node up, then each child it declares (created when
absent, as a repo nested in the node; a child with its own node.json recurses).
`--rebuild` renders every generated file again, in place, and prints one line per
file: regenerated, drift, record, unaccounted, failed. It never writes a record, nor
a generated file carrying uncommitted changes; `--dry-run` writes nothing."""
import json
import re
import subprocess
import unittest

from setuplib import core
from tests.helpers import DOCS_DECLARATION, ROOT, SETUP, Case, git, git_repo, hook_listing, snapshot, workspace_cli

HOOK_FILES = sorted(rel for rel, _ in hook_listing() or [])  # what the hooks dependency lists
GITHOOKS = next(c for c in core.load_spec()["components"] if c["name"] == "githooks")
SCAFFOLD = ["CLAUDE.md", "TODO.md", "dev.sh", "services.json", "checks.json", ".gitignore", "devtools/parts.py",
            ".claude/settings.json", *HOOK_FILES, *(f"{GITHOOKS['dir']}/{f}" for f in GITHOOKS["files"]),
            *DOCS_DECLARATION]
CHECKS_CLI = workspace_cli("checks")[1]
REBUILD = [str(SETUP), ".", "--node", "--rebuild"]
ID = ["-c", "user.email=t@example.invalid", "-c", "user.name=t"]
# A repo's description (PLAN-architecture §9 step 10.2): a fixture node is created with
# it and its node.json's rebuild carries it, as an input of the render (services.json
# without one is drift on the next run; tests/test_contract.py Description holds that)
DESC = "Turns plain notes into dated entries."
NODE_REBUILD = [*REBUILD, "--description", DESC]


def commit_all(repo, msg="node config"):
    git(["add", "-A"], repo)
    r = git([*ID, "commit", "-q", "-m", msg], repo)
    assert r.returncode == 0, r.stderr + r.stdout


def describe(repo, text=DESC):
    """The owner's step for a repo setup created without a description (a node's
    child): add it to services.json and commit."""
    doc = json.loads((repo / "services.json").read_text())
    name, *rest = doc.items()  # after the name, where setup's render puts it
    doc = dict([name, ("description", text), *rest])
    (repo / "services.json").write_text(json.dumps(doc, indent=2) + "\n")
    commit_all(repo, "described")


def write_node(repo, children=(), generated=SCAFFOLD, record=(), commit=True, **extra):
    doc = {"rebuild": NODE_REBUILD, "generated": list(generated), "record": list(record), **extra}
    if children:
        doc["children"] = list(children)
    (repo / "node.json").write_text(json.dumps(doc, indent=2) + "\n")
    if commit:
        commit_all(repo)


def node_line(doc):
    """The node component's result in a run's document."""
    (line,) = [r for r in doc["results"] if r["component"] == "node"]
    return line


def statuses(doc):
    """Every result status in a run's document, children included."""
    out = [r["status"] for r in doc["results"]]
    for kid in doc.get("children", []):
        out += statuses(kid)
    return out


class NodeCase(Case):
    def tree(self, top="top", *args):
        """A node created by setup from nothing, with its description."""
        code, _ = self.run_json(top, "--description", DESC, *args)
        self.assertEqual(code, 0)
        return self.tmp / top

    def run_doc(self, *args):
        r = self.run_setup(*args, "--json")
        self.assertIn(r.returncode, (0, 1), r.stderr)
        return r.returncode, json.loads(r.stdout)

    def by_path(self, lines):
        return {x["path"]: x for x in lines}


class Node(NodeCase):
    def test_without_the_flag_node_json_is_read_by_nothing(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        _, res = self.run_json("top")
        self.assertEqual(res["node"]["status"], "none")
        self.assertFalse((top / "alpha").exists())

    def test_node_flag_without_node_json_fails(self):
        git_repo(self.tmp / "r")
        code, res = self.run_json("r", "--node")
        self.assertEqual((code, res["node"]["status"]), (1, "failed"))
        self.assertIn("no node.json", res["node"]["detail"])

    def test_rebuild_without_node_renders_no_generated_file(self):
        # without --node, --rebuild means the hook copies (tests/test_rebuild.py): with
        # --only naming another component it renders nothing, a usage error
        git_repo(self.tmp / "r")
        self.assertEqual(self.run_setup("r", "--rebuild", "--only", "rules").returncode, 2)

    def test_two_level_tree_from_an_empty_folder(self):
        # §7.5's fixture: each level rendered from the same templates with its own data
        (self.tmp / "top").mkdir()
        top = self.tree()
        write_node(top, children=["alpha", "beta"])
        code, doc = self.run_doc("top", "--node")
        self.assertEqual(code, 0, doc)
        kids = self.by_path(doc["children"])
        self.assertEqual(sorted(kids), ["top/alpha", "top/beta"])
        for name in ("alpha", "beta"):
            repo = top / name
            st = {r["component"]: r["status"] for r in kids[f"top/{name}"]["results"]}
            self.assertEqual((st["repo"], st["commit"], st["node"]), ("installed", "installed", "none"))
            self.assertEqual(git(["rev-parse", "--show-toplevel"], repo).stdout.strip(), str(repo))
            self.assertEqual(sorted(git(["ls-files"], repo).stdout.split()), sorted(SCAFFOLD))
            self.assertEqual((repo / "TODO.md").read_text().splitlines()[0], f"# {name} TODO")
        self.assertIn("2 created", node_line(doc)["detail"])
        for name in ("alpha", "beta"):  # setup never guesses a child's description: its owner's step
            describe(top / name)
        # the second level: alpha becomes a node of its own, and the top recurses into it
        write_node(top / "alpha", children=["gamma"], record=["node.json"])
        code, doc = self.run_doc("top", "--node")
        self.assertEqual(code, 0, doc)
        alpha = self.by_path(doc["children"])["top/alpha"]
        (gamma,) = alpha["children"]
        self.assertEqual(gamma["path"], "top/alpha/gamma")
        self.assertEqual(git(["rev-parse", "--show-toplevel"], top / "alpha/gamma").stdout.strip(),
                         str(top / "alpha/gamma"))
        # gamma's owner describes it, which changes alpha's registry proposal (the union)
        describe(top / "alpha/gamma")
        self.assertEqual(self.run_doc("top", "--node")[0], 0)
        # and a run on the settled tree writes nothing, anywhere
        before = snapshot(top)
        code, doc = self.run_doc("top", "--node")
        self.assertEqual(code, 0)
        after = snapshot(top)
        self.assertEqual(sorted(p for p in {*before, *after} if before.get(p) != after.get(p)), [])
        self.assertNotIn("installed", statuses(doc))

    def test_bad_node_json_fails_and_creates_nothing(self):
        cases = {
            "climbs out": {"children": ["../out"]}, "absolute": {"children": ["/abs"]},
            "the node itself": {"children": ["."]}, "twice": {"children": ["alpha", "./alpha"]},
            "child in a child": {"children": ["alpha", "alpha/inner"]}, "empty path": {"children": [""]},
            "not a string": {"children": [3]}, "unknown key": {"kids": []},
            "no rebuild": {"rebuild": None}, "empty rebuild": {"rebuild": []},
            "generated glob": {"generated": ["*.md"]},
            "generated and record": {"generated": ["x.md"], "record": ["*.md"]},
            "generated under a child": {"children": ["alpha"], "generated": ["alpha/x"]},
            "registry outside": {"registry": "../reg.json"},
        }
        for i, (why, change) in enumerate(cases.items()):
            with self.subTest(why):
                top = self.tree(f"t{i}")
                doc = {"rebuild": REBUILD, "generated": [], "record": [], **change}
                doc = {k: v for k, v in doc.items() if v is not None}
                (top / "node.json").write_text(json.dumps(doc))
                before = snapshot(top)
                code, res = self.run_json(top.name, "--node")
                self.assertEqual((code, res["node"]["status"]), (1, "failed"), why)
                self.assertEqual(snapshot(top), before)
                self.assertFalse((self.tmp / "out").exists())

    def test_a_good_node_json_passes_the_same_validation(self):
        # the counterfactual to the cases above: the rules do not refuse everything
        top = self.tree()
        write_node(top, children=["alpha", "beta"], record=["notes/*", "node.json"], commit=False)
        code, res = self.run_json("top", "--node")
        self.assertEqual((code, res["node"]["status"]), (0, "installed"))

    def test_one_refused_child_does_not_stop_the_others(self):
        top = self.tree()
        write_node(top, children=["alpha", "taken"])
        (top / "taken").mkdir()
        (top / "taken/someones.txt").write_text("x\n")
        code, doc = self.run_doc("top", "--node")
        self.assertEqual(code, 1)
        kids = self.by_path(doc["children"])
        self.assertEqual(kids["top/taken"]["results"][0]["status"], "failed")
        self.assertIn("refused", kids["top/taken"]["results"][0]["detail"])
        self.assertEqual((top / "taken/someones.txt").read_text(), "x\n")
        self.assertTrue((top / "alpha/.git").is_dir())

    def test_an_empty_declared_folder_becomes_the_child(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        (top / "alpha").mkdir()
        code, _ = self.run_doc("top", "--node")
        self.assertEqual(code, 0)
        self.assertEqual(git(["rev-parse", "--show-toplevel"], top / "alpha").stdout.strip(), str(top / "alpha"))

    def test_an_undeclared_folder_in_a_node_is_still_refused(self):
        # nesting is allowed only for a child the node declares
        top = self.tree()
        write_node(top, children=["alpha"])
        self.assertEqual(self.run_setup("top/other").returncode, 2)
        self.assertFalse((top / "other").exists())
        (top / "empty").mkdir()
        self.assertEqual(self.run_setup("top/empty").returncode, 2)
        self.assertEqual(list((top / "empty").iterdir()), [])

    def test_dry_run_creates_no_child(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        before = snapshot(top)
        code, doc = self.run_doc("top", "--node", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(top), before)
        (alpha,) = doc["children"]
        self.assertEqual(alpha["results"][0]["status"], "installed")
        self.assertIn("would", alpha["results"][0]["detail"])

    def test_children_are_not_given_a_github_repo(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        _, doc = self.run_doc("top", "--node", "--github")
        (alpha,) = doc["children"]
        st = {r["component"]: r["status"] for r in alpha["results"]}
        self.assertEqual(st["remote"], "none")
        self.assertEqual(git(["remote"], top / "alpha").stdout.strip(), "")

    def test_text_output_shows_children_and_rebuild_lines(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        r = self.run_setup("top", "--node", "--rebuild", "--dry-run")
        self.assertRegex(r.stdout, r"(?m)^  child top/alpha: ok$")
        self.assertRegex(r.stdout, r"(?m)^    regenerated  TODO\.md ")


class Rebuild(NodeCase):
    def rebuild(self, *args, top="top"):
        code, doc = self.run_doc(top, "--node", "--rebuild", "--description", DESC, *args)
        return code, doc, self.by_path(doc["rebuild"])

    def test_a_scaffold_regenerates_byte_for_byte_and_nothing_is_written(self):
        top = self.tree()
        write_node(top)
        before = snapshot(top)
        code, doc, lines = self.rebuild()
        self.assertEqual(code, 0, doc["rebuild"])
        for p in SCAFFOLD:
            self.assertEqual(lines[p]["status"], "regenerated", p)
        self.assertEqual(lines["node.json"]["status"], "record")
        self.assertEqual({x["status"] for x in doc["rebuild"]}, {"regenerated", "record"})
        self.assertEqual(node_line(doc)["status"], "unchanged")
        self.assertEqual(snapshot(top), before)

    def test_deleted_generated_files_are_rendered_back(self):
        # the shared checks' engine deletes every generated file in its copy, then runs this
        top = self.tree()
        write_node(top)
        want = {p: (top / p).read_bytes() for p in SCAFFOLD}
        for p in SCAFFOLD:
            (top / p).unlink()
        code, doc, lines = self.rebuild()
        self.assertEqual(code, 0, doc["rebuild"])
        self.assertEqual({lines[p]["status"] for p in SCAFFOLD}, {"regenerated"})
        self.assertEqual({p: (top / p).read_bytes() for p in SCAFFOLD}, want)
        self.assertEqual(git(["status", "--porcelain"], top).stdout, "")

    def test_a_committed_hand_edit_is_drift_and_the_render_is_written(self):
        top = self.tree()
        write_node(top)
        rendered = (top / "TODO.md").read_text()
        (top / "TODO.md").write_text(rendered + "edited by hand\n")
        commit_all(top, "edit a generated file")
        code, doc, lines = self.rebuild()
        self.assertEqual((code, lines["TODO.md"]["status"]), (0, "drift"))
        self.assertIn("git diff", lines["TODO.md"]["detail"])
        self.assertEqual(lines["CLAUDE.md"]["status"], "regenerated")
        self.assertEqual((top / "TODO.md").read_text(), rendered)
        self.assertIn("-edited by hand", git(["diff"], top).stdout)
        self.assertEqual(node_line(doc)["status"], "installed")

    def test_dry_run_reports_the_drift_and_writes_nothing(self):
        top = self.tree()
        write_node(top)
        (top / "TODO.md").write_text("edited\n")
        commit_all(top, "edit")
        before = snapshot(top)
        _, _, lines = self.rebuild("--dry-run")
        self.assertEqual(lines["TODO.md"]["status"], "drift")
        self.assertIn("would write", lines["TODO.md"]["detail"])
        self.assertEqual(snapshot(top), before)

    def test_an_uncommitted_edit_is_drift_and_kept(self):
        top = self.tree()
        write_node(top)
        (top / "TODO.md").write_text("mine, not committed\n")
        code, _, lines = self.rebuild()
        self.assertEqual((code, lines["TODO.md"]["status"]), (0, "drift"))
        self.assertIn("uncommitted", lines["TODO.md"]["detail"])
        self.assertEqual((top / "TODO.md").read_text(), "mine, not committed\n")

    def test_a_mode_change_is_drift(self):
        top = self.tree()
        write_node(top)
        (top / "dev.sh").chmod(0o644)
        commit_all(top, "mode")
        code, _, lines = self.rebuild()
        self.assertEqual((code, lines["dev.sh"]["status"]), (0, "drift"))
        self.assertIn("mode", lines["dev.sh"]["detail"])
        self.assertTrue((top / "dev.sh").stat().st_mode & 0o100)

    def test_a_stray_file_is_unaccounted(self):
        top = self.tree()
        write_node(top)
        (top / "stray.txt").write_text("x\n")
        code, _, lines = self.rebuild()
        self.assertEqual((code, lines["stray.txt"]["status"]), (0, "unaccounted"))
        self.assertTrue((top / "stray.txt").is_file())

    def test_an_ignored_file_is_not_unaccounted(self):
        top = self.tree()
        write_node(top)
        (top / "local.env").write_text("K=v\n")  # the baseline ignores *.env
        _, _, lines = self.rebuild()
        self.assertNotIn("local.env", lines)

    def test_a_record_is_never_written(self):
        top = self.tree()
        (top / "notes").mkdir()
        (top / "notes/keep.md").write_text("content\n")
        (top / "PLAN-a.md").write_text("plan\n")
        write_node(top, record=["notes/*", "PLAN-*.md"])
        (top / "notes/keep.md").write_text("changed, not committed\n")
        code, _, lines = self.rebuild()
        self.assertEqual(code, 0)
        self.assertEqual(lines["notes/keep.md"]["status"], "record")
        self.assertEqual(lines["PLAN-a.md"]["status"], "record")
        self.assertEqual((top / "notes/keep.md").read_text(), "changed, not committed\n")

    def test_a_file_setup_does_not_render_fails_and_is_not_touched(self):
        top = self.tree()
        (top / "out.txt").write_text("one\n")
        write_node(top, generated=[*SCAFFOLD, "out.txt"])
        code, doc, lines = self.rebuild()
        self.assertEqual((code, lines["out.txt"]["status"]), (1, "failed"))
        self.assertEqual(node_line(doc)["status"], "failed")
        self.assertEqual((top / "out.txt").read_text(), "one\n")

    def test_a_generated_file_in_neither_the_tree_nor_the_commit_is_drift_and_rendered(self):
        # not TODO.md: the docs declaration names it, so its absence is the docs line's drift too
        top = self.tree()
        write_node(top)
        git(["rm", "-q", "checks.json"], top)
        commit_all(top, "drop")
        code, _, lines = self.rebuild()
        self.assertEqual((code, lines["checks.json"]["status"]), (0, "drift"))
        self.assertIn("neither", lines["checks.json"]["detail"])
        self.assertTrue((top / "checks.json").is_file())

    def test_the_render_is_for_this_node(self):
        # the name changes the output: proof the render takes this node's data
        top = self.tree()
        write_node(top)
        _, _, lines = self.rebuild("--name", "other")
        self.assertEqual(lines["TODO.md"]["status"], "drift")
        self.assertEqual((top / "TODO.md").read_text().splitlines()[0], "# other TODO")

    def test_a_plugin_that_applies_here_is_rendered_here(self):
        # the render runs in a throwaway folder; a plug-in registry is matched against the node's path
        reg = self.tmp / "plugins.json"
        reg.write_text(json.dumps({"root": str(self.tmp / "top"), "ok": True, "plugins": [
            {"name": "p", "applies_to": "repos:.", "faults": [], "registration": {"Stop": [{"hooks": [
                {"type": "command", "command": "$CLAUDE_PROJECT_DIR/kb/p.sh"}]}]}}]}))
        top = self.tree("top", "--plugins", str(reg))
        self.assertIn("kb/p.sh", (top / ".claude/settings.json").read_text())
        write_node(top)
        _, _, lines = self.rebuild("--plugins", str(reg))
        self.assertEqual(lines[".claude/settings.json"]["status"], "regenerated")
        # counterfactual: without the registry the render lacks it
        _, _, lines = self.rebuild("--dry-run")
        self.assertEqual(lines[".claude/settings.json"]["status"], "drift")

    def test_children_are_not_the_parents_files_and_a_child_node_rebuilds_itself(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        self.run_doc("top", "--node")
        describe(top / "alpha")
        write_node(top / "alpha")  # its command declares the description it was given
        (top / "alpha/stray.txt").write_text("x\n")
        code, doc, lines = self.rebuild()
        self.assertEqual(code, 0)
        self.assertEqual([p for p in lines if p.startswith("alpha")], [])
        (alpha,) = doc["children"]
        kid = self.by_path(alpha["rebuild"])
        self.assertEqual(kid["stray.txt"]["status"], "unaccounted")
        self.assertEqual(kid["TODO.md"]["status"], "regenerated")
        # rendered with the description its own node.json declares, not the parent's flag's absence
        self.assertEqual(kid["services.json"]["status"], "regenerated")
        self.assertEqual(json.loads((top / "alpha/services.json").read_text())["description"], DESC)

    def test_an_absent_child_is_not_created_by_a_rebuild(self):
        top = self.tree()
        write_node(top, children=["alpha"])
        self.rebuild()
        self.assertFalse((top / "alpha").exists())

    def test_rebuild_statuses_declared_equal_emitted(self):
        src = (ROOT / "setuplib" / "node.py").read_text()
        emitted = set(re.findall(r'Line\([^,]+, "([a-z]+)"', src))
        self.assertEqual(emitted, set(core.load_spec()["rebuild_statuses"]))
        out = self.run_setup("components").stdout
        for k in core.load_spec()["rebuild_statuses"]:
            self.assertRegex(out, r"(?m)^  " + k + r"\s")

    def test_the_render_list_names_components_and_not_node(self):
        spec = core.load_spec()
        names = [c["name"] for c in spec["components"]]
        render = next(c for c in spec["components"] if c["name"] == "node")["render"]
        self.assertTrue(set(render) <= set(names))
        self.assertNotIn("node", render)


@unittest.skipIf(CHECKS_CLI is None, "no shared checks CLI in a workspace around this tool (a lone clone)")
class LiveChecks(NodeCase):
    """The seam with the shared checks, which read node.json too and run this rebuild
    in a copy. Run as subprocesses, never imported."""

    def checks(self, *args):
        r = subprocess.run([str(CHECKS_CLI), *args, "--json"], capture_output=True, text=True, env=self.env)
        try:
            doc = json.loads(r.stdout)
        except ValueError as e:
            self.fail(f"checks {' '.join(args)} printed no JSON ({e}): {r.stderr[-400:]}")
        return doc

    def run_all(self, repo):
        return {x["check"]: x for x in self.checks("run", str(repo))["results"]}

    def one(self, name, repo):
        """One gate's result on repo, whether or not it applies there; None when the
        shared checks have no such gate (reported by the skip, never read as a pass)."""
        if name not in {x["name"] for x in self.checks("list")["checks"]}:
            return None
        (res,) = self.checks("one", name, str(repo))["results"]
        return res

    def test_every_repo_of_a_two_level_tree_passes_the_shared_checks(self):
        top = self.tree()
        # a node with children names a registry (registry-matches): Jacob applies the
        # proposal setup renders, the union of the services.json files under the node
        write_node(top, children=["alpha", "beta"], record=["registry.json"], registry="registry.json")
        self.run_doc("top", "--node")
        for name in ("alpha", "beta"):  # each owner's step; alpha's equals its node.json's --description
            describe(top / name)
        write_node(top / "alpha", children=["gamma"], record=["registry.json"], registry="registry.json")
        self.run_doc("top", "--node")
        describe(top / "alpha/gamma")
        self.run_doc("top", "--node")  # the proposals again, now carrying the descriptions
        for node in (top, top / "alpha"):
            (node / "registry.proposed.json").replace(node / "registry.json")
            for args in (["add", "registry.json"], [*ID, "commit", "-q", "-m", "registry"]):
                self.assertEqual(git(args, node).returncode, 0, node)
        code, doc = self.run_doc("top", "--node")
        self.assertEqual(code, 0, doc)
        self.assertEqual({r["component"]: r["status"] for r in doc["results"]}["registry"], "unchanged")
        for repo in (top, top / "alpha", top / "beta", top / "alpha/gamma"):
            red = [(k, x["status"], x.get("lines")) for k, x in self.run_all(repo).items()
                   if x["status"] in ("fail", "error")]
            self.assertEqual(red, [], repo)

    def test_the_shared_rebuild_gates_agree_both_ways(self):
        top = self.tree()
        write_node(top)
        for gate in ("rendered-matches", "regenerate"):
            with self.subTest(gate):
                res = self.one(gate, top)
                if res is None:
                    self.skipTest(f"the shared checks have no {gate} gate")
                self.assertEqual(res["status"], "ok", res)
        (top / "TODO.md").write_text("edited\n")
        commit_all(top, "edit")
        for gate in ("rendered-matches", "regenerate"):
            with self.subTest(gate):
                res = self.one(gate, top)
                self.assertEqual(res["status"], "fail", res)
                self.assertTrue(any("TODO.md" in x for x in res.get("lines", [])), res)
