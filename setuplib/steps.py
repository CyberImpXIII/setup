"""Plan steps (PLAN-services.md §3 "Plan steps are always tracked", G1 and G5): the
one parser of a plan's steps (`setup plans steps <file> --json`), what each step's
tag resolves to (`setup plans <dir> --steps`), and the citations of plan steps found
elsewhere (the reverse check). All reports, never a failing gate: G2's failing half
is held (§3 G6, G2-1), so the plans gate only counts the unplaceable steps.

G1's grammar, as this parser reads it:
- A step is a numbered list item (`1. text`) under a heading whose title starts with
  one of STEP_HEADINGS, or under a heading nested (by level) inside one. A numbered
  heading's title is the text after its number (`## 4. Steps`). Fenced code is text.
- An item indented under another is a step too, numbered `<parent>.<n>` (`6.1`). A
  step's text runs to the next item at its indent or less, the next heading, or,
  after a blank line, a line indented less than its text; its own text leaves out
  its children's.
- A step is cited `<file> §<section> step <number>`: the section is the innermost
  numbered section holding it (None when there is none).
- Owners: the text starts with backticked names and a colon: `` `alpha`: ... ``,
  `` **`beta`:** ... ``, `` `alpha` and `beta`: ... ``.
- Its tag: one `track:` outside code spans, ending its own text, whose value is
  exactly one form of TRACK_FORMS (G1's table).
- Placeable: it names an owner or carries a tag of the table. A step with children
  is a group, placed through its children. Unplaceable, with the reason: two tags,
  a tag off the table (or not at the end), or no owner and no tag.
"""
import hashlib
import json
import re
import subprocess
from pathlib import Path

from . import plans

STEP_HEADINGS = ("Steps", "Phase", "Handoff")
_REF = r"\d+[a-z]?(?:\.\d+[a-z]?)*"
TRACK_FORMS = {  # G1's table: the tag's kind -> its value's exact grammar
    "todo": re.compile(r"todo:(?P<repo>[^\s#]+)#(?P<id>[\w.-]+)"),
    "TODO.md": re.compile(r'TODO\.md\s+"(?P<title>[^"]+)"'),
    "needs-yes": re.compile(r"needs-yes\s+(?P<file>[\w./-]+\.md)\s*§(?P<ref>" + _REF + ")"),
    "superseded-by": re.compile(r"superseded-by\s+(?P<file>[\w./-]+\.md)\s*§(?P<ref>" + _REF + ")"),
    "done": re.compile(r"done\s+(?P<repo>[^\s@]+)@(?P<commit>[0-9a-f]{7,40})"),
}
STATUSES = {  # what `--steps` prints per step: G5's four first
    "open": "its item is open: a store item not closed, a TODO.md item present",
    "closed": "its item is closed: a store item closed, a `done` commit that exists",
    "needs-yes": "not approved yet; the pointer resolves",
    "superseded": "replaced by other work; the pointer resolves",
    "untracked": "names its owner, no tag: the plan sync makes its item",
    "dangling": "its tag does not resolve (the reason is printed)",
    "unchecked": "its tag could not be looked up here (the reason is printed): never a pass",
    "unplaceable": "no owner and no tag, or a tag off the table: a person fixes the step",
    "group": "has children, each reported on its own",
}
CITE_STATUSES = ("ok", "dangling", "ambiguous")

ITEM_RX = re.compile(r"^( *)(\d+)\.\s+(.*)$")
OWNER_RX = re.compile(r"^(?:\*\*)?(`[^`\s]+`(?:\s*(?:,|and|&)\s*`[^`\s]+`)*)\s*(?::\s*\*\*|\*\*\s*:|:)")
CODE_RX = re.compile(r"`[^`]*`")
TAG_RX = re.compile(r"(?<![\w-])track:")
CITE_RX = re.compile(r"((?:[\w.-]+/)*PLAN-[\w.-]+\.md)\s*§\s*(" + _REF + r")(?:,?\s+step\s+(\d+(?:\.\d+)*))?")


