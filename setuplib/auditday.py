"""setup audit-day: the full suite, once a day, over what changed
(PLAN-check-progress.md §13 step 4; Jacob 2026-11-03: "more an audit than a check").

Each git work tree under the root that holds the shared runner's parts file
(components.json `audit_day.declared_by`), one at a time: its `check` (`./dev.sh
check --full`) runs once over every commit since the one its record names as last
audited. A repo with no commit since is `unchanged` and nothing runs. The result is
read from the runner's progress file (`times`, `passed_steps`, `unchecked`, `failed`),
never from its text, and only when that file is this run's `--full` record; else the
repo is `not-run`, with why, and its range is kept for the next run.

The range and each part's result go to `audit_day.record` inside the repo (gitignored,
written through fsw): never into the progress file, which the next short run
rewrites whole. `findings()` turns the records into the findings list a todo detect
detector prints (one per failed part, naming the range); `--todo CLI` files them
with `detect --id <audit_day.detector>`. The result is a finding, never a gate.
"""
import datetime
import json
import os
import signal
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import core
from .fanout import _git, work_trees
from .fsw import Writer

TAIL = 5  # lines of a check's output carried into an outcome
SETTLE_S = 30  # seconds a timed-out check's process group gets between SIGTERM and SIGKILL
FILE_TIMEOUT_S = 600  # seconds the store CLI gets for `repos` or `detect`
SHORT = 12  # a commit, as a range names it


class Usage(Exception):
    """The run cannot start: exit 2."""


@dataclass
class Outcome:
    path: str
    status: str
    detail: str
    range: dict = None
    parts: list = field(default_factory=list)


def spec():
    return core.load_spec()["audit_day"]


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read(path: Path):
    """(document, None), (None, None) when absent, or (None, why)."""
    try:
        return json.loads(path.read_text()), None
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as e:
        return None, str(getattr(e, "strerror", None) or e)


def declared(root: Path, ad=None):
    ad = ad or spec()
    prune = set(core.load_spec()["fanout"]["prune"])
    return [t for t in work_trees(root, prune) if (t / ad["declared_by"]).is_file()]


def _head(tree):
    r = _git(["rev-parse", "--verify", "-q", "HEAD"], tree)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def span(tree, frm, to):
    """{from, to, commits}: the commits in `to` and not in `from` (all of `to`'s on a
    first audit); commits null when git cannot count them (`from` gone)."""
    r = _git(["rev-list", "--count", to if frm is None else f"{frm}..{to}"], tree)
    n = int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else None
    return {"from": frm, "to": to, "commits": n}


def range_text(rng):
    if not rng:
        return "no range"
    n = "an uncounted number of" if rng.get("commits") is None else str(rng["commits"])
    frm = "the first commit" if rng.get("from") is None else rng["from"][:SHORT]
    return f"{frm}..{rng['to'][:SHORT]} ({n} commit{'' if n == '1' else 's'})"


def ignored(tree, rel):
    """True when git ignores rel in tree, False when it does not, None when git cannot say."""
    r = _git(["check-ignore", "-q", rel], tree)
    return {0: True, 1: False}.get(r.returncode)


def dirty(tree):
    """The paths git does not hold (tracked changes and untracked, not ignored), or None
    when git status fails."""
    r = _git(["status", "--porcelain"], tree)
    if r.returncode != 0:
        return None
    return [line[3:] for line in r.stdout.splitlines() if line.strip()]


def _kill(p):
    """SIGTERM the check's process group, SIGKILL it after SETTLE_S; bounded."""
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            p.communicate(timeout=SETTLE_S)
            return
        except subprocess.TimeoutExpired:
            continue


def run_check(tree, ad, timeout, progress):
    """(exit code, output tail, None), or (None, tail, why) when it could not run or
    finish. Its own session, so a timeout stops the whole tree of processes."""
    cmd = ad["check"]
    if not (tree / cmd[0]).is_file():
        return None, "", f"no {cmd[0]} to check with"
    env = dict(os.environ)
    env.pop("CHECK_PARTS", None)  # the repo's own parts, never a suite handed in
    env["PROGRESS_FILE"] = str(progress)
    try:
        p = subprocess.Popen(cmd, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             start_new_session=True, env=env)
    except OSError as e:
        return None, "", f"`{' '.join(cmd)}` could not run ({e.strerror or e})"
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(p)
        return None, "", f"`{' '.join(cmd)}` did not finish in {timeout}s; stopped"
    tail = [line for line in (out or "").strip().splitlines() if line.strip()][-TAIL:]
    return p.returncode, " | ".join(tail), None


