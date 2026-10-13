"""The sibling tools setup installs FROM, as data (dependencies.json): where each
one is, its CLI, and for the hook source the one comparator by meaning, and for the docs declaration its one reader.

A dependency is resolved by walking up from this tool: the first ancestor <top>
for which <top>/<path> is a git work tree. None when there is none (a lone
clone): the caller says so, never guesses another place."""
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent.parent
DEPS_FILE = "dependencies.json"
KEYS = {"path", "cli", "source", "comparator", "runner", "reader"}  # every non-comment key an entry may carry
READER_ATTRS = ("declaration", "parse", "resolve")  # what a reader names in its module


def load(tool_root: Path = TOOL_ROOT):
    """(dependencies, None), or (None, why) when the file is missing, does not parse,
    or carries an entry this code does not read in full."""
    try:
        doc = json.loads((tool_root / DEPS_FILE).read_text())
    except (OSError, ValueError) as e:
        return None, f"{DEPS_FILE} unreadable ({e.__class__.__name__})"
    deps = doc.get("dependencies") if isinstance(doc, dict) else None
    if not isinstance(deps, dict) or not deps:
        return None, f"{DEPS_FILE} has no `dependencies` object"
    for name, d in deps.items():
        if not isinstance(d, dict):
            return None, f"{DEPS_FILE}: {name} is not an object"
        extra = {k for k in d if not k.startswith("_")} - KEYS
        if extra:
            return None, f"{DEPS_FILE}: {name} carries {', '.join(sorted(extra))}, which nothing reads"
        for k in ("path", "cli"):
            if not isinstance(d.get(k), str) or not d[k] or Path(d[k]).is_absolute() or ".." in Path(d[k]).parts:
                return None, f"{DEPS_FILE}: {name}.{k} is not a relative path"
        if "source" in d and (not isinstance(d["source"], str) or ".." in Path(d["source"]).parts):
            return None, f"{DEPS_FILE}: {name}.source is not a relative path"
        if "runner" in d and not _inside_rel(d["runner"]):
            return None, f"{DEPS_FILE}: {name}.runner is not a relative path"
        c = d.get("comparator")
        if c is not None and not (isinstance(c, dict) and all(isinstance(c.get(k), str) and c[k]
                                                               for k in ("module", "function"))):
            return None, f"{DEPS_FILE}: {name}.comparator is not {{module, function}}"
        r = d.get("reader")
        if r is not None and not (isinstance(r, dict) and set(r) == {"module", *READER_ATTRS}
                                  and all(isinstance(v, str) and v for v in r.values())):
            return None, f"{DEPS_FILE}: {name}.reader is not {{module, {', '.join(READER_ATTRS)}}}"
    return deps, None


def _inside_rel(p):
    """A non-empty relative path with no `..` segment."""
    return isinstance(p, str) and p != "" and not Path(p).is_absolute() and ".." not in Path(p).parts


def runner(name, where: Path, deps):
    """(the dependency's runner file, None), or (None, why): `runner` declared, and a
    file inside the dependency's folder (a symlink out of it is refused)."""
    r = deps[name].get("runner")
    if r is None:
        return None, f"{DEPS_FILE} `{name}` declares no runner"
    p = (where / deps[name]["runner"]).resolve()
    if where.resolve() not in p.parents:
        return None, f"{DEPS_FILE} `{name}`.runner resolves to {p}, outside {where}: refused"
    if not p.is_file():
        return None, f"{DEPS_FILE} `{name}`: {where / r} is not a file"
    return p, None


def committed(where: Path, path: Path):
    """(bytes, mode, dirty, None): path as the dependency's HEAD holds it, its mode
    there (0o755 or 0o644), and whether the work tree holds changes to it git has
    not committed; or (None, None, None, why). What is rendered is the committed
    source, never another owner's work in progress."""
    where = where.resolve()
    try:
        rel = Path(path).resolve().relative_to(where).as_posix()
    except ValueError:
        return None, None, None, f"{path} is outside {where}"

    def git(*a, text=True):
        return subprocess.run(["git", "-C", str(where), *a], capture_output=True, text=text)
    t = git("ls-tree", "HEAD", "--", rel)
    if t.returncode != 0 or not t.stdout.strip():
        return None, None, None, f"{rel} is not committed in {where} (HEAD holds no such file)"
    b = git("show", f"HEAD:{rel}", text=False)
    s = git("status", "--porcelain=v1", "--", rel)
    if b.returncode != 0 or s.returncode != 0:
        return None, None, None, f"git could not read {rel} at HEAD in {where}"
    return b.stdout, 0o755 if t.stdout.split()[0] == "100755" else 0o644, bool(s.stdout.strip()), None