def _blocks(lines):
    """[(first line, end, the steps heading's line)] for each run of lines between two
    headings that a steps heading holds, itself or by level."""
    heads, _ = plans._headings(lines)
    out, stack = [], []
    for k, (i, level, _, title) in enumerate(heads):
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, i, title.startswith(STEP_HEADINGS)))
        holder = next((ln for _, ln, is_steps in reversed(stack) if is_steps), None)
        if holder is not None:
            out.append((i + 1, heads[k + 1][0] if k + 1 < len(heads) else len(lines), holder))
    return out


def _items(lines, first, end):
    """The numbered items of lines[first:end], nested by indent: dicts with step,
    parent, line, own (its lines) and children."""
    items, stack, blank, fenced = [], [], False, False
    for j in range(first, end):
        line = lines[j]
        if plans.FENCE_RX.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if not line.strip():
            blank = True
            continue
        ind = len(line) - len(line.lstrip(" "))
        m = ITEM_RX.match(line)
        if m:
            while stack and stack[-1]["ind"] >= ind:
                stack.pop()
            parent = stack[-1] if stack else None
            num = f"{parent['step']}.{m.group(2)}" if parent else m.group(2)
            it = {"step": num, "parent": parent["step"] if parent else None, "line": j + 1, "ind": ind,
                  "col": ind + len(m.group(2)) + 2, "own": [m.group(3)], "children": []}
            if parent:
                parent["children"].append(num)
            items.append(it)
            stack.append(it)
        elif stack and not blank:  # a lazy continuation: the deepest open item's
            stack[-1]["own"].append(line.strip())
        elif stack:
            holders = [s for s in stack if s["col"] <= ind]
            if holders:
                while stack[-1] is not holders[-1]:
                    stack.pop()
                holders[-1]["own"].append(line.strip())
            else:  # a paragraph after the list ends it
                stack = []
        blank = False
    return items


def _track(text):
    """(kind, fields, value): (None, None, None) untagged; (None, why, value) off the table."""
    bare = CODE_RX.sub(lambda m: " " * len(m.group(0)), text)
    at = [m.end() for m in TAG_RX.finditer(bare)]
    if not at:
        return None, None, None
    if len(at) > 1:
        return None, f"carries {len(at)} track tags, not one", None
    value = text[at[0]:].strip()
    for kind, rx in TRACK_FORMS.items():
        m = rx.fullmatch(value)
        if m:
            return kind, m.groupdict(), value
    return None, (f"its track tag is off G1's table or does not end the step: {value[:80]!r} "
                  f"(kinds: {', '.join(TRACK_FORMS)})"), value