def this_run(doc, before, started):
    """None when the progress file is the record of the run started at `started`, a
    --full one that ended; else why not."""
    if not isinstance(doc, dict):
        return "no progress file"
    if not (isinstance(doc.get("started"), str) and doc["started"] >= started):
        return "the progress file is an earlier run's"
    if isinstance(before, dict) and (before.get("pid"), before.get("started")) == (doc.get("pid"), doc.get("started")):
        return "the progress file is an earlier run's"
    if doc.get("full_run") is not True:
        return "the progress file is not a --full run's (a runner without --full?)"
    if doc.get("state") not in ("passed", "failed"):
        return f"the run did not end (state {doc.get('state')!r})"
    return None


def parts_of(doc):
    """([{name, result, s}], None) in the order the parts started, or (None, why) when
    the progress file disagrees with itself. failed_names is capped: never read."""
    times, passed = doc.get("times"), doc.get("passed_steps")
    unchecked = doc.get("unchecked") or []
    if not isinstance(times, dict) or not isinstance(passed, list) or not isinstance(unchecked, list):
        return None, "the progress file has no `times` and `passed_steps`"
    out = []
    for name, t in times.items():
        end, start = (t.get("end"), t.get("start")) if isinstance(t, dict) else (None, None)
        s = round(end - start, 1) if isinstance(end, (int, float)) and isinstance(start, (int, float)) else None
        if name in passed:
            res = "passed"
        elif name in unchecked:
            res = "unchecked"
        elif end is None:
            res = "unsettled"
        else:
            res = "failed"
        out.append({"name": name, "result": res, "s": s})
    stray = sorted(set(passed) - set(times))
    if stray:
        return None, f"parts passed without running ({', '.join(stray)}): not a full run"
    n_failed = sum(p["result"] in ("failed", "unsettled") for p in out)
    if n_failed != doc.get("failed"):
        return None, f"the progress file counts {doc.get('failed')!r} failed, its parts {n_failed}"
    return out, None


def _short_budget(doc):
    """The budget a short run judged (over true or false), with when; else None."""
    b = doc.get("budget") if isinstance(doc, dict) else None
    if isinstance(b, dict) and doc.get("full_run") is False and isinstance(b.get("over"), bool):
        return {**b, "at": doc.get("updated")}
    return None


