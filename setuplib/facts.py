"""A fact cites its command (PLAN-architecture.md §12 item 3): in a plan, a count or a
status is written with the command that produced it, as `` `<cmd>` → <value> ``.
`setup plans <dir> --facts` re-runs each cited command and lists the facts whose
value changed. The command must be a declared read verb: a `read.verbs` key of the
cli.json whose `cli` the command names. Anything else is never run and fails:
a command that is not one argv (a pipe, a redirect, `$(`), a CLI no cli.json under
the root declares, a CLI two declare (ambiguous), a verb that is not a declared read
verb (a verb only in `verbs` may write, so it is not re-run).

Resolution: the command's first word is the CLI. With a `/` it is a path from the
folder holding the plan; without one, it is the basename of exactly one declared
CLI. The verb is the first later word that names a verb the cli.json declares (in
`verbs` or `read.verbs`); none is a failure, never a guess. The command runs
without a shell, from the plan's folder, with a timeout; its stdout, stripped, is
the value, compared as text with the cited one.

A fact with no command is written `(read by hand, <date>)`; those are counted, not
run (they count against the document)."""
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

# `<cmd>` → <value>: the value a backticked span, or one word (trailing punctuation off)
FACT_RX = re.compile(r"`([^`\n]+)`\s*(?:→|->)\s*(?:`([^`\n]*)`|([^\s`]+))")
BY_HAND_RX = re.compile(r"\(read by hand, (\d{4}-\d{2}-\d{2})\)")
SHELL_RX = re.compile(r"[|;&<>]|\$\(|`")
PRUNE = {".git", "node_modules", ".mutants", "__pycache__", "tests", "fixtures"}
STATUSES = ("same", "changed", "failed", "not-declared", "not-one-command", "ambiguous")
TIMEOUT = 60


def parse(name, text):
    """[{doc, line, cmd, value}] for each `` `<cmd>` → <value> `` in text, and the
    number of `(read by hand, <date>)` marks."""
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in FACT_RX.finditer(line):
            value = m.group(2) if m.group(2) is not None else m.group(3).rstrip(".,;:)")
            out.append({"doc": name, "line": i, "cmd": m.group(1).strip(), "value": value})
    return out, len(BY_HAND_RX.findall(text))


def declared(root):
    """{cli path (resolved): {"repo", "verbs", "read"}} for each cli.json under root
    (not under .git, tests, fixtures and the like). A cli.json that does not parse, or
    names no cli, is skipped and listed: [(path, why)]."""
    found, bad = {}, []
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in PRUNE)
        if "cli.json" not in files:
            continue
        p = Path(d) / "cli.json"
        try:
            doc = json.loads(p.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            bad.append((str(p), e.__class__.__name__))
            continue
        cli = doc.get("cli") if isinstance(doc, dict) else None
        if not isinstance(cli, str) or not cli:
            bad.append((str(p), "no cli"))
            continue
        read = (doc.get("read") or {}).get("verbs") or {}
        verbs = doc.get("verbs") if isinstance(doc.get("verbs"), list) else []
        found[str((Path(d) / cli).resolve())] = {"repo": d, "verbs": set(verbs) | set(read), "read": set(read)}
    return found, bad


def resolve(cmd, here, clis):
    """(status, why, argv or None, cli path or None) for a cited command, run from
    `here`. Status is None when it may be run."""
    if SHELL_RX.search(cmd):
        return "not-one-command", "a pipe, redirect or substitution: only one argv is re-run", None, None
    try:
        argv = shlex.split(cmd)
    except ValueError as e:
        return "not-one-command", f"does not split ({e})", None, None
    if not argv:
        return "not-one-command", "empty", None, None
    head = argv[0]
    if "/" in head:
        exe = str((Path(here) / head).resolve())
        hits = [exe] if exe in clis else []
    else:
        hits = [c for c in clis if Path(c).name == head]
    if not hits:
        return "not-declared", f"{head}: no cli.json under the root declares this CLI", argv, None
    if len(hits) > 1:
        return "ambiguous", f"{head}: {len(hits)} cli.json files declare a CLI of that name", argv, None
    spec = clis[hits[0]]
    verb = next((w for w in argv[1:] if w in spec["verbs"]), None)
    if verb is None:
        return "not-declared", f"{head}: names no verb its cli.json declares", argv, hits[0]
    if verb not in spec["read"]:
        return "not-declared", f"{head} {verb}: not a declared read verb (cli.json read.verbs), so not re-run", \
            argv, hits[0]
    return None, verb, [hits[0], *argv[1:]], hits[0]


def check(fact, here, clis):
    """{**fact, status, now, why}: the fact re-derived, or why it could not be."""
    status, why, argv, _ = resolve(fact["cmd"], here, clis)
    if status:
        return {**fact, "status": status, "now": None, "why": why}
    try:
        r = subprocess.run(argv, cwd=here, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                           timeout=TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {**fact, "status": "failed", "now": None, "why": f"{e.__class__.__name__}: {e}"[:200]}
    if r.returncode != 0:
        tail = (r.stderr.strip() or r.stdout.strip())[-160:]
        return {**fact, "status": "failed", "now": None, "why": f"exit {r.returncode}: {tail}"}
    now = r.stdout.strip()
    if now == fact["value"]:
        return {**fact, "status": "same", "now": now, "why": ""}
    return {**fact, "status": "changed", "now": now, "why": f"cited {fact['value']!r}, now {now[:80]!r}"}
