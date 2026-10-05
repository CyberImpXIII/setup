"""A node's one input, node.json, and `--rebuild` (PLAN-repo-setup §7.5, §7.10).

node.json's shape is the shared checks' (their schema/node.schema.json:
rendered-matches, regenerate and registry-matches read the same file); setup may not
import a sibling tool, so `load` mirrors its schema and its rules here, and
tests/test_node.py's live tests hold the two readings together:
  rebuild    the argv that re-renders every generated file in place (for a node
             setup renders: this tool's `setup . --node --rebuild`); setup only
             checks its shape, it never runs it
  generated  every generated file, one exact path each
  record     the record files, committed as content and never generated (globs)
  children   (optional) child repos, set up in turn by --node; nothing under a
             child is this node's
  registry   (optional) the node's registry file; not read here

`rebuild` renders setup's baseline afresh, as a new repo in a throwaway folder,
for this node's path and name, and writes each generated file it renders over the
tree's copy. One Line per file: regenerated (byte for byte, mode included, as the
tree held it, or as the last commit holds it when the tree has none), drift
(rendered otherwise: the render is written, so `git diff` is the finding), record,
unaccounted (in the tree, named by neither list), failed (the render failed, or
setup renders no such file). Two things are never written: a record, and a
generated file with uncommitted changes (that edit is not setup's to discard: it is
reported as drift and kept). Drift and unaccounted are the progress to be made,
not a failure of the rebuild; the gate that requires zero of each is the shared
checks' `regenerate`, which runs this in a clone. Nothing here writes: files go
through the Writer the caller gives, the render through fsw.Scratch."""
import fnmatch
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from .fsw import Scratch

NODE_FILE = "node.json"
REQUIRED = ("rebuild", "generated", "record")
OPTIONAL = ("children", "registry")
LISTS = ("generated", "record", "children")
GLOB = set("*?[")


@dataclass
class Line:
    path: str
    status: str
    detail: str = ""


def norm(rel):
    return PurePosixPath(rel).as_posix()


def _inside(rel):
    p = PurePosixPath(rel)
    return not p.is_absolute() and ".." not in p.parts and norm(rel) != "."


def under(rel, prefixes):
    rel = norm(rel)
    return any(rel == norm(c) or rel.startswith(norm(c) + "/") for c in prefixes)


def is_record(rel, record):
    return any(fnmatch.fnmatchcase(norm(rel), norm(g)) for g in record)


def _strings(v, nonempty=False):
    return isinstance(v, list) and (v or not nonempty) and all(isinstance(x, str) and x for x in v)


def load(path: Path):
    """(config, None) or (None, why): the checks' schema and rules, mirrored. One
    rule is setup's own: a child inside another child is refused (it belongs in that
    child's node.json, and setting it up from here would nest it in the wrong repo)."""
    try:
        cfg = json.loads(path.read_text())
    except FileNotFoundError:
        return None, f"no {NODE_FILE}"
    except (OSError, ValueError) as e:
        return None, f"does not parse ({e.__class__.__name__})"
    if not isinstance(cfg, dict):
        return None, "not an object"
    extra = sorted(set(cfg) - set(REQUIRED) - set(OPTIONAL))
    if extra:
        return None, f"unknown key(s) {', '.join(extra)}; it holds {', '.join(REQUIRED + OPTIONAL)}"
    for k in REQUIRED:
        if k not in cfg:
            return None, f"`{k}` is missing"
    if not _strings(cfg["rebuild"], nonempty=True):
        return None, "`rebuild` is not a command (a non-empty list of non-empty strings)"
    for k in LISTS:
        if not _strings(cfg.get(k, [])):
            return None, f"`{k}` is not a list of non-empty strings"
    if "registry" in cfg and not (isinstance(cfg["registry"], str) and _inside(cfg["registry"])):
        return None, "`registry` is not a path inside the node"
    cfg = {**cfg, "children": cfg.get("children", [])}
    for k in LISTS:
        bad = [p for p in cfg[k] if not _inside(p)]
        if bad:
            return None, f"`{k}`: {bad[0]!r} is not a path inside the node"
        seen = [norm(p) for p in cfg[k]]
        if len(set(seen)) != len(seen):
            return None, f"`{k}` lists a path twice"
    globbed = [p for p in cfg["generated"] if GLOB & set(p)]
    if globbed:
        return None, f"generated {globbed[0]!r} is a glob; list each generated file"
    for p in cfg["generated"]:
        if is_record(p, cfg["record"]):
            return None, f"{p} is listed as both generated and a record"
        if under(p, cfg["children"]):
            return None, f"generated {p} lies under a child, whose files are its own"
    for a in cfg["children"]:
        for b in cfg["children"]:
            if norm(a) != norm(b) and under(b, [a]):
                return None, f"child {b} is inside child {a}: declare it in {a}'s own {NODE_FILE}"
    cfg["generated"] = [norm(p) for p in cfg["generated"]]
    cfg["children"] = [norm(p) for p in cfg["children"]]
    return cfg, None


