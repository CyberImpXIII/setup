"""The push component (PLAN-services.md §3 F3, verb step 5; tl-570): git config
funnel.push, the record commit.sh reads before it pushes, set from the repo's own
registration (services.json `push`), only where an origin exists, never guessed.
Each assertion reads the record the way commit.sh does (`git config --bool`), not
from setup's own line alone."""
import json
import shutil

from tests.helpers import Case, commit_all, git, git_repo, snapshot


class Push(Case):
    def repo(self, push="absent", origin=True, record=None):
        r = git_repo(self.tmp / "r")
        doc = {"name": "r", "services": [{"service": "check", "run": "dev.sh", "verbs": ["check"]}]}
        if push != "absent":
            doc["push"] = push
        (r / "services.json").write_text(json.dumps(doc, indent=2) + "\n")
        commit_all(r)
        if origin:
            bare = self.tmp / "origin.git"
            git(["init", "-q", "--bare", str(bare)], self.tmp)
            git(["remote", "add", "origin", str(bare)], r)
        if record is not None:
            git(["config", "--local", "funnel.push", record], r)
        return r

    def drop(self, r):
        """Remove a subtest's repo and its origin, so the next subtest builds its own."""
        shutil.rmtree(r)
        shutil.rmtree(self.tmp / "origin.git")

    def record(self, r):
        """As commit.sh reads it: `git config --bool funnel.push`; None when unset."""
        p = git(["config", "--bool", "funnel.push"], r)
        return p.stdout.strip() if p.returncode == 0 else None

    def only_push(self, *extra):
        code, res = self.run_json("r", "--only", "push", *extra)
        return code, res["push"]

    def test_true_is_written_where_the_registration_says_push(self):
        r = self.repo(push=True)
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "installed"), line)
        self.assertIn("set funnel.push = true from services.json `push` (was unset)", line["detail"])
        self.assertEqual(self.record(r), "true")
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "unchanged"), line)

    def test_false_is_written_where_the_registration_says_no(self):
        # the input changes the output: the same fixture but the one field
        r = self.repo(push=False)
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "installed"), line)
        self.assertEqual(self.record(r), "false")

    def test_no_origin_writes_nothing(self):
        r = self.repo(push=True, origin=False)
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "none"), line)
        self.assertIn("no origin", line["detail"])
        self.assertIsNone(self.record(r))

    def test_no_field_takes_jacobs_default(self):
        # su-111: true in every repo with an origin unless its store records false
        r = self.repo(push="absent")
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "installed"), line)
        self.assertIn("set funnel.push = true from the default (services.json declares no `push`", line["detail"])
        self.assertEqual(self.record(r), "true")
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "unchanged"), line)

    def test_no_registration_takes_jacobs_default(self):
        r = self.repo(push=True)
        (r / "services.json").unlink()
        commit_all(r, "no registration")
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "installed"), line)
        self.assertIn("from the default (no services.json", line["detail"])
        self.assertEqual(self.record(r), "true")

    def test_a_default_never_flips_a_recorded_no(self):
        for absent in ("field", "file"):
            with self.subTest(absent=absent):
                r = self.repo(push="absent" if absent == "field" else True, record="false")
                if absent == "file":
                    (r / "services.json").unlink()
                    commit_all(r, "no registration")
                code, line = self.only_push()
                self.assertEqual((code, line["status"]), (0, "needs-owner"), line)
                self.assertIn("a default never overrides a recorded no", line["detail"])
                self.assertEqual(self.record(r), "false")
                self.drop(r)

    def test_a_field_that_is_not_a_boolean_is_drift(self):
        for bad in ("true", 1, None):
            with self.subTest(push=bad):
                r = self.repo(push=bad)
                code, line = self.only_push()
                self.assertEqual((code, line["status"]), (1, "drift"), line)
                self.assertIsNone(self.record(r))
                self.drop(r)

    def test_a_registration_that_does_not_parse_is_drift(self):
        r = self.repo(push=True)
        (r / "services.json").write_text("{not json\n")
        commit_all(r, "broken")
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (1, "drift"), line)
        self.assertIsNone(self.record(r))

    def test_a_record_that_differs_is_set_from_the_registration(self):
        for old, push, want in (("true", False, "false"), ("false", True, "true"), ("maybe", True, "true")):
            with self.subTest(old=old):
                r = self.repo(push=push, record=old)
                code, line = self.only_push()
                self.assertEqual((code, line["status"]), (0, "installed"), line)
                self.assertIn(f"(was {'invalid' if old == 'maybe' else old})", line["detail"])
                self.assertEqual(self.record(r), want)
                self.drop(r)

    def test_a_record_git_reads_as_the_same_boolean_is_unchanged(self):
        # `yes` is true to git, so to commit.sh: read as git reads it, not as text
        r = self.repo(push=True, record="yes")
        code, line = self.only_push()
        self.assertEqual((code, line["status"]), (0, "unchanged"), line)
        self.assertEqual(git(["config", "--local", "funnel.push"], r).stdout.strip(), "yes")

    def test_dry_run_writes_nothing(self):
        r = self.repo(push=True)
        before = snapshot(r)
        code, line = self.only_push("--dry-run")
        self.assertEqual((code, line["status"]), (0, "installed"), line)
        self.assertIn("would set funnel.push = true", line["detail"])
        self.assertEqual(snapshot(r), before)
        self.assertIsNone(self.record(r))

    def test_a_full_run_sets_it_after_the_render_commit(self):
        # the component runs after `commit`, where an existing repo's other config
        # writes are already applied: a deferred write here would never land
        r = self.repo(push=True)
        code, res = self.run_json("r")
        self.assertEqual(res["push"]["status"], "installed", res["push"])
        self.assertEqual(self.record(r), "true")

    def test_a_new_repo_with_github_takes_the_default(self):
        # the skeleton declares no `push` (services.schema.json does not take it yet:
        # TODO.md), so the record is the default, in the dry run and the real one
        code, res = self.run_json("fresh", "--github", "--dry-run")
        self.assertEqual(res["push"]["status"], "installed", res["push"])
        self.assertIn("would set funnel.push = true from the default", res["push"]["detail"])
        self.assertFalse((self.tmp / "fresh").exists(), "a dry run creates nothing")
        code, res = self.run_json("fresh", "--github")
        self.assertEqual(res["remote"]["status"], "installed", res["remote"])  # the fake gh made the origin
        self.assertEqual(res["push"]["status"], "installed", res["push"])
        self.assertEqual(self.record(self.tmp / "fresh"), "true")
