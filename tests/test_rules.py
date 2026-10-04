"""The rules block: installed, kept, updated when behind, never overwritten when edited."""
from setuplib.core import TOOL_ROOT, sha12
from tests.helpers import Case, git_repo

TMPL = (TOOL_ROOT / "templates/shared-rules.md").read_text()


def block(body, mark=None):
    return f"<!-- shared:rules@{mark or sha12(body)} -->\n{body}<!-- /shared -->\n"


class Rules(Case):
    def repo_with(self, text):
        repo = git_repo(self.tmp / "r")
        (repo / "CLAUDE.md").write_text(text)
        return repo

    def test_current_block_is_unchanged(self):
        self.repo_with("# r\n\nown text\n\n" + block(TMPL) + "\n## Own section\n")
        _, res = self.run_json("r")
        self.assertEqual(res["rules"]["status"], "unchanged")

    def test_behind_block_is_updated_and_own_text_kept(self):
        old = "## Shared rules\n\nan older version of the rules\n"
        repo = self.repo_with("# r\n\nown text\n\n" + block(old) + "\n## Own section\nmine\n")
        _, res = self.run_json("r")
        self.assertEqual(res["rules"]["status"], "installed")
        text = (repo / "CLAUDE.md").read_text()
        self.assertEqual(text, "# r\n\nown text\n\n" + block(TMPL) + "\n## Own section\nmine\n")

    def test_locally_edited_block_is_drift_and_untouched(self):
        edited = TMPL.replace("Nothing else.", "Nothing else, mostly.")
        self.assertNotEqual(edited, TMPL)
        repo = self.repo_with("# r\n\n" + block(edited, mark=sha12(TMPL)))
        before = (repo / "CLAUDE.md").read_bytes()
        code, res = self.run_json("r")
        self.assertEqual((code, res["rules"]["status"]), (1, "drift"))
        self.assertIn("edited locally", res["rules"]["detail"])
        self.assertEqual((repo / "CLAUDE.md").read_bytes(), before)

    def test_hand_copy_without_markers_is_drift(self):
        self.repo_with("# r\n\n## Keep an active TODO\n\nhand copy\n")
        code, res = self.run_json("r")
        self.assertEqual((code, res["rules"]["status"]), (1, "drift"))
        self.assertIn("no shared:rules block", res["rules"]["detail"])

    def test_two_blocks_is_drift(self):
        self.repo_with(block(TMPL) + block(TMPL))
        _, res = self.run_json("r")
        self.assertEqual(res["rules"]["status"], "drift")