def audit_one(tree: Path, label, ad, opts):
    rec_path = tree / ad["record"]
    rec, why = _read(rec_path)
    if why or (rec is not None and not isinstance(rec, dict)):
        return Outcome(label, "not-run", f"{ad['record']} is unreadable ({why or 'not an object'}): "
                                         "its owner moves it aside")
    rec = rec or {}
    head = _head(tree)
    if head is None:
        return Outcome(label, "not-run", "no commit to audit")
    frm = (rec.get("audited") or {}).get("to")
    w = Writer(tree, opts["dry_run"])

    def keep(status, detail, rng):
        """A run that audited nothing: the record's range and parts kept, `last` says why."""
        if not opts["dry_run"] and status == "not-run":
            w.write(ad["record"], json.dumps({**rec, "last": {"at": now(), "status": status, "why": detail,
                                                               "range": rng}}, indent=1) + "\n", commit=False)
        return Outcome(label, status, detail, rng)

    if frm == head:
        if (rec.get("last") or {}).get("status") == "not-run" and not opts["dry_run"]:
            w.write(ad["record"], json.dumps({**rec, "last": {"at": now(), "status": "unchanged", "why": None,
                                                               "range": None}}, indent=1) + "\n", commit=False)
        return Outcome(label, "unchanged", f"no commit since {head[:SHORT]}, audited {rec.get('at')}",
                       rec.get("audited"))
    rng = span(tree, frm, head)
    ig = ignored(tree, ad["record"])
    if ig is not True:
        return Outcome(label, "not-run", f"git does not ignore {ad['record']} (`git check-ignore` "
                                         f"{'cannot say' if ig is None else 'says no'}): nothing written", rng)
    held = dirty(tree)
    if held is None:
        return keep("not-run", "`git status` failed: what the check would run over is unknown", rng)
    # Uncommitted work is audited with the range, and named in the record and each
    # finding: a tree its owner is working in is the norm, and refusing it would
    # leave most repos never audited (2026-11-03, setup-owned; TODO.md).
    over = range_text(rng) + (f" plus {len(held)} uncommitted path(s)" if held else "")
    if opts["dry_run"]:
        return Outcome(label, "would-run", f"would run `{' '.join(ad['check'])}` over {over}", rng)
    progress = tree / ad["progress"]
    before, _ = _read(progress)
    budget = _short_budget(before) or rec.get("budget")
    started = now()
    code, tail, why = run_check(tree, ad, opts["timeout"], progress)
    if why:
        return keep("not-run", why + (f" ({tail})" if tail else ""), rng)
    doc, dwhy = _read(progress)
    why = dwhy or this_run(doc, before, started)
    parts = None
    if why is None:
        parts, why = parts_of(doc)
    if why:
        return keep("not-run", f"`{' '.join(ad['check'])}` exit {code}: {why}" + (f" ({tail})" if tail else ""), rng)
    red = [p["name"] for p in parts if p["result"] in ("failed", "unsettled")]
    after = None
    if code != 0 and not red:
        after = f"exit {code} after its parts" + (f": {tail}" if tail else "")
    result = "red" if red or after or doc["state"] != "passed" else "passed"
    unchecked = [p["name"] for p in parts if p["result"] == "unchecked"]
    at = now()
    w.write(ad["record"], json.dumps({"audited": rng, "uncommitted": held, "at": at, "result": result, "exit": code,
                                      "parts": parts, "after": after, "wall_s": doc.get("wall_s"), "budget": budget,
                                      "last": {"at": at, "status": result, "why": None, "range": rng}},
                                     indent=1) + "\n", commit=False)
    said = [f"{len(parts)} parts over {over}"]
    if red:
        said.append("failed: " + ", ".join(red))
    if after:
        said.append(after)
    if unchecked:
        said.append("unchecked: " + ", ".join(unchecked))
    return Outcome(label, result, "; ".join(said), rng, parts)


def file_findings(cli, root, ad):
    """(True, what it said) when `detect --id` ran clean, else (False, why)."""
    cmd = [cli, "-C", str(root), "--root", str(root), "detect", "--id", ad["detector"]]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FILE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return False, f"`{' '.join(cmd)}` did not finish in {FILE_TIMEOUT_S}s"
    except OSError as e:
        return False, f"`{cmd[0]}` could not run ({e.strerror or e})"
    tail = [line for line in (r.stdout + r.stderr).strip().splitlines() if line.strip()][-TAIL:]
    return r.returncode == 0, f"detect --id {ad['detector']} exit {r.returncode}" + (f": {' | '.join(tail)}" if tail else "")


def run(repos, root, opts):
    """{root, dry_run, repos[Outcome], filed, ok}. Raises Usage."""
    ad = spec()
    if repos is not None:
        found = []
        for r in repos:
            p = Path(r).resolve()
            if core._toplevel(p) != p or not (p / ad["declared_by"]).is_file():
                raise Usage(f"--repos {r}: not the top of a git work tree holding {ad['declared_by']}")
            found.append(p)
    else:
        found = declared(root, ad)
    out = [audit_one(t, os.path.relpath(t, Path.cwd()), ad, opts) for t in found]
    filed = None
    if opts["todo"] and not opts["dry_run"]:
        ok, said = file_findings(opts["todo"], root, ad)
        filed = {"ok": ok, "said": said}
    return {"root": str(root), "dry_run": opts["dry_run"], "detector": ad["detector"],
            "repos": [asdict(o) for o in out], "filed": filed,
            "ok": not any(o.status == "not-run" for o in out) and (filed is None or filed["ok"])}


# -- findings ---------------------------------------------------------------------

