"""The ONLY module in setuplib that changes anything on disk or on a remote.

Every file write, chmod, folder creation, `git init`, `git config`, commit, `gh repo create` and
the repo CLI's own write setup asks for (the data component's `import`) goes
through a Writer, so `--dry-run` is enforced in one place: a dry Writer
records what it would have done and touches nothing. tests/test_vocab.py
(OneWriter) audits that no other module in setuplib writes, and
tests/test_dryrun.py that a dry run leaves the target byte-identical. The two
writes outside a Writer are throwaway folders in the system temp folder, which
never touch the target and are removed before they return: ignore_verdicts' repo,
and Scratch, the copy `--rebuild` renders into.
"""
import os
import subprocess
import tempfile
from pathlib import Path


def ignore_verdicts(texts, paths, as_folders=False):
    """What git decides for each path under each candidate root .gitignore text, in a
    throwaway repo of its own (removed afterwards; the target is never touched, so
    this runs in a dry run too). With as_folders the paths are created there as
    folders first: git applies a folder-only pattern (`x/`) only to a folder on disk.
    Returns ([{path: (line number, pattern)} per text, with (0, "") for no match],
    None) or ([], error)."""
    out = []
    with tempfile.TemporaryDirectory(prefix="setup-ignore-") as d:
        r = subprocess.run(["git", "init", "-q", d], capture_output=True, text=True)
        if r.returncode != 0:
            return [], r.stderr.strip() or "git init failed"
        if as_folders:
            for p in paths:
                Path(d, p).mkdir(parents=True, exist_ok=True)
        for text in texts:
            Path(d, ".gitignore").write_text(text)
            r = subprocess.run(["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "-z", "-v",
                                "-n", "--no-index", "--stdin"], input="\0".join(paths) + "\0",
                               cwd=d, capture_output=True, text=True)
            if r.returncode not in (0, 1):
                return [], r.stderr.strip() or f"git check-ignore exit {r.returncode}"
            f = r.stdout.split("\0")
            got = {}
            for i in range(0, len(f) - 3, 4):  # source, line number, pattern, path
                got[f[i + 3]] = (int(f[i + 1]) if f[i + 1] else 0, f[i + 2])
            out.append(got)
    return out, None


class Scratch:
    """The throwaway folder `--rebuild` renders setup's baseline into (setuplib/node.py):
    in the system temp folder, removed on exit. The caller renders into a subfolder of
    `path` through its own Writer; nothing here touches the target."""

    def __enter__(self):
        self._d = tempfile.TemporaryDirectory(prefix="setup-rebuild-")
        self.path = Path(self._d.name).resolve()
        return self

    def __exit__(self, *exc):
        self._d.cleanup()


