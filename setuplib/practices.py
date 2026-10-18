"""The `## Practices` rules of `setup plans` (PLAN-services.md §3 A3, §4 step 7.3).

A plan that builds or changes a tool carries a `## Practices` heading, as it does
"Setup component" (a heading at level 2 to 4, numbered or not, titled `Practices`,
a parenthesis after it allowed). It runs to the next heading at its level or
above, and names the registry ids the work touches, one per list item, each item
starting with the id in backticks:

    ## Practices
    - `root-seams`: the new verb's output is held by tests/test_x.py

In each plan not done that carries the heading:

- the section names at least one id (`no-ids`), each once (`listed-twice`);
- every id named there resolves in the practice registry (`unresolved`);
- every approved design decision names its gate row or says why none can
  (`no-gate-row`). A decision is one list item, or one paragraph, of a Decisions
  section (any heading titled `Decisions...`, as setuplib/rsids.py reads it); it
  is approved when it carries the word `approved` (the plans write `approved:
  Jacob <date>`). It names its row as gate: `<id>` (the id resolves, as above) or
  says `prose: <why>`.

The rule that every plan not done carries the heading is HELD (REQUIRE_HEADING):
on 2026-10-18 none of the workspace's 36 live plans did, and a red `setup plans`
refuses every `setup plans edit` and `add`, so turning it on before they carry it
would stop every plan write. While held, the plans without it are counted in a
note, never failed, and the decision rule applies only where the heading is.

The registry is the one A1 names: the `registry` file of the dependency
DEPENDENCY names in dependencies.json, its `rules[].id`. It is read, never written. An id cited
when the registry cannot be read is unchecked, never a pass."""
import json
import re

from setuplib import deps, plans, rsids

TITLE = re.compile(r"^Practices(?:\s*\(.*\))?$")
ID = r"[a-z0-9]+(?:-[a-z0-9]+)*"
ID_LINE = re.compile(rf"^`({ID})`")
GATE_RX = re.compile(rf"\bgate:\s*`({ID})`")
PROSE_RX = re.compile(r"\bprose:\s*\S")
APPROVED_RX = re.compile(r"\bapproved\b", re.I)
DEPENDENCY = "checks"  # its key in dependencies.json; its `registry` names the file
REQUIRE_HEADING = False  # held: see the module docstring; Jacob says when it turns on
KINDS = ("missing", "no-ids", "listed-twice", "unresolved", "no-gate-row")


def registry_ids(tool_root=None):
    """(the set of registry ids, where it was read), or (None, why): the checks
    dependency's `registry` file, its `rules`, each row's `id`."""
    kw = {} if tool_root is None else {"tool_root": tool_root}
    d, why = deps.load(**kw)
    if why:
        return None, why
    where, why = deps.resolve(DEPENDENCY, deps=d, **kw)
    if where is None:
        return None, why
    path, why = deps.registry(DEPENDENCY, where, d)
    if path is None:
        return None, why
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return None, f"{path} unreadable ({e.__class__.__name__})"
    rows = doc.get("rules") if isinstance(doc, dict) else None
    if not isinstance(rows, list) or not rows:
        return None, f"{path} has no `rules` list"
    ids = {r["id"] for r in rows if isinstance(r, dict) and isinstance(r.get("id"), str) and r["id"]}
    if not ids:
        return None, f"{path}: no row of `rules` carries an id"
    return ids, str(path)


def _items(lines, start, end, live):
    """[(first line index, text)]: each list item or paragraph between start and
    end, outside fenced code. A bullet starts an item; a blank line ends one."""
    out, cur = [], None
    for i in range(start, end):
        if i not in live or not lines[i].strip():
            cur = None
            continue
        if rsids.BULLET_RX.match(lines[i]) or cur is None:
            cur = [i, lines[i]]
            out.append(cur)
        else:
            cur[1] += "\n" + lines[i]
    return [tuple(c) for c in out]


def cited(text):
    """(has the heading, named, decisions, findings) of one plan: named [(line no,
    id)] from its Practices sections; decisions [(line no, gate id or None)] for
    each approved decision, None when it says prose; findings [(line no, kind,
    why)] of the grammar."""
    lines = text.splitlines()
    live = set(rsids._unfenced(lines))
    heads, _ = plans._headings(lines)
    spans = []
    for k, (i, level, _num, title) in enumerate(heads):
        if 2 <= level <= 4 and TITLE.match(title):
            spans.append((i, next((j for j, lv, _, _ in heads[k + 1:] if lv <= level), len(lines))))
    named, findings, seen = [], [], {}
    for h, end in spans:
        mine = 0
        for i in range(h + 1, end):
            if i not in live:
                continue
            m = ID_LINE.match(rsids.BULLET_RX.sub("", lines[i], count=1).strip()) \
                if rsids.BULLET_RX.match(lines[i]) else None
            if not m:
                continue
            mine += 1
            if m.group(1) in seen:
                findings.append((i + 1, "listed-twice", f"`{m.group(1)}` is named at line {seen[m.group(1)]} too"))
                continue
            seen[m.group(1)] = i + 1
            named.append((i + 1, m.group(1)))
        if not mine:
            findings.append((h + 1, "no-ids", "a `## Practices` section names the registry ids the work touches, "
                                              "one list item each, starting `- `<id>``"))
    decisions = []
    if spans:
        for s, e in rsids._spans(lines, rsids.DECISIONS_TITLE):
            for i, body in _items(lines, s, e, live):
                if not APPROVED_RX.search(body):
                    continue
                g = GATE_RX.search(body)
                if g:
                    decisions.append((i + 1, g.group(1)))
                elif PROSE_RX.search(body):
                    decisions.append((i + 1, None))
                else:
                    findings.append((i + 1, "no-gate-row", "an approved decision names its gate row "
                                                           "(gate: `<id>`) or says `prose: <why>`"))
    return bool(spans), named, decisions, findings


def findings(named_texts, ids, require_heading=REQUIRE_HEADING):
    """(findings, unchecked, without): findings ["<file>:<line>: <kind>: <why>"] over
    [(file name, text)] of the plans not done; unchecked, the ids not resolved for
    want of a registry (ids None); without, the plans that carry no heading."""
    out, unchecked, without = [], set(), []
    for name, text in named_texts:
        has, named, decisions, grammar = cited(text)
        if not has:
            without.append(name)
            if require_heading:
                out.append(f"{name}:1: missing: no `## Practices` heading naming the registry ids the work touches")
            continue
        out += [f"{name}:{n}: {k}: {why}" for n, k, why in grammar]
        for n, rid in named + [(n, g) for n, g in decisions if g]:
            if ids is None:
                unchecked.add(rid)
            elif rid not in ids:
                out.append(f"{name}:{n}: unresolved: `{rid}` is no id of the practice registry")
    return out, sorted(unchecked), without
