"""The repo list block (PLAN-architecture.md §13.1 G9): rendered from the names file
handed with --names, between names:repos markers; behind, updated; edited locally,
drift; no block, drift saying where it goes; without --names, none."""
import json

from setuplib.core import render_repolist, sha12
from tests.helpers import Case, commit_all, git_repo

NAMES = {"locations": [
    {"name": "zeta", "dir": "tools/zeta", "store": "zeta", "remote": "owner/zeta", "agent": "zeta"},
    {"name": "alpha", "dir": "alpha", "store": None, "remote": "owner/alpha", "agent": "alpha"},
    {"name": "top", "dir": ".", "store": "top", "remote": None, "agent": None},
    {"name": "quiet", "dir": "tools/quiet", "store": None, "remote": None, "agent": "quiet"}]}
AFTER = "- Each tool is its own repo:"


def block(body, mark=None):
    return f"<!-- names:repos@{mark or sha12(body)} -->\n{body}<!-- /names:repos -->\n"


class RepoList(Case):
    def names_file(self, doc=NAMES):
        p = self.tmp / "names.json"
        p.write_text(json.dumps(doc) + "\n")
        return p

    def repo_with(self, text):
        repo = git_repo(self.tmp / "r")
        (repo / "CLAUDE.md").write_text(text)
        commit_all(repo)
        return repo

    def test_the_render_is_one_bullet_per_remote_sorted_by_folder_then_the_local_ones(self):
        body = render_repolist(NAMES)
        self.assertEqual(body, "- `alpha/` → `github.com/owner/alpha`\n- `tools/zeta/` → `github.com/owner/zeta`\n"
                               "- Local only, no remote: the top folder, `tools/quiet/`\n")
        self.assertEqual(render_repolist(NAMES), body, "two renders are byte-identical")

    def test_a_current_block_is_unchanged_and_a_second_run_writes_nothing(self):
        body = render_repolist(NAMES)
        repo = self.repo_with(f"# r\n\n{AFTER}\n{block(body)}\nown text\n")
        before = (repo / "CLAUDE.md").read_bytes()
        code, res = self.run_json("r", "--only", "repolist", "--names", self.names_file())
        self.assertEqual((code, res["repolist"]["status"]), (0, "unchanged"))
        self.assertEqual((repo / "CLAUDE.md").read_bytes(), before)

    def test_a_changed_names_file_updates_the_block_and_keeps_the_rest(self):
        old = render_repolist(NAMES)
        repo = self.repo_with(f"# r\n\n{AFTER}\n{block(old)}\nown text\n")
        changed = json.loads(json.dumps(NAMES))
        changed["locations"][1]["remote"] = "owner/alpha-moved"
        code, res = self.run_json("r", "--only", "repolist", "--names", self.names_file(changed))
        self.assertEqual((code, res["repolist"]["status"]), (0, "installed"))
        self.assertIn("the names record changed", res["repolist"]["detail"])
        text = (repo / "CLAUDE.md").read_text()
        self.assertEqual(text, f"# r\n\n{AFTER}\n{block(render_repolist(changed))}\nown text\n")

    def test_a_dry_run_reports_the_update_and_writes_nothing(self):
        old = render_repolist(NAMES)
        repo = self.repo_with(f"# r\n\n{AFTER}\n{block(old)}\n")
        changed = json.loads(json.dumps(NAMES))
        changed["locations"][0]["remote"] = "owner/zeta2"
        before = (repo / "CLAUDE.md").read_bytes()
        _, res = self.run_json("r", "--only", "repolist", "--names", self.names_file(changed), "--dry-run")
        self.assertEqual(res["repolist"]["status"], "installed")
        self.assertEqual((repo / "CLAUDE.md").read_bytes(), before)

    def test_a_locally_edited_block_is_drift_and_untouched(self):
        body = render_repolist(NAMES)
        edited = body.replace("owner/alpha", "owner/alpha-by-hand")
        repo = self.repo_with(f"# r\n\n{block(edited, mark=sha12(body))}\n")
        before = (repo / "CLAUDE.md").read_bytes()
        code, res = self.run_json("r", "--only", "repolist", "--names", self.names_file())
        self.assertEqual((code, res["repolist"]["status"]), (1, "drift"))
        self.assertIn("edited locally", res["repolist"]["detail"])
        self.assertEqual((repo / "CLAUDE.md").read_bytes(), before)

    def test_no_block_is_drift_naming_where_it_goes_and_writes_nothing(self):
        repo = self.repo_with(f"# r\n\n{AFTER} `a/` → `github.com/o/a`\n")
        before = (repo / "CLAUDE.md").read_bytes()
        code, res = self.run_json("r", "--only", "repolist", "--names", self.names_file())
        self.assertEqual((code, res["repolist"]["status"]), (1, "drift"))
        self.assertIn(f"after the line `{AFTER}`", res["repolist"]["detail"])
        self.assertEqual((repo / "CLAUDE.md").read_bytes(), before)

    def test_without_names_the_component_does_nothing(self):
        repo = self.repo_with("# r\n\nown text\n")
        before = (repo / "CLAUDE.md").read_bytes()
        code, res = self.run_json("r", "--only", "repolist")
        self.assertEqual((code, res["repolist"]["status"]), (0, "none"))
        self.assertIn("no --names", res["repolist"]["detail"])
        self.assertEqual((repo / "CLAUDE.md").read_bytes(), before)

    def test_a_names_file_that_cannot_be_read_fails(self):
        self.repo_with("# r\n")
        p = self.tmp / "bad.json"
        p.write_text("{\"locations\": \"no\"}\n")
        code, res = self.run_json("r", "--only", "repolist", "--names", p)
        self.assertEqual((code, res["repolist"]["status"]), (1, "failed"))

    def test_a_folder_in_no_repo_with_the_markers_is_rendered_and_never_made_a_repo(self):
        """The workspace top is no git repo by design; --only repolist renders its block all
        the same, and any other run still refuses to touch the folder."""
        body = render_repolist(NAMES)
        top = self.tmp / "top"
        top.mkdir()
        (top / "CLAUDE.md").write_text(f"# top\n\n{AFTER}\n{block(body)}\n")
        (top / "other.md").write_text("someone's file\n")
        code, res = self.run_json("top", "--only", "repolist", "--names", self.names_file())
        self.assertEqual((code, res["repolist"]["status"], list(res)), (0, "unchanged", ["repolist"]))
        self.assertFalse((top / ".git").exists(), "never turned into a repo")
        changed = json.loads(json.dumps(NAMES))
        changed["locations"][1]["remote"] = "owner/alpha2"
        code, res = self.run_json("top", "--only", "repolist", "--names", self.names_file(changed), "--dry-run")
        self.assertEqual((code, res["repolist"]["status"]), (0, "installed"))
        self.assertIn(block(body), (top / "CLAUDE.md").read_text(), "a dry run writes nothing")
        code, res = self.run_json("top", "--only", "repolist", "--names", self.names_file(changed))
        self.assertEqual((code, res["repolist"]["status"]), (0, "installed"))
        self.assertIn(block(render_repolist(changed)), (top / "CLAUDE.md").read_text())
        self.assertFalse((top / ".git").exists())
        r = self.run_setup("top", "--names", self.names_file())
        self.assertEqual(r.returncode, 2)
        self.assertIn("will not turn someone's folder into a repo", r.stderr)
        r = self.run_setup("top", "--only", "rules")
        self.assertEqual(r.returncode, 2, "only the repo list may be rendered into a folder that is no repo")
        (top / "CLAUDE.md").write_text("# top, no markers\n")
        r = self.run_setup("top", "--only", "repolist", "--names", self.names_file())
        self.assertEqual(r.returncode, 2, "without the markers the folder is someone's, refused as before")