def parse(name, text):
    """Every step of one plan, in file order: dicts with file, section, heading,
    heading_line, step, parent, line (1-based), text (its own, whitespace collapsed),
    hash (sha256 of that text without its tag: what a renumbered step is matched by),
    owners, track ({kind, value, fields} or None), children, placeable and why."""
    lines = text.splitlines()
    secs = plans.sections(text)
    out = []
    for first, end, holder in _blocks(lines):
        for it in _items(lines, first, end):
            own = " ".join(" ".join(it["own"]).split())
            kind, info, value = _track(own)
            bare = own[:own.rfind("track:")].rstrip() if kind else own
            j = it["line"] - 1
            sec = max((s for s in secs if s["start"] < j < s["end"]), key=lambda s: s["start"], default=None)
            owners = re.findall(r"`([^`]+)`", OWNER_RX.match(own).group(1)) if OWNER_RX.match(own) else []
            if it["children"]:
                why = None
            elif kind is None and info is not None:
                why = info
            elif kind is None and not owners:
                why = "names no owner (`name`: at its start) and carries no track tag"
            else:
                why = None
            out.append({"file": name, "section": sec["number"] if sec else None,
                        "heading": lines[holder].lstrip("#").strip(), "heading_line": holder + 1,
                        "step": it["step"], "parent": it["parent"], "line": it["line"], "text": own,
                        "hash": hashlib.sha256(bare.encode()).hexdigest(), "owners": owners,
                        "track": {"kind": kind, "value": value, "fields": info} if kind else None,
                        "children": it["children"], "placeable": why is None, "why": why})
    return out


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def resolve(step, folder: Path, todo_cli=None):
    """(status, detail) for one parsed step, its tag looked up from `folder` (the
    plans' folder: TODO.md beside them, repos and plans relative to it). A store item
    is looked up only through `todo_cli` (`<cli> -C <repo> get <id>`, JSON with
    `closed`); without it, or when that fails, the step is unchecked, never guessed."""
    if step["children"]:
        return "group", f"{len(step['children'])} children"
    if not step["placeable"]:
        return "unplaceable", step["why"]
    t = step["track"]
    if t is None:
        return "untracked", "owner " + ", ".join(step["owners"])
    kind, f = t["kind"], t["fields"]
    if kind in ("needs-yes", "superseded-by"):
        try:
            text = (folder / f["file"]).read_text()
        except (OSError, UnicodeDecodeError):
            return "dangling", f"{f['file']}: no such file beside the plans"
        _, why = plans.resolve(f["file"], text, f["ref"])
        if why:
            return "dangling", why
        return ("needs-yes" if kind == "needs-yes" else "superseded"), f"{f['file']} §{f['ref']}"
    if kind == "TODO.md":
        try:
            text = (folder / "TODO.md").read_text()
        except (OSError, UnicodeDecodeError):
            return "dangling", "no TODO.md beside the plans"
        rx = re.compile(r"^\s*(?:[-*]|\d+\.)\s+\*\*" + re.escape(f["title"]) + r"\*\*", re.M)
        m = rx.search(text)
        if not m:
            return "dangling", f'no TODO.md item with the bold title "{f["title"]}"'
        return "open", f'TODO.md:{text.count(chr(10), 0, m.start()) + 1} "{f["title"]}"'
    if kind == "done":
        repo = folder / f["repo"]
        if _git(repo, "rev-parse", "--show-toplevel").returncode != 0:
            return "dangling", f"{f['repo']}: not a git repo beside the plans"
        r = _git(repo, "show", "-s", "--format=%cs", f"{f['commit']}^{{commit}}")
        if r.returncode != 0:
            return "dangling", f"no commit {f['commit']} in {f['repo']}"
        return "closed", f"{f['repo']}@{f['commit']} ({r.stdout.strip()})"
    # kind == "todo": a store item
    if not todo_cli:
        return "unchecked", f"store item {t['value']}: pass --todo CLI to look it up"
    r = subprocess.run([todo_cli, "-C", str(folder / f["repo"]), "get", f["id"]], capture_output=True, text=True)
    first = (r.stderr.strip().splitlines() or [""])[0]
    if r.returncode != 0:
        return "unchecked", f"{t['value']}: get exited {r.returncode}: {first[:160]}"
    try:
        closed = json.loads(r.stdout).get("closed")
    except (ValueError, AttributeError):
        closed = None
    if not isinstance(closed, bool):
        return "unchecked", f"{t['value']}: get printed no boolean `closed`"
    return ("closed" if closed else "open"), t["value"]


def citations(source, text):
    """Each citation of a plan section or step in `text`: dicts with source, line,
    plan (as written), section and step (None for a section alone)."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in CITE_RX.finditer(line):
            out.append({"source": source, "line": i, "plan": m.group(1), "section": m.group(2),
                        "step": m.group(3)})
    return out


def check_citation(c, folder: Path, parsed):
    """(status, why) for one citation: the plan, its section and (when cited) its step
    exist, once. `parsed` caches {plan path: (text, steps)}."""
    p = folder / c["plan"]
    if p not in parsed:
        try:
            text = p.read_text()
            parsed[p] = (text, parse(p.name, text))
        except (OSError, UnicodeDecodeError):
            parsed[p] = (None, [])
    text, steps = parsed[p]
    if text is None:
        return "dangling", f"{c['plan']}: no such plan in {folder}"
    _, why = plans.resolve(p.name, text, c["section"])
    if why:
        return "dangling", why
    if c["step"] is None:
        return "ok", None
    sec = c["section"]
    hits = [s for s in steps if s["step"] == c["step"] and s["section"] == sec] or \
           [s for s in steps if s["step"] == c["step"] and (s["section"] or "").startswith(sec + ".")]
    if not hits:
        return "dangling", f"{p.name} §{sec} holds no step {c['step']}"
    if len(hits) > 1:
        return "ambiguous", (f"{p.name} §{sec} step {c['step']} is carried by {len(hits)} steps "
                             f"(lines {', '.join(str(s['line']) for s in hits)})")
    return "ok", None