def repo_names(cli, root):
    """{resolved work tree: repo name} from the store CLI's own listing (`repos --status
    --json`): the names its detect files findings under. Raises Usage when it cannot list."""
    cmd = [cli, "-C", str(root), "--root", str(root), "repos", "--status", "--json"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FILE_TIMEOUT_S)
        doc = json.loads(r.stdout) if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        raise Usage(f"`{' '.join(cmd)}` gave no listing ({e})")
    if not isinstance(doc, dict) or not isinstance(doc.get("repos"), list):
        raise Usage(f"`{' '.join(cmd)}` exit {r.returncode}, no repos listing: {(r.stderr or r.stdout).strip()[-300:]}")
    base = Path(doc.get("root") or root)
    return {(base / x["path"]).resolve(): x["name"] for x in doc["repos"]
            if isinstance(x, dict) and isinstance(x.get("path"), str) and isinstance(x.get("name"), str)}


def _finding(repo, subject, count, evidence, clears):
    return {"repo": repo, "subject": subject, "count": count, "evidence": evidence, "clears_with": clears}


def findings_of(tree: Path, repo, ad):
    """The findings one repo's record (and its progress file's short-run budget) holds."""
    rec_rel, check = ad["record"], " ".join(ad["check"])
    again = f"`{check}` green over a later commit, then setup audit-day"
    out = []
    ig = ignored(tree, rec_rel)
    if ig is not True:
        out.append(_finding(repo, "audit-day record not ignored", 1,
                            f"git does not ignore {rec_rel} in {tree} (`git check-ignore` "
                            f"{'cannot say' if ig is None else 'says no'}): audit-day writes nothing there, so "
                            "never audits it", f"{rec_rel} gitignored (.progress/ in .gitignore)"))
    rec, why = _read(tree / rec_rel)
    if why or (rec is not None and not isinstance(rec, dict)):
        return out + [_finding(repo, "audit-day record unreadable", 1, f"{tree / rec_rel}: {why or 'not an object'}",
                               f"{rec_rel} moved aside, then setup audit-day")]
    rec = rec or {}
    rng, at, held = range_text(rec.get("audited")), rec.get("at"), rec.get("uncommitted") or []
    if held:
        rng += f" plus {len(held)} uncommitted path(s): " + ", ".join(held[:TAIL]) + (" ..." if len(held) > TAIL else "")
    for p in rec.get("parts") or []:
        if p.get("result") in ("failed", "unsettled"):
            out.append(_finding(repo, f"full part {p['name']} failed", 1,
                                f"{p['name']} {'did not settle' if p['result'] == 'unsettled' else 'failed'} in the "
                                f"--full run over {rng}, at {at} ({p.get('s')}s); record {tree / rec_rel}", again))
    unchecked = [p["name"] for p in rec.get("parts") or [] if p.get("result") == "unchecked"]
    if unchecked:
        out.append(_finding(repo, "full parts unchecked", len(unchecked),
                            f"said unchecked (exit 3) in the --full run over {rng}, at {at}: {', '.join(unchecked)}",
                            again))
    if rec.get("after"):
        out.append(_finding(repo, "full check failed after its parts", 1,
                            f"`{check}` over {rng}, at {at}: {rec['after']}", again))
    last = rec.get("last") or {}
    if last.get("status") == "not-run":
        out.append(_finding(repo, "audit-day did not run", 1,
                            f"at {last.get('at')}, over {range_text(last.get('range'))}: {last.get('why')}",
                            "setup audit-day audits it (the range kept meanwhile)"))
    prog, _ = _read(tree / ad["progress"])
    b = _short_budget(prog) or rec.get("budget")
    if isinstance(b, dict) and b.get("over") is True:
        slow = ", ".join(f"{s.get('name')} {s.get('s')}s" for s in b.get("slowest") or []) or "none named"
        out.append(_finding(repo, "check over budget", 1,
                            f"`./dev.sh check` took {b.get('wall_s')}s wall at {b.get('at')}, over its "
                            f"{b.get('budget_s')}s budget ({b.get('from')}); slowest: {slow}",
                            "the slowest parts tagged `full`, a short run under the budget"))
    return out


def findings(cli, root):
    """The findings list `todo detect` reads: every declared repo under root. Raises
    Usage when a repo that has findings has no name in the store CLI's listing."""
    ad = spec()
    names = repo_names(cli, root)
    out = []
    for tree in declared(root, ad):
        fs = findings_of(tree, None, ad)
        if not fs:
            continue
        name = names.get(tree.resolve())
        if name is None:
            raise Usage(f"{tree} has {len(fs)} finding(s) and no name in the store CLI's repos listing")
        out += [{**f, "repo": name} for f in fs]
    return out
