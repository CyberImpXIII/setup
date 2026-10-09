"""Plan sections: one addressed by its number (`§n`), the status each one states,
and the one-section replace `setup plans edit` writes (PLAN-todo-tool.md §9 step 6,
PLAN-services.md §3). Pure functions over text: the CLI reads and writes (through
fsw.Writer) and runs the plans gate (audit.plan_findings) around an edit.

A section is a numbered heading, `## 3. Title`, `### 7.12 Title`, `## 2a. Title`
(two to four `#`), and runs to the next heading of its level or above, so `§7`
holds its `### 7.9` subsections; trailing blank lines are not part of it. Headings
inside fenced code are not headings.

A section states its status in a marker on the first non-blank line under its
heading: `<!-- status: open -->`, one of STATUSES. No marker: unstated (never
guessed). A marker anywhere else, or with another value, is a finding of the plans
gate, so a status that would be ignored is never written silently.
"""
import hashlib
import re

STATUSES = ("open", "approved", "done")
NUMBERED_RX = re.compile(r"^(#{2,4})\s+(\d+[a-z]?(?:\.\d+[a-z]?)*)\.?(?:\s+(.*?))?\s*$")
ANY_HEADING_RX = re.compile(r"^(#{1,6})\s")
FENCE_RX = re.compile(r"^\s*(```|~~~)")
MARKER_RX = re.compile(r"<!--\s*status:\s*([^\s>]*)\s*-->")
REF_RX = re.compile(r"^§?(\d+[a-z]?(?:\.\d+[a-z]?)*)$")


def digest(raw: bytes) -> str:
    """The digest `plans show` prints and `plans edit --digest` takes: sha256 of the
    plan file's bytes, hex."""
    return hashlib.sha256(raw).hexdigest()


def _headings(lines):
    """[(index, level, number or None, title)] for every heading outside fenced code,
    and whether a fence is left open at the end."""
    out, fenced = [], False
    for i, line in enumerate(lines):
        if FENCE_RX.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        m = NUMBERED_RX.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2), m.group(3) or ""))
            continue
        m = ANY_HEADING_RX.match(line)
        if m:
            out.append((i, len(m.group(1)), None, line[len(m.group(1)):].strip()))
    return out, fenced


def sections(text):
    """Every numbered section: dicts with number, level, title, start and end (line
    indexes, end exclusive, trailing blank lines dropped), status (None: unstated)
    and marker (the line index of the marker under the heading, or None)."""
    lines = text.splitlines()
    heads, _ = _headings(lines)
    out = []
    for k, (i, level, num, title) in enumerate(heads):
        if num is None:
            continue
        end = next((j for j, lv, _, _ in heads[k + 1:] if lv <= level), len(lines))
        while end > i + 1 and not lines[end - 1].strip():
            end -= 1
        first = next((j for j in range(i + 1, end) if lines[j].strip()), None)
        m = MARKER_RX.fullmatch(lines[first].strip()) if first is not None else None
        out.append({"number": num, "level": level, "title": title, "start": i, "end": end,
                    "status": m.group(1) if m else None, "marker": first if m else None})
    return out


def marker_findings(name, text):
    """Each status marker that is misplaced or holds a value outside STATUSES."""
    lines = text.splitlines()
    placed = {s["marker"]: s for s in sections(text) if s["marker"] is not None}
    out, fenced = [], False
    for i, line in enumerate(lines):
        if FENCE_RX.match(line):
            fenced = not fenced
            continue
        m = None if fenced else MARKER_RX.search(line)
        if not m:
            continue
        s = placed.get(i)
        if s is None:
            out.append(f"{name}:{i + 1}: a status marker not on the first line under a numbered heading (it would be ignored)")
        elif s["status"] not in STATUSES:
            out.append(f"{name}:{i + 1}: §{s['number']} status {s['status']!r} is not one of {', '.join(STATUSES)}")
    return out


def duplicate_findings(name, secs):
    """Each section number two or more headings carry: a pointer to it cannot resolve."""
    by = {}
    for s in secs:
        by.setdefault(s["number"], []).append(s["start"] + 1)
    return [f"{name}: §{n} is carried by {len(at)} headings (lines {', '.join(map(str, at))}): "
            "a pointer to it cannot resolve" for n, at in by.items() if len(at) > 1]


def live(secs, every=False):
    """The sections to list: all with `every`, else those neither done nor inside a done one."""
    if every:
        return list(secs)
    done = [s for s in secs if s["status"] == "done"]
    return [s for s in secs if not any(d["start"] <= s["start"] < d["end"] for d in done)]


def resolve(name, text, ref):
    """(the section dict, None) or (None, why `ref` does not resolve in this text)."""
    m = REF_RX.match(ref)
    if not m:
        return None, f"not a section reference: {ref!r} (expected §<n>, e.g. §3 or §7.12)"
    num = m.group(1)
    hits = [s for s in sections(text) if s["number"] == num]
    if not hits:
        return None, f"{name}: no section §{num}"
    if len(hits) > 1:
        at = ", ".join(str(s["start"] + 1) for s in hits)
        return None, f"{name}: §{num} is ambiguous: {len(hits)} headings carry it (lines {at})"
    return hits[0], None


def section_text(name, text, ref):
    """(the section's lines joined, None) or (None, why)."""
    s, why = resolve(name, text, ref)
    if why:
        return None, why
    return "\n".join(text.splitlines()[s["start"]:s["end"]]), None


def replace(name, text, ref, new):
    """Replace exactly the section `ref` names with `new`, which must be that section
    again: its first line the heading of the same number at the same level (the title
    may change), no other heading at that level or above (that would add a section),
    no fence left open (that would hide the headings after it). Everything outside the
    section is kept byte for byte. ((new text, (first line, old last, new last)), None)
    or (None, why)."""
    s, why = resolve(name, text, ref)
    if why:
        return None, why
    body = new.splitlines()
    while body and not body[-1].strip():
        body.pop()
    if not body:
        return None, "the replacement is empty"
    m = NUMBERED_RX.match(body[0])
    if not m or m.group(2) != s["number"] or len(m.group(1)) != s["level"]:
        return None, (f"the replacement must start with the heading of §{s['number']} at its level "
                      f"(`{'#' * s['level']} {s['number']}...`), not {body[0][:60]!r}")
    heads, open_fence = _headings(body)
    if open_fence:
        return None, "the replacement opens a code fence it does not close"
    extra = [i for i, lv, _, _ in heads if i > 0 and lv <= s["level"]]
    if extra:
        return None, (f"the replacement has a heading at or above its level on its line {extra[0] + 1}: "
                      "it would add a section (edit one section at a time)")
    # split keeping line ends, so every byte outside the section is the original's
    kept = text.splitlines(keepends=True)
    last = kept[s["end"] - 1]
    tail_nl = last[len(last.rstrip("\r\n")):]  # the section's own last line ending ("" at an unterminated end)
    out = "".join(kept[:s["start"]]) + "\n".join(body) + tail_nl + "".join(kept[s["end"]:])
    return (out, (s["start"] + 1, s["end"], s["start"] + len(body))), None
