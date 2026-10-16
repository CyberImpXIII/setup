"""setup fanout <component>: one shared change rendered into every repo that declares
it (PLAN-workspace-audit §3.2 option 2, Jacob's yes of 2026-10-13).

Per repo, one after another, each step its own process: `setup <repo> --only C
--dry-run --json` (a drift it would keep, or a refusal, is a named failure and
nothing is written; nothing to render is `unchanged`), a clean tree, `setup <repo>
--only C --no-commit --json`, the repo's own check (components.json fanout.check),
and only when it passes a commit of exactly the rendered files (fsw.Writer
.commit_render) whose message names the source commit. A repo whose check is red is
left with its render written and uncommitted, and named; no repo is ever skipped
silently. `--rebuild` is passed through to setup (off by default): without it a copy
whose logic drifted is kept, and the repo fails, named.
"""
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import core
from .fsw import Writer

SETUP = core.TOOL_ROOT / "setup"
SETUP_TIMEOUT = 600  # seconds for one `setup <repo> --only C` call
TAIL = 5  # lines of a red check's output carried into its outcome


class Usage(Exception):
    """The run cannot start, or one repo's setup call was a usage error (it would be
    the same for every repo): exit 2."""


@dataclass
class Outcome:
    path: str
    status: str
    detail: str
    written: list = field(default_factory=list)
    commit: str = None


def spec():
    return core.load_spec()["fanout"]


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def declares(target: Path, component: str, fo):
    """(True/False, None), or (None, why) when the declaring file cannot be read."""
    d = fo["declared_by"][component]
    p = target / d["file"]
    if not p.exists():
        return False, None
    if "contains" not in d:
        return True, None
    try:
        return d["contains"] in p.read_text(errors="replace"), None
    except OSError as e:
        return None, f"{d['file']} is unreadable ({e.strerror or e})"


def work_trees(root: Path, prune):
    """Every git work tree at or under root (a folder holding `.git`), sorted; a
    nested one included. Never follows a symlink; never enters a `prune` folder."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames or ".git" in filenames:
            out.append(Path(dirpath))
        dirnames[:] = sorted(d for d in dirnames if d not in prune)
    return sorted(out)


def placement(path: Path, component: str, sub: str):
    """(the folder setup renders into, the git work tree that commits it), or
    (None, why). A work tree's own top; or, for the hooks only, a folder in no work
    tree whose `sub` folder is one (the workspace top, `setup --only hooks`)."""
    if core._toplevel(path) == path:
        if component == "hooks" and path.name == sub and core.sub_repo(path.parent, sub):
            return path.parent, path
        return path, path
    if component == "hooks" and core.sub_repo(path, sub):
        return path, path / sub
    return None, f"{path} is not the top of a git work tree"


def source_commit(where: Path, paths):
    """(HEAD's full sha, None), or (None, why): the commit the render is from. Refused
    while a path the render reads holds changes git does not: the message could not
    name the commit honestly."""
    r = _git(["rev-parse", "--verify", "HEAD"], where)
    if r.returncode != 0:
        return None, f"the source {where} has no commit to name"
    if paths:
        st = _git(["status", "--porcelain", "--untracked-files=all", "--", *paths], where)
        if st.returncode != 0:
            return None, f"git status cannot run in the source {where}: {st.stderr.strip()[-200:]}"
        if st.stdout.strip():
            changed = [line[3:] for line in st.stdout.splitlines()]
            return None, (f"the source {where} holds uncommitted changes ({', '.join(changed[:5])}"
                          f"{', ...' if len(changed) > 5 else ''}): no commit names what would be rendered")
    return r.stdout.strip(), None


def _setup(target: Path, component: str, extra):
    """(exit code, the --json document or None, stderr). Raises Usage on a usage error."""
    argv = [sys.executable, str(SETUP), str(target), "--only", component, "--json", *extra]
    try:
        r = subprocess.run(argv, cwd=target, capture_output=True, text=True, timeout=SETUP_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, None, f"setup did not finish in {SETUP_TIMEOUT}s"
    err = r.stderr.strip()
    if r.returncode == 2 and not err.startswith("setup: refused:"):
        raise Usage(err or "setup exited 2 without saying why")
    if r.returncode == 2:
        return 2, None, err
    try:
        return r.returncode, json.loads(r.stdout), err
    except ValueError:
        return r.returncode, None, f"setup exit {r.returncode} printed no JSON document ({err[-200:]})"


def _bad(doc):
    """Why a setup document is not ok: each failed or drifted line, and each hook
    file it kept."""
    out = [f"{r['component']} {r['status']}: {r['detail'][:300]}" for r in doc["results"] if r["status"] in core.BAD]
    kept = [x["path"] for x in doc.get("hook_files", []) if x["action"] in ("kept", "failed")]
    if kept:
        out.append(f"kept ({len(kept)}): {', '.join(kept)}")
    return "; ".join(out) or "setup reported not ok"


def _check(tree: Path, fo, timeout):
    """None when the repo's check passed, else why (exit code and the output's tail)."""
    cmd = fo["check"]
    if not (tree / cmd[0]).is_file():
        return f"no {cmd[0]} to check with"
    try:
        r = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"`{' '.join(cmd)}` did not finish in {timeout}s"
    except OSError as e:
        return f"`{' '.join(cmd)}` could not run ({e.strerror or e})"
    if r.returncode == 0:
        return None
    tail = [line for line in (r.stdout + r.stderr).strip().splitlines() if line.strip()][-TAIL:]
    return f"`{' '.join(cmd)}` exit {r.returncode}" + (f" ({' | '.join(tail)})" if tail else "")


def _paths(paths):
    return ", ".join(paths)


def fan_one(target, tree, label, component, opts, source, fo):
    """One repo's outcome. Never raises but Usage."""
    declared, why = declares(target, component, fo)
    if declared is None:
        return Outcome(label, "failed", why)
    if not declared:
        d = fo["declared_by"][component]
        return Outcome(label, "undeclared", f"no {d['file']}" + (f" holding {d['contains']}" if "contains" in d else "")
                       + ": nothing run")
    extra = (["--rebuild"] if opts["rebuild"] else []) + (
        ["--hooks-from", str(opts["hooks_from"])] if opts["hooks_from"] else [])
    code, doc, err = _setup(target, component, ["--dry-run", *extra])
    if doc is None:
        return Outcome(label, "failed", f"setup refused it ({err}); nothing written" if code == 2 else err)
    if not doc["ok"]:
        hint = "" if opts["rebuild"] else " (--rebuild overwrites a drifted copy)"
        return Outcome(label, "failed", f"{_bad(doc)}; nothing written{hint}")
    would = doc["written"]
    if not would:
        return Outcome(label, "unchanged", "nothing to render: no check run, nothing committed")
    st = _git(["status", "--porcelain"], tree)
    if st.returncode != 0 or st.stdout.strip():
        dirty = [line[3:] for line in st.stdout.splitlines()]
        why = (f"git status cannot run ({st.stderr.strip()[-200:]})" if st.returncode != 0 else
               f"the tree is not clean ({', '.join(dirty[:10])}{', ...' if len(dirty) > 10 else ''})")
        return Outcome(label, "failed", f"{why}: the check would test its owner's work too; nothing written "
                                        f"(would render {_paths(would)})", would)
    if opts["dry_run"]:
        return Outcome(label, "would-commit", f"{len(would)} file(s) would be rendered, then checked and "
                                              f"committed: {_paths(would)}", would)
    code, doc, err = _setup(target, component, ["--no-commit", *extra])
    if doc is None or not doc["ok"]:
        left = doc["written"] if doc else []
        what = err if doc is None else _bad(doc)
        return Outcome(label, "failed", f"the render failed ({what})" + (
            f"; left written and uncommitted: {_paths(left)}" if left else "; nothing written"), left)
    paths = doc["written"]
    if not paths:
        return Outcome(label, "unchanged", "nothing rendered after all: no check run, nothing committed")
    red = _check(tree, fo, opts["check_timeout"])
    if red:
        return Outcome(label, "failed", f"check red: {red}; the render is left written and uncommitted: "
                                        f"{_paths(paths)}", paths)
    now, why = source_commit(source["where"], source["paths"])
    if now != source["commit"]:
        return Outcome(label, "failed", f"the source moved during the run ({why or now[:12]}); the render is "
                                        f"left written and uncommitted: {_paths(paths)}", paths)
    w = Writer(target, False)
    w.git_sub = tree.relative_to(target).as_posix() if tree != target else ""
    msg = (f"setup fanout: render {component} ({len(paths)} file(s)) from {source['name']}@{source['commit'][:12]}"
           f"\n\nsource commit: {source['commit']} ({source['where']})\n" + "\n".join(paths) + "\n"
           + (f"\nAgent: {opts['agent']}\n" if opts["agent"] else ""))
    why, left = w.commit_render(paths, msg)
    if why:
        return Outcome(label, "failed", f"the commit was refused ({why}); the render is left written and "
                                        f"unstaged: {_paths(paths)}" + (f"; unstaging failed: {left}" if left else ""),
                       paths)
    sha = _git(["rev-parse", "--short", "HEAD"], tree).stdout.strip()
    return Outcome(label, "committed", f"{sha}: {len(paths)} file(s) after a green check: {_paths(paths)}",
                   paths, sha)