def tree_files(target: Path, children):
    """The node's own files: tracked and untracked-not-ignored, present on disk, minus
    the children's subtrees (a nested repo is listed as `child/`). (paths, error)."""
    r = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                       cwd=target, capture_output=True, text=True)
    if r.returncode != 0:
        return [], r.stderr.strip() or f"git ls-files exit {r.returncode}"
    out = []
    for p in dict.fromkeys(x for x in r.stdout.split("\0") if x):
        if under(p.rstrip("/"), children) or not os.path.lexists(target / p):
            continue
        out.append(p)
    return out, None


def _state(p: Path):
    """(bytes, executable) of a file, or None when absent."""
    if not p.is_file():
        return None
    return p.read_bytes(), os.access(p, os.X_OK)


def _committed(target: Path, rel: str):
    """(bytes, executable) of rel in HEAD, or None (not committed, or no commit yet)."""
    r = subprocess.run(["git", "ls-tree", "-z", "HEAD", "--", rel], cwd=target, capture_output=True, text=True)
    meta = r.stdout.split("\t", 1)[0].split() if r.returncode == 0 and r.stdout else []
    if len(meta) != 3 or meta[1] != "blob":
        return None
    blob = subprocess.run(["git", "cat-file", "blob", meta[2]], cwd=target, capture_output=True)
    return (blob.stdout, meta[0] == "100755") if blob.returncode == 0 else None


def _first_diff(old: bytes, new: bytes):
    lo, ln = old.split(b"\n"), new.split(b"\n")
    for i, (x, y) in enumerate(zip(lo, ln)):
        if x != y:
            return f"first difference at line {i + 1}"
    return f"the render has {len(ln)} line(s), the tree's copy {len(lo)}"


def _differs(before, new):
    if before[0] != new[0]:
        return f"rendered differently ({_first_diff(before[0], new[0])})"
    return f"mode differs: executable in the {'render' if new[1] else 'tree'} only"


def rebuild(target: Path, cfg: dict, render, writer):
    """One Line per generated file, record file and unaccounted file. `render(folder)`
    renders setup's baseline as a new repo at `folder` (absent until then) and returns
    None or why it failed. `writer` is the fsw.Writer rooted at target (a dry one
    writes nothing)."""
    files, err = tree_files(target, cfg["children"])
    if err:
        return [Line(NODE_FILE, "failed", f"cannot list the tree: {err}")]
    lines = []
    did = "would write" if writer.dry_run else "wrote"
    with Scratch() as s:
        why = render(s.path / "render")
        for g in cfg["generated"]:
            new = None if why else _state(s.path / "render" / g)
            if why:
                lines.append(Line(g, "failed", f"the setup render failed: {why}"))
                continue
            if new is None:
                lines.append(Line(g, "failed", "setup renders no such file; not touched"))
                continue
            cur, head = _state(target / g), _committed(target, g)
            before = cur if cur is not None else head
            if before == new:
                if cur is None:
                    writer.write(g, new[0], mode=0o755 if new[1] else 0o644)
                lines.append(Line(g, "regenerated", "as the tree holds it" if cur is not None
                                  else f"as the last commit holds it ({did} it back)"))
            elif before is None:
                writer.write(g, new[0], mode=0o755 if new[1] else 0o644)
                lines.append(Line(g, "drift", f"in neither the tree nor the last commit; {did} the render"))
            elif cur is not None and cur != head:
                lines.append(Line(g, "drift", f"{_differs(cur, new)}; it has uncommitted changes, so it is "
                                              "kept, not re-rendered: commit or discard them, then rebuild"))
            else:
                writer.write(g, new[0], mode=0o755 if new[1] else 0o644)
                lines.append(Line(g, "drift", f"{_differs(before, new)}; {did} the render (git diff shows it)"))
    gen = set(cfg["generated"])
    for p in files:
        if p in gen:
            continue
        if p == NODE_FILE or is_record(p, cfg["record"]):
            lines.append(Line(p, "record", "the node's config" if p == NODE_FILE else "content: never written"))
        else:
            lines.append(Line(p, "unaccounted", f"named by neither generated nor record in {NODE_FILE}"))
    return lines


def overall(lines, wrote):
    """The node line's share of a rebuild: failed when a line failed, else installed
    when the rebuild wrote (or would write) a file, else unchanged. Drift and
    unaccounted are counted in the detail: the progress to make, judged by the gate."""
    if any(x.status == "failed" for x in lines):
        return "failed"
    return "installed" if wrote else "unchanged"


def counts(lines):
    c = {}
    for x in lines:
        c[x.status] = c.get(x.status, 0) + 1
    return ", ".join(f"{n} {k}" for k, n in sorted(c.items()))
