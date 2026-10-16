"""The `## Research` id rules of `setup plans` (PLAN-services.md §3 R1 and R6, §4
step 8.4).

A plan that uses research lists its questions under a `## Research` heading, one
per line (a list bullet allowed), as `rs-<n> -- <question>`. A Research or
Decisions section is any heading, numbered or not, at any level, titled
`Research` (a parenthesis after it allowed) or starting with the word `Decisions`
(`## 8. Decisions for Jacob`, `### 11.5 Decisions`, `## Decisions (...)`, as the
plans write them); it runs to the next heading at its level or above. In each
plan not done:

- a line of a Research section starting with an `rs-` id is in that grammar, and
  lists its id once (`malformed`, `listed-twice`); other lines there are left
  alone (a plan's research from before the service);
- every question id the plan cites (`rs-<n>`, outside fenced code) is listed
  under its Research section (`not-listed`);
- every id it cites resolves in the research service, Jacob's answer records
  (`rs-<n>.j<k>`) included (`unresolved`);
- an `rs-<n>` cited in a Decisions section is answered at `full` depth: a design
  is never put up for a yes on an open question (`open`) or on one answered only
  at `quick` (`quick`; R6, Jacob 2026-10-15). Elsewhere a plan may cite any id
  that resolves.

The service is read through its CLI only: `<cli> get <id> --json` (its `status`,
`open` or `answered`, and `answered_depth`), as a subprocess with the caller's
environment (so RESEARCH_HOME reaches it). No CLI (a lone clone) and ids cited:
every id is unchecked, never a pass. Nothing here writes."""
import json
import re
import subprocess

from setuplib import deps, plans

ID_RX = re.compile(r"(?<![\w-])rs-(\d+)(\.j\d+)?(?![\w-])")
LINE_RX = re.compile(r"^rs-(\d+) -- \S")
BULLET_RX = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
RESEARCH_TITLE = re.compile(r"^Research(?:\s*\(.*\))?$")
DECISIONS_TITLE = re.compile(r"^Decisions\b")
DEPENDENCY = "research"  # its key in dependencies.json, which says where the service is
WAIT = 30  # seconds for one `get`: a read of one record; past this it is a hang, a finding of its own
KINDS = ("malformed", "listed-twice", "not-listed", "unresolved", "open", "quick")


def service_cli(tool_root=None):
    """(the service's CLI, None), or (None, why): from dependencies.json, as every
    other dependency is found (setuplib/deps.py)."""
    kw = {} if tool_root is None else {"tool_root": tool_root}
    d, why = deps.load(**kw)
    if why:
        return None, why
    where, why = deps.resolve(DEPENDENCY, deps=d, **kw)
    if where is None:
        return None, why
    exe = deps.cli(DEPENDENCY, where, d)
    return (exe, None) if exe else (None, f"{where / d[DEPENDENCY]['cli']} is not an executable file")


def _spans(lines, title_rx):
    """[(start, end)] line ranges (the heading excluded) of the sections whose title
    (its number aside) matches, each to the next heading at its level or above."""
    heads, _ = plans._headings(lines)
    out = []
    for k, (i, level, num, title) in enumerate(heads):
        if not title_rx.match(title):
            continue
        end = next((j for j, lv, _, _ in heads[k + 1:] if lv <= level), len(lines))
        out.append((i + 1, end))
    return out


def _unfenced(lines):
    """Line indexes outside fenced code."""
    keep, fenced = [], False
    for i, line in enumerate(lines):
        if plans.FENCE_RX.match(line):
            fenced = not fenced
            continue
        if not fenced:
            keep.append(i)
    return keep


def cited(text):
    """(citations, listed, findings) of one plan: citations [(line no, id, in
    Decisions)], listed {question id: line no} from its `## Research`, and the
    grammar findings [(line no, kind, why)]."""
    lines = text.splitlines()
    live = _unfenced(lines)
    in_dec = {i for s, e in _spans(lines, DECISIONS_TITLE) for i in range(s, e)}
    in_res = {i for s, e in _spans(lines, RESEARCH_TITLE) for i in range(s, e)}
    cites, listed, findings = [], {}, []
    for i in live:
        for m in ID_RX.finditer(lines[i]):
            cites.append((i + 1, m.group(0), i in in_dec))
        if i in in_res:
            body = BULLET_RX.sub("", lines[i], count=1).strip()
            if not body.startswith("rs-"):
                continue
            m = LINE_RX.match(body)
            if not m:
                findings.append((i + 1, "malformed", "a `## Research` line is `rs-<n> -- <question>`"))
                continue
            qid = f"rs-{m.group(1)}"
            if qid in listed:
                findings.append((i + 1, "listed-twice", f"{qid} is listed at line {listed[qid]} too"))
            else:
                listed[qid] = i + 1
    return cites, listed, findings


def lookup(cli, rid):
    """(record, None) from `<cli> get <rid> --json`, or (None, why). The record's id
    is `<service>:<rid>`; one for another id is not taken as this one."""
    run = f"`{cli.name} get {rid} --json`"
    try:
        r = subprocess.run([str(cli), "get", rid, "--json"], capture_output=True, text=True, timeout=WAIT)
    except subprocess.TimeoutExpired:
        return None, f"{run} gave no answer in {WAIT}s"
    except OSError as e:
        return None, f"{run} could not run ({e.strerror or e})"
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or [f"exit {r.returncode}"])[-1]
        return None, last
    try:
        rec = json.loads(r.stdout)
    except ValueError:
        return None, f"{run} printed no JSON"
    if not isinstance(rec, dict) or str(rec.get("id")).rpartition(":")[2] != rid:
        return None, f"{run} answered for another id ({rec.get('id') if isinstance(rec, dict) else rec!r})"
    return rec, None


def depth_finding(rid, rec):
    """None when a Decisions row may rest on this question, else (kind, why)."""
    status, depth = rec.get("status"), rec.get("answered_depth")
    if status == "open":
        how = f"; its answer is only at {depth} depth" if depth else ""
        return "open", f"rests on {rid}, still open{how}: a design is not put up for a yes on an open question"
    if status == "answered" and depth == "full":
        return None
    if status == "answered" and depth == "quick":
        return "quick", (f"rests on {rid}, answered only at quick depth: raise it to full "
                         "and answer it in full first")
    return "unresolved", f"{rid}: status {status!r}, answered_depth {depth!r} not read as open or answered"


def findings(named_texts, cli):
    """(findings, unchecked, count): findings ["<file>:<line>: <kind>: <why>"] over
    [(file name, text)]; unchecked, the ids not resolved for want of a CLI; count,
    the ids cited."""
    out, cache, unchecked, count = [], {}, set(), 0
    for name, text in named_texts:
        cites, listed, grammar = cited(text)
        out += [f"{name}:{n}: {k}: {why}" for n, k, why in grammar]
        said = {n for n, _, _ in grammar}  # a malformed listing is one finding, not also not-listed
        count += len(cites)
        for n, rid, in_dec in cites:
            qid = rid.split(".")[0]
            if rid == qid and qid not in listed and n not in said:
                out.append(f"{name}:{n}: not-listed: {qid} is cited but not listed under the plan's `## Research`")
            if cli is None:
                unchecked.add(rid)
                continue
            if rid not in cache:
                cache[rid] = lookup(cli, rid)
            rec, why = cache[rid]
            if rec is None:
                out.append(f"{name}:{n}: unresolved: {rid}: {why}")
                continue
            if in_dec and rid == qid:
                f = depth_finding(rid, rec)
                if f:
                    out.append(f"{name}:{n}: {f[0]}: Decisions {f[1]}")
    return out, sorted(unchecked), count
