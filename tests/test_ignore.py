""".gitignore: a fresh scaffold reads clean; an existing .gitignore only gains the
lines it lacks, by meaning (what git ignores), never rewritten or reordered; a
negation is drift, never overridden; a second run is a no-op."""
import subprocess

from setuplib import core
from tests.helpers import Case, git, git_repo, snapshot

SPEC = core.load_spec()
ENTRIES = next(c for c in SPEC["components"] if c["name"] == "ignore")["entries"]
LINES = [e["line"] for e in ENTRIES]


class Ignore(Case):
    def test_fresh_scaffold_reads_clean(self):
        code, res = self.run_json("fresh")
        self.assertEqual(code, 0)
        repo = self.tmp / "fresh"
        self.assertEqual(res["ignore"]["status"], "installed")
        self.assertIn(".gitignore", git(["ls-files"], repo).stdout.split())
        self.assertEqual(git(["status", "--porcelain"], repo).stdout, "")
        # every probe the data names, present on disk, still reads clean
        for e in ENTRIES:
            p = repo / e["probe"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x\n")
        self.assertEqual(git(["status", "--porcelain", "--untracked-files=all"], repo).stdout, "")

    def test_every_entry_ignores_its_probe(self):
        # the data's own seam: each line, alone, makes git ignore its probe
        for e in ENTRIES:
            repo = git_repo(self.tmp / ("r" + str(LINES.index(e["line"]))), commit=False)
            (repo / ".gitignore").write_text(e["line"] + "\n")
            r = subprocess.run(["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "-v",
                                "--no-index", "--", e["probe"]], cwd=repo, capture_output=True, text=True)
            self.assertEqual(r.stdout.split("\t")[0], f".gitignore:1:{e['line']}", e)

    def test_existing_gitignore_keeps_its_lines_and_gains_only_the_missing(self):
        repo = git_repo(self.tmp / "old")
        old = "node_modules/\n# mine\n.env*\nbuild\n"  # .env* already covers .env
        (repo / ".gitignore").write_text(old)
        before = snapshot(repo)
        code, res = self.run_json("old", "--dry-run")
        self.assertEqual(snapshot(repo), before)
        self.assertEqual(res["ignore"]["status"], "installed")
        code, res = self.run_json("old")
        self.assertEqual(res["ignore"]["status"], "installed", res["ignore"])
        new = (repo / ".gitignore").read_text()
        self.assertTrue(new.startswith(old), new)
        added = new[len(old):].splitlines()
        self.assertEqual(added, [x for x in LINES if x != ".env"])
        # a second run is a no-op
        before = snapshot(repo)
        code, res = self.run_json("old")
        self.assertEqual(res["ignore"]["status"], "unchanged", res["ignore"])
        self.assertEqual(snapshot(repo), before)

    def test_missing_final_newline_is_completed_not_merged(self):
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("dist")
        self.run_json("old")
        self.assertEqual((repo / ".gitignore").read_text().splitlines(), ["dist", *LINES])

    def test_negation_of_a_baseline_path_is_drift_and_untouched(self):
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("*.env\n!local.env\n")
        code, res = self.run_json("old")
        self.assertEqual(code, 1)
        self.assertEqual(res["ignore"]["status"], "drift")
        self.assertIn("!local.env", res["ignore"]["detail"])
        self.assertEqual((repo / ".gitignore").read_text(), "*.env\n!local.env\n")

    def test_negation_an_append_would_override_is_drift_and_untouched(self):
        # appending *.bak after !keep.bak would re-ignore keep.bak: the owner's to place
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("*.cfg\n!keep.bak\n")
        code, res = self.run_json("old")
        self.assertEqual((code, res["ignore"]["status"]), (1, "drift"), res["ignore"])
        detail = res["ignore"]["detail"]
        self.assertIn("*.bak would re-ignore keep.bak", detail)
        self.assertIn("!keep.bak (.gitignore:2)", detail)
        self.assertEqual((repo / ".gitignore").read_text(), "*.cfg\n!keep.bak\n")

    def test_negation_no_append_overrides_is_kept_and_the_lines_appended(self):
        repo = git_repo(self.tmp / "old")
        old = "build/*\n!build/keep.txt\n"
        (repo / ".gitignore").write_text(old)
        code, res = self.run_json("old")
        self.assertEqual((code, res["ignore"]["status"]), (0, "installed"), res["ignore"])
        new = (repo / ".gitignore").read_text()
        self.assertEqual(new, old + "".join(x + "\n" for x in LINES))
        # by meaning: the owner's kept path is still kept after the append
        r = git(["-c", "core.excludesFile=/dev/null", "check-ignore", "-v", "-n", "--no-index",
                 "--", "build/keep.txt"], repo)
        self.assertIn("!build/keep.txt", r.stdout)
        code, res = self.run_json("old")
        self.assertEqual(res["ignore"]["status"], "unchanged", res["ignore"])

    def test_directory_negation_an_append_would_override_is_caught(self):
        # !keep.bak/ keeps a folder; *.bak would re-ignore the folder itself
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("*.d\n!keep.bak/\n")
        code, res = self.run_json("old")
        self.assertEqual((code, res["ignore"]["status"]), (1, "drift"), res["ignore"])
        self.assertIn("*.bak would re-ignore keep.bak/", res["ignore"]["detail"])

    def test_glob_negation_is_drift_with_the_reason_not_a_guess(self):
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("*.txt\n!keep*.txt\n")
        code, res = self.run_json("old")
        self.assertEqual((code, res["ignore"]["status"]), (1, "drift"), res["ignore"])
        self.assertIn("!keep*.txt (.gitignore:2) is a pattern", res["ignore"]["detail"])
        self.assertEqual((repo / ".gitignore").read_text(), "*.txt\n!keep*.txt\n")

    def test_negation_in_a_subfolder_gitignore_does_not_block(self):
        # a deeper .gitignore outranks the root one: a root append cannot override it
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("dist\n")
        (repo / "sub").mkdir()
        (repo / "sub" / ".gitignore").write_text("!keep.bak\n")
        code, res = self.run_json("old")
        self.assertEqual(res["ignore"]["status"], "installed", res["ignore"])

    def commit_files(self, repo, *paths):
        for p in paths:
            (repo / p).parent.mkdir(parents=True, exist_ok=True)
            (repo / p).write_text("x\n")
        git(["add", "--", *paths], repo)
        git(["commit", "-q", "-m", "tracked"], repo)

    def test_tracked_file_the_baseline_covers_is_drift_and_stays_tracked(self):
        # .gitignore cannot untrack a committed file; setup says so and never untracks it
        repo = git_repo(self.tmp / "old")
        self.commit_files(repo, "local.env", "sub/notes.bak", "kept.txt")
        (repo / ".gitignore").write_text("dist\n")
        git(["add", ".gitignore"], repo)
        git(["commit", "-q", "-m", "gi"], repo)
        before = snapshot(repo)
        code, res = self.run_json("old", "--dry-run")
        self.assertEqual(snapshot(repo), before)
        self.assertEqual((code, res["ignore"]["status"]), (1, "drift"), res["ignore"])
        code, res = self.run_json("old")
        self.assertEqual((code, res["ignore"]["status"]), (1, "drift"), res["ignore"])
        detail = res["ignore"]["detail"]
        self.assertIn("local.env", detail)
        self.assertIn("sub/notes.bak", detail)
        self.assertNotIn("kept.txt", detail)
        self.assertIn("git rm --cached", detail)
        # still tracked, nothing staged; the missing lines were still appended
        self.assertIn("local.env", git(["ls-files"], repo).stdout.split())
        self.assertEqual(git(["diff", "--cached", "--name-only"], repo).stdout, "")
        self.assertIn("*.env", (repo / ".gitignore").read_text().splitlines())

    def test_tracked_file_the_owner_negated_is_not_flagged(self):
        repo = git_repo(self.tmp / "old")
        self.commit_files(repo, "keep.env")
        (repo / ".gitignore").write_text("".join(x + "\n" for x in LINES) + "!keep.env\n")
        code, res = self.run_json("old")
        self.assertEqual((code, res["ignore"]["status"]), (0, "unchanged"), res["ignore"])

    def test_ignored_only_by_info_exclude_still_gets_the_line(self):
        # .git/info/exclude is not in a clone; the repo's own .gitignore must carry it
        repo = git_repo(self.tmp / "old")
        (repo / ".gitignore").write_text("x\n")
        (repo / ".git/info/exclude").write_text("*.bak\n")
        self.run_json("old")
        self.assertIn("*.bak", (repo / ".gitignore").read_text().splitlines())
