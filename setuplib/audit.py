"""Audits run by ./dev.sh check, plus the plan-section gate.

content    setup's code, data and templates name no repo, repo path or repo command.
           The names are DISCOVERED (git repos within two folders above this tool),
           never listed, so a new sibling is covered without an edit here.
direction  nothing here reads the delegation layer: the patterns are data in
           audit-terms.json (the one file exempt from this audit).
deps       each sibling dependencies.json names (the tools setup installs FROM,
           exempt from `content` for that reason) resolves to a discovered repo,
           with its CLI executable and its source a folder (setuplib/deps.py).
plans      every PLAN-*.md in a folder whose status is not done has a
           "Setup component" heading.
"""
import json
import os
import re
from pathlib import Path

from . import deps
from .core import TOOL_ROOT

# What is setup's own code, data and templates: the scope of both audits. Prose
# about this repo (CLAUDE.md, TODO.md) and the hook copies (.claude/, owned by
# their canonical repo) are out of scope by design.
CODE_GLOBS = ["setup", "dev.sh", "components.json", "dependencies.json", "setuplib/*.py", "templates/*",
              "devtools/*"]
TERMS_FILE = "audit-terms.json"
# Exempt by design: the audit's own term list, and the mutants that plant a
# finding on purpose to prove these audits go red (devtools/mutants.json).
EXEMPT = {TERMS_FILE, "mutants.json"}
# Exempt from the content audit only: the sibling tools setup installs FROM, which
# must be named to be found (setuplib/deps.py; `setup audit deps` gates each one).
# The direction audit still reads it.
CONTENT_EXEMPT = EXEMPT | {"dependencies.json"}
# Names every repo carries by contract, so naming them is not naming a repo.
CONTRACT_NAMES = {"dev.sh"}
# Folders every repo carries by contract: a plain name under one is that repo's own.
CONTRACT_DIRS = [".claude"]


def code_files(root: Path, extra_globs=(), exempt=EXEMPT):
    out = []
    for g in [*CODE_GLOBS, *extra_globs]:
        out += [p for p in sorted(root.glob(g)) if p.is_file() and "__pycache__" not in p.parts]
    return [p for p in dict.fromkeys(out) if p.name not in exempt]


def discover_repos(tool_root: Path, levels: int = 2, depth: int = 3):
    """Git work trees under the folders 1..levels above tool_root, excluding tool_root.
    Returns {repo path: relative path from the highest folder scanned}."""
    tool_root = tool_root.resolve()
    tops = [tool_root.parents[i] for i in range(min(levels, len(tool_root.parents)))]
    if not tops:
        return {}
    base = tops[-1]
    found = {}
    for top in tops:
        for dirpath, dirnames, _ in os.walk(top):
            d = Path(dirpath)
            rel_depth = len(d.relative_to(top).parts)
            dirnames[:] = [n for n in dirnames if not n.startswith(".") and n != "node_modules"]
            if (d / ".git").exists() and d != top:
                if d.resolve() != tool_root:
                    found[d.resolve()] = str(d.resolve().relative_to(base))
                dirnames[:] = []
            elif rel_depth >= depth:
                dirnames[:] = []
    return found


def repo_terms(repos: dict):
    """(label, regex) per repo name, repo path and root executable."""
    terms = []
    for path, rel in repos.items():
        name = path.name
        if re.search(r"[-_A-Z0-9]", name) or len(name) >= 12:
            terms.append((f"repo name {name}", re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])")))
        else:  # a plain word ("scripts") counts only where it reads as a path, not one
            # under a folder every repo carries (`.claude/hooks` is the repo's own)
            own = "".join(r"(?<!" + re.escape(d + "/") + r")" for d in CONTRACT_DIRS)
            terms.append((f"repo name {name}", re.compile(
                r"(?:(?<![\w.-])" + own + re.escape(name) + r"/|/" + own + re.escape(name) + r"(?![\w-])|`"
                + re.escape(name) + r"`)")))
        if "/" in rel:
            terms.append((f"repo path {rel}", re.compile(re.escape(rel) + r"(?![\w-])")))
        try:
            entries = sorted(path.iterdir())
        except FileNotFoundError:  # removed since discovery (another process's temp repo)
            entries = []
        for f in entries:
            if f.is_file() and not f.name.startswith(".") and os.access(f, os.X_OK) \
                    and f.name not in CONTRACT_NAMES:
                terms.append((f"repo command {f.name}", re.compile(
                    r"(?:\./" + re.escape(f.name) + r"|`" + re.escape(f.name) + r"`)(?![\w.-])")))
    return terms


def scan(files, terms, strip=None):
    findings = []
    for f in files:
        try:
            lines = f.read_text().splitlines()
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(lines, 1):
            probe = strip.sub("", line) if strip else line
            for label, rx in terms:
                if rx.search(probe):
                    findings.append(f"{f}:{i}: {label}")
    return findings


def audit_content(tool_root: Path = TOOL_ROOT, levels: int = 2):
    """Returns (findings, note). An empty discovery is UNCHECKED, never a silent pass."""
    repos = discover_repos(tool_root, levels)
    if not repos:
        return [], f"UNCHECKED: no sibling git repos within {levels} folders above {tool_root}; nothing to compare against"
    files = code_files(tool_root, exempt=CONTENT_EXEMPT)
    return scan(files, repo_terms(repos)), f"{len(files)} files against {len(repos)} discovered repos"


def load_direction_terms(tool_root: Path = TOOL_ROOT):
    spec = json.loads((tool_root / TERMS_FILE).read_text())
    terms = [(f"reads the delegation layer ({p})", re.compile(p)) for p in spec["paths"]]
    terms += [(f"names roster agent {n}", re.compile(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])"))
              for n in spec["roster_names"]]
    strip = re.compile("|".join(re.escape(s) for s in spec["allowed_phrases"])) if spec["allowed_phrases"] else None
    return terms, strip


def audit_direction(tool_root: Path = TOOL_ROOT):
    terms, strip = load_direction_terms(tool_root)
    if not terms:
        return [f"{TERMS_FILE}: no terms loaded; the audit would pass everything"], ""
    files = code_files(tool_root, extra_globs=["tests/*.py"])
    return scan(files, terms, strip), f"{len(files)} files against {len(terms)} terms"


def audit_deps(tool_root: Path = TOOL_ROOT, levels: int = 2):
    """(findings, note): dependencies.json against the repos discovered as `content`
    discovers them. None discovered (a lone clone): UNCHECKED, never a pass."""
    return deps.audit(tool_root, list(discover_repos(tool_root, levels)))


STATUS_RX = re.compile(r"\*\*Status:\s*([A-Za-z-]+)")
HEADING_RX = re.compile(r"^#{2,4}\s+(?:\d+[a-z]?\.?\s+)?Setup component\b", re.M)


def audit_plans(folder: Path):
    """(findings, note): each not-done PLAN-*.md must carry a Setup component heading."""
    plans = sorted(folder.glob("PLAN-*.md"))
    if not plans:
        return [f"no PLAN-*.md in {folder}"], ""
    findings, done = [], 0
    for p in plans:
        text = p.read_text()
        m = STATUS_RX.search("\n".join(text.splitlines()[:25]))
        if m and m.group(1).lower() == "done":
            done += 1
            continue
        if not HEADING_RX.search(text):
            findings.append(f"{p.name}: status {m.group(1) if m else 'unstated'}, no 'Setup component' heading")
    return findings, f"{len(plans)} plans, {done} done (skipped)"