def run(component, repos, root, opts):
    """{component, source, rebuild, dry_run, repos[Outcome], ok}. Raises Usage."""
    fo = spec()
    if component not in fo["declared_by"]:
        raise Usage(f"fanout {component}: not a fanout component (one of: {', '.join(fo['declared_by'])})")
    sub = core.load_spec()["components"]
    sub = next(c for c in sub if c["name"] == "hooks")["rebuild"]["scope_root"]
    probe = core.Setup(root, label=".", name="fanout", dry_run=True, hooks_from=opts["hooks_from"])
    where, paths, why = probe.render_source(component)
    if where is None:
        raise Usage(f"fanout {component}: {why}")
    commit, why = source_commit(where, paths)
    if commit is None:
        raise Usage(f"fanout {component}: {why}")
    source = {"name": where.name, "where": where, "paths": paths, "commit": commit}
    explicit = repos is not None
    if explicit:
        found = [Path(r).resolve() for r in repos]
    else:
        found = work_trees(root, set(fo["prune"]))
    out, seen, undeclared = [], set(), 0
    for p in found:
        label = os.path.relpath(p, Path.cwd())
        target, tree = placement(p, component, sub)
        if target is None:
            out.append(Outcome(label, "failed", tree))
            continue
        if target in seen:
            continue
        seen.add(target)
        label = os.path.relpath(target, Path.cwd())
        res = fan_one(target, tree, label, component, opts, source, fo)
        if res.status == "undeclared" and not explicit:
            undeclared += 1  # a discovered repo the component is not for: counted, not listed
            continue
        out.append(res)
    return {"component": component, "source": {"path": str(where), "commit": commit},
            "rebuild": opts["rebuild"], "dry_run": opts["dry_run"], "undeclared": undeclared,
            "repos": [asdict(o) for o in out], "ok": not any(o.status == "failed" for o in out)}
