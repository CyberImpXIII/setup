"""The docs component: a repo's docs declaration, its file name, grammar and
resolution imported from the docs dependency's reader (dependencies.json `reader`),
never copied here. Absent: the `rows` that resolve here are written and committed
with the render, and the reader reads them back with no failure. Present: the
owner's, only read (drift when the reader refuses it or a row resolves to no doc,
needs-owner when a row that resolves here is missing). No reader: none, no file."""
import shutil
import subprocess

from setuplib import core, deps
from tests.helpers import ROOT, Case, commit_all, git, git_repo, snapshot

SPEC = next(c for c in core.load_spec()["components"] if c["name"] == "docs")


def reader():
    d, why = deps.load()
    where, why = (None, why) if d is None else deps.resolve(SPEC["dependency"], deps=d)
    return (None, why) if where is None else deps.reader(SPEC["dependency"], where, d)


class Docs(Case):
    def setUp(self):
        super().setUp()
        self.rd, why = reader()
        if self.rd is None:
            self.skipTest(f"lone clone: {why} (NoReader covers it)")
        self.f = self.rd["declaration"]

    def owned(self, text, *files):
        """A repo whose owner wrote the declaration (and files), committed."""
        repo = git_repo(self.tmp / "r")
        for rel in files:
            (repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (repo / rel).write_text("# a doc\n")
        (repo / self.f).write_text(text)
        commit_all(repo)
        return repo

    def test_a_new_repo_declares_what_resolves_and_the_reader_reads_it_back(self):
        repo = git_repo(self.tmp / "r")
        (repo / "docs").mkdir()
        (repo / "docs/a.md").write_text("# a\n")
        commit_all(repo)
        code, res = self.run_json("r")
        self.assertEqual(res["docs"]["status"], "installed", res["docs"])
        text = (repo / self.f).read_text()
        rows = self.rd["parse"](text, self.f)
        self.assertEqual(rows, [("file", "CLAUDE.md"), ("file", "TODO.md"), ("glob", "docs/*.md")])
        self.assertEqual(self.rd["resolve"]("r", str(repo), rows)[1], [])
        self.assertIn(self.f, git(["show", "--name-only", "--format=", "HEAD"], repo).stdout.split())
        _, again = self.run_json("r", "--only", "docs")
        self.assertEqual(again["docs"]["status"], "unchanged", again["docs"])

    def test_a_glob_with_no_hit_is_not_written(self):
        git_repo(self.tmp / "r")
        _, res = self.run_json("r")
        rows = self.rd["parse"]((self.tmp / "r" / self.f).read_text(), self.f)
        self.assertNotIn("glob", [k for k, _ in rows])

    def test_a_dry_run_counts_what_the_run_would_render_and_writes_nothing(self):
        repo = git_repo(self.tmp / "r")
        before = snapshot(repo)
        _, res = self.run_json("r", "--dry-run")
        self.assertEqual(res["docs"]["status"], "installed", res["docs"])
        self.assertIn("file CLAUDE.md", res["docs"]["detail"])  # rendered by rules in the same run
        self.assertEqual(snapshot(repo), before)

    def test_an_owners_declaration_lacking_a_row_is_needs_owner_and_untouched(self):
        repo = self.owned("file\tCLAUDE.md\nhelp\t./x --help\n", "CLAUDE.md", "TODO.md")
        before = (repo / self.f).read_bytes()
        _, res = self.run_json("r", "--only", "docs")
        self.assertEqual(res["docs"]["status"], "needs-owner", res["docs"])
        self.assertIn("file TODO.md", res["docs"]["detail"])
        self.assertEqual((repo / self.f).read_bytes(), before)

    def test_a_declaration_the_reader_refuses_is_drift_and_untouched(self):
        for text in ("file CLAUDE.md\n", "file\t.env\n", "file\tgone.md\n", "glob\tnone/*.md\n"):
            with self.subTest(text=text):
                repo = self.owned(text, "CLAUDE.md", "TODO.md")
                before = (repo / self.f).read_bytes()
                code, res = self.run_json("r", "--only", "docs")
                self.assertEqual(res["docs"]["status"], "drift", res["docs"])
                self.assertEqual(code, 1)
                self.assertEqual((repo / self.f).read_bytes(), before)
                shutil.rmtree(repo)

    def test_a_complete_declaration_with_the_owners_help_is_unchanged(self):
        self.owned("file\tCLAUDE.md\nfile\tTODO.md\nhelp\t./x --help\n", "CLAUDE.md", "TODO.md")
        _, res = self.run_json("r", "--only", "docs")
        self.assertEqual(res["docs"]["status"], "unchanged", res["docs"])
        self.assertIn("3 row(s)", res["docs"]["detail"])

    def test_setup_never_writes_a_help_row(self):
        self.assertNotIn("help", {r["kind"] for r in SPEC["rows"]})


class Reader(Case):
    def test_a_module_without_the_names_it_declares_is_refused(self):
        import uuid
        for body, why in (("DECLARATION = ''\n", "is not a file name"),
                          ("DECLARATION = 'd.tsv'\nparse_declaration = 1\n", "has no function")):
            mod = "fake_reader_" + uuid.uuid4().hex[:8]  # an import is cached by name once a process
            where = self.tmp / mod
            where.mkdir()
            (where / f"{mod}.py").write_text(body)
            d = {"x": {"reader": {"module": mod, "declaration": "DECLARATION",
                                  "parse": "parse_declaration", "resolve": "docs_of"}}}
            got, said = deps.reader("x", where.resolve(), d)
            self.assertIsNone(got, body)
            self.assertIn(why, said)


class NoReader(Case):
    def test_a_lone_clone_writes_no_declaration(self):
        lone = self.tmp / "lone" / "setup"
        shutil.copytree(ROOT, lone, ignore=shutil.ignore_patterns(".git", ".mutants", "__pycache__"))
        repo = git_repo(self.tmp / "r")
        before = {p.name for p in repo.iterdir()}
        r = subprocess.run([str(lone / "setup"), str(repo), "--only", "docs"], capture_output=True,
                           text=True, env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"docs +none +no docs reader")
        self.assertEqual({p.name for p in repo.iterdir()}, before)