def resolve(name, tool_root: Path = TOOL_ROOT, deps=None):
    """(the dependency's folder, None), or (None, why). Walks up from tool_root; the
    first <ancestor>/<path> that is a git work tree, never tool_root itself."""
    if deps is None:
        deps, why = load(tool_root)
        if why:
            return None, why
    d = deps.get(name)
    if d is None:
        return None, f"{DEPS_FILE} names no `{name}`"
    me = tool_root.resolve()
    for top in me.parents:
        cand = top / d["path"]
        if (cand / ".git").exists() and cand.resolve() != me:
            return cand.resolve(), None
    return None, f"{d['path']} ({DEPS_FILE} `{name}`) is not a git work tree above {me}"


def workspace_top(name, tool_root: Path = TOOL_ROOT, deps=None):
    """The folder the dependency's path is relative to (where applies_to=repos:
    names are rooted), or None when it does not resolve."""
    if deps is None:
        deps, why = load(tool_root)
        if why:
            return None
    where, _ = resolve(name, tool_root, deps)
    if where is None:
        return None
    top = where
    for _ in Path(deps[name]["path"]).parts:
        top = top.parent
    return top


def cli(name, where: Path, deps):
    """The dependency's CLI as a path, or None when it is not an executable file."""
    p = where / deps[name]["cli"]
    return p if p.is_file() and os.access(p, os.X_OK) else None


def _module(where: Path, module):
    """(the module imported from where, None), or (None, why). A module of that
    name found elsewhere first (shadowing) is refused, never used."""
    if str(where) not in sys.path:
        sys.path.append(str(where))
    try:
        mod = importlib.import_module(module)
    except Exception as e:  # its import may fail in any way; the line says how
        return None, f"cannot import {module} from {where} ({e.__class__.__name__}: {e})"
    origin = Path(getattr(mod, "__file__", "") or "/").resolve()
    if where not in origin.parents:
        return None, f"{module} resolved to {origin}, not under {where}: refused"
    return mod, None


def reader(name, where: Path, deps):
    """({declaration: file name, parse: fn(text, label) -> rows, resolve: fn(repo
    name, repo dir, rows) -> (docs, failed)}, None), or (None, why): the docs
    declaration's one reader, imported from the dependency's own folder, so its
    file name and grammar are never a second copy here."""
    r = deps[name]["reader"]
    mod, why = _module(where, r["module"])
    if mod is None:
        return None, why
    out = {k: getattr(mod, r[k], None) for k in READER_ATTRS}
    if not (isinstance(out["declaration"], str) and out["declaration"]):
        return None, f"{r['module']}.{r['declaration']} is not a file name"
    for k in ("parse", "resolve"):
        if not callable(out[k]):
            return None, f"{r['module']} has no function {r[k]}"
    return out, None


def comparator(name, where: Path, deps):
    """(fn(path) -> meaning, None), or (None, why). The function is imported from the
    dependency's own folder and nowhere else: a module of that name found elsewhere
    first (shadowing) is refused, never used."""
    c = deps[name].get("comparator")
    if c is None:
        return None, f"{DEPS_FILE} `{name}` declares no comparator"
    mod, why = _module(where, c["module"])
    if mod is None:
        return None, why
    fn = getattr(mod, c["function"], None)
    if not callable(fn):
        return None, f"{c['module']} has no function {c['function']}"
    return fn, None


def audit(tool_root: Path = TOOL_ROOT, discovered=None):
    """(findings, note): each dependency resolves to a discovered repo, its cli is
    executable, its source (if declared) is a folder. Nothing discovered: UNCHECKED."""
    deps, why = load(tool_root)
    if why:
        return [why], ""
    if not discovered:
        return [], (f"UNCHECKED: no sibling git repos discovered around {tool_root}; "
                    f"{len(deps)} dependencies not resolved against anything")
    found = {Path(p).resolve() for p in discovered}
    findings = []
    for name, d in deps.items():
        where, why = resolve(name, tool_root, deps)
        if where is None:
            findings.append(f"{DEPS_FILE} `{name}`: {why}")
            continue
        if where not in found:
            findings.append(f"{DEPS_FILE} `{name}`: {where} is not one of the discovered repos")
        if cli(name, where, deps) is None:
            findings.append(f"{DEPS_FILE} `{name}`: {where / d['cli']} is not an executable file")
        if "source" in d and not (where / d["source"]).is_dir():
            findings.append(f"{DEPS_FILE} `{name}`: {where / d['source']} is not a folder")
        if "runner" in d:
            why = runner(name, where, deps)[1]
            if why:
                findings.append(why)
        if "reader" in d:  # its file, not an import: an import is cached once a process
            f = where / (d["reader"]["module"].replace(".", "/") + ".py")
            if not f.is_file():
                findings.append(f"{DEPS_FILE} `{name}`: {f} (its reader) is not a file")
    return findings, f"{len(deps)} dependencies against {len(found)} discovered repos"