class Writer:
    def __init__(self, root: Path, dry_run: bool):
        self.root = root
        self.dry_run = dry_run
        self.written = []  # (relative path, include in the scaffold commit)
        # an existing repo: a git config write waits for the render's commit (a
        # core.hooksPath set first would gate setup's own commit), apply_config sets it
        self.defer_config = False
        self.pending_config = []
        # "" : root is the repo. A subfolder name: root is not a repo, that folder of
        # it is (the workspace top, whose .claude/ is its own repo): paths are given
        # from root, and git runs in the subfolder on the part after it
        self.git_sub = ""

    def _in_repo(self, paths):
        """(the folder git runs in, paths relative to it). A path outside git_sub is
        a ValueError: it would be committed nowhere."""
        if not self.git_sub:
            return self.root, list(paths)
        pre = self.git_sub + "/"
        out = [p[len(pre):] for p in paths if p.startswith(pre)]
        if len(out) != len(paths):
            raise ValueError(f"outside {pre}: " + ", ".join(p for p in paths if not p.startswith(pre)))
        return self.root / self.git_sub, out

    def create_repo(self, existed_empty: bool):
        """mkdir (unless an empty folder is already there) and `git init`."""
        if self.dry_run:
            return None
        if not existed_empty:
            self.root.mkdir()
        r = subprocess.run(["git", "init", "-q"], cwd=self.root,
                           capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stderr.strip() or "git init failed")

    def write(self, rel: str, data, mode=None, commit=True):
        self.written.append((rel, commit))
        if self.dry_run:
            return
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode()
        p.write_bytes(data)
        if mode is not None:
            os.chmod(p, mode)

    def commit_scaffold(self, message: str):
        """Commit exactly the files this Writer wrote with commit=True. Never `add -A`."""
        paths = [rel for rel, c in self.written if c]
        if self.dry_run or not paths:
            return None
        r = subprocess.run(["git", "add", "--", *paths], cwd=self.root,
                           capture_output=True, text=True)
        if r.returncode != 0:
            return r.stderr.strip() or "git add failed"
        r = subprocess.run(["git", "commit", "-q", "-m", message], cwd=self.root,
                           capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip() or "git commit failed")

    def commit_render(self, paths, message: str):
        """An existing repo (PLAN-architecture §11 S2): commit exactly `paths` (`git
        add`, then `git commit --only`, so nothing else staged rides along). When either
        fails (the repo's own git hooks refuse it, say), `paths` are unstaged again and
        the files stay written, for the repo's owner to check and commit (TODO.md: a
        rollback meant no render could land in a gated repo). (None, None) committed,
        or (why, None or why the unstaging failed)."""
        if self.dry_run or not paths:
            return None, None
        try:
            cwd, paths = self._in_repo(paths)
        except ValueError as e:
            return f"nothing committed: rendered {e}, which is no repo", None
        r = subprocess.run(["git", "add", "--", *paths], cwd=cwd, capture_output=True, text=True)
        if r.returncode == 0:
            r = subprocess.run(["git", "commit", "-q", "-m", message, "--only", "--", *paths], cwd=cwd,
                               capture_output=True, text=True)
            if r.returncode == 0:
                return None, None
        why = (r.stderr.strip() or r.stdout.strip() or "git commit failed")[-300:]
        u = subprocess.run(["git", "reset", "-q", "--", *paths], cwd=cwd, capture_output=True, text=True)
        if u.returncode != 0:  # no HEAD yet: unstage by removing from the index only
            u = subprocess.run(["git", "rm", "-q", "--cached", "--ignore-unmatch", "--", *paths],
                               cwd=cwd, capture_output=True, text=True)
        return why, None if u.returncode == 0 else (u.stderr.strip() or "git reset failed")[-120:]

    def apply_config(self):
        """Set the git config writes deferred while defer_config was on. None, or why
        one failed."""
        while self.pending_config:
            key, value = self.pending_config.pop(0)
            err = self._set_config(key, value)
            if err:
                return err
        return None

    def git_config(self, key: str, value: str):
        """`git config --local key value` in the repo (the githooks component:
        core.hooksPath, and the checks CLI its pre-commit runs). None, or why it failed.
        With defer_config it is only recorded, for apply_config."""
        if self.dry_run:
            return None
        if self.defer_config:
            self.pending_config.append((key, value))
            return None
        return self._set_config(key, value)

    def _set_config(self, key: str, value: str):
        r = subprocess.run(["git", "config", "--local", key, value], cwd=self.root,
                           capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stderr.strip() or f"git config {key} failed")

    def run_repo_cli(self, argv, env, timeout):
        """A write the repo's own CLI does (the data component's `import`), run in the
        repo. (exit code, stderr+stdout tail, None) or (None, "", why it could not run);
        a dry run runs nothing: (0, "", None). The caller checks what it wrote, not the code."""
        if self.dry_run:
            return 0, "", None
        try:
            r = subprocess.run(argv, cwd=self.root, env=env, capture_output=True, text=True,
                               stdin=subprocess.DEVNULL, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return None, "", f"{e.__class__.__name__}: {e}"
        return r.returncode, (r.stderr.strip() or r.stdout.strip())[-200:], None

    def create_github(self, gh: str, slug: str, private: bool):
        """`gh repo create` with origin and a push. The caller verifies the result."""
        if self.dry_run:
            return None
        vis = "--private" if private else "--public"
        r = subprocess.run([gh, "repo", "create", slug, vis, "--source", str(self.root),
                            "--remote", "origin", "--push"],
                           cwd=self.root, capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip() or "gh repo create failed")
