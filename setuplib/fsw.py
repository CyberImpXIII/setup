"""The ONLY module in setuplib that changes anything on disk or on a remote.

Every file write, chmod, folder creation, `git init`, commit and `gh repo create`
goes through a Writer, so `--dry-run` is enforced in one place: a dry Writer
records what it would have done and touches nothing. tests/test_vocab.py
(OneWriter) audits that no other module in setuplib writes, and
tests/test_dryrun.py that a dry run leaves the target byte-identical. The one
write outside a Writer is ignore_verdicts' throwaway repo in the system temp
folder, which never touches the target and is removed before it returns.
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


class Writer:
    def __init__(self, root: Path, dry_run: bool):
        self.root = root
        self.dry_run = dry_run
        self.written = []  # (relative path, include in the scaffold commit)

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

    def create_github(self, gh: str, slug: str, private: bool):
        """`gh repo create` with origin and a push. The caller verifies the result."""
        if self.dry_run:
            return None
        vis = "--private" if private else "--public"
        r = subprocess.run([gh, "repo", "create", slug, vis, "--source", str(self.root),
                            "--remote", "origin", "--push"],
                           cwd=self.root, capture_output=True, text=True)
        return None if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip() or "gh repo create failed")
