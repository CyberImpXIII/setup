"""setup: bring one git repo to the shared baseline, from its path alone.

Content-agnostic: nothing here knows what the target repo does. What gets
installed is declared in components.json; the files come from templates/ and
from the hook source folder (default: this tool's own .claude/). Every write
goes through fsw.Writer, the one place --dry-run is enforced.
"""
import copy
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .fsw import Writer, ignore_verdicts

TOOL_ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = TOOL_ROOT / "components.json"

# Worst first: a component's overall status is the worst of its parts, and the
# exit code is 1 when any result is one of BAD.
PRECEDENCE = ["failed", "drift", "needs-jacob", "needs-owner", "needs-harness",
              "installed", "none", "unchanged"]
BAD = {"failed", "drift"}


class Refused(Exception):
    """The path is not one setup may touch. Raised before anything is written."""


@dataclass
class Result:
    component: str
    status: str
    detail: str = ""


def load_spec(path: Path = SPEC_PATH) -> dict:
    return json.loads(path.read_text())


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _toplevel(p: Path):
    r = _git(["rev-parse", "--show-toplevel"], p)
    return Path(r.stdout.strip()).resolve() if r.returncode == 0 else None


def preflight(target: Path):
    """Decide what the path is, or refuse. Returns (is_new, existed_empty). Writes nothing."""
    if target.exists():
        if not target.is_dir():
            raise Refused(f"{target} exists and is not a directory")
        top = _toplevel(target)
        if top is not None and top != target:
            raise Refused(f"{target} is inside the git work tree {top}, not its top level; "
                          "setup works on a whole repo")
        if top == target:
            return False, False
        if any(target.iterdir()):
            raise Refused(f"{target} exists, is not empty, and is not a git work tree; "
                          "setup will not turn someone's folder into a repo")
        return True, True
    parent = target.parent
    if not parent.is_dir():
        raise Refused(f"the parent folder {parent} does not exist; create it first")
    top = _toplevel(parent)
    if top is not None:
        raise Refused(f"{parent} is inside the git work tree {top}; a new repo there would nest")
    return True, False


def _read(p: Path):
    try:
        return p.read_text()
    except FileNotFoundError:
        return None


def _fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{" + k + "}", v)
    return text


def roster_dir(target: Path, base: Path):
    """target relative to base, as a normalised POSIX path ("." for base itself);
    None when target is not under base: a roster dir is relative, never absolute
    and never climbing out with '..'."""
    try:
        return target.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return None


def worst(statuses):
    return min(statuses, key=PRECEDENCE.index)


class Setup:
    def __init__(self, target: Path, *, label: str, name: str, dry_run: bool,
                 github: bool = False, private: bool = False, owner=None,
                 hooks_from=None, plugins_from=None, user_scope_from=None, dir_base=None, gh: str = "gh",
                 spec=None):
        self.target = target
        self.dir_base = Path(dir_base) if dir_base is not None else Path.cwd()
        self.label = label
        self.name = name
        self.dry_run = dry_run
        self.github = github
        self.private = private
        self.owner = owner
        self.gh = gh
        self.spec = spec or load_spec()
        self.comp = {c["name"]: c for c in self.spec["components"]}
        hf = self.comp["hooks"]["source"]
        self.hooks_from = Path(hooks_from) if hooks_from else TOOL_ROOT / hf
        self.plugins_from = Path(plugins_from) if plugins_from else None
        self.user_scope_from = Path(user_scope_from) if user_scope_from else None
        self.w =Writer(target, dry_run)
        self.is_new = False
        self.repo_slug = None

    # ---- components: one method per name in components.json -----------------

    def c_repo(self):
        if not self.is_new:
            return Result("repo", "unchanged", "an existing git work tree")
        err = self.w.create_repo(self._existed_empty)
        if err:
            return Result("repo", "failed", err)
        did = "would create {} and run git init" if self.dry_run else "created {} and ran git init"
        return Result("repo", "installed", did.format(self.label))

    def c_rules(self):
        c = self.comp["rules"]
        tmpl = (TOOL_ROOT / c["template"]).read_text()
        bid = c["block_id"]
        begin = f"<!-- shared:{bid}@{sha12(tmpl)} -->"
        end = "<!-- /shared -->"
        block = f"{begin}\n{tmpl}{end}\n"
        f = self.target / c["file"]
        text = _read(f)
        if text is None:
            head = _fill((TOOL_ROOT / c["head"]).read_text(), {"name": self.name})
            self.w.write(c["file"], head + block)
            return Result("rules", "installed", f"{c['file']} with the shared block @{sha12(tmpl)}")
        rx = re.compile(r"<!-- shared:" + re.escape(bid) + r"@([0-9a-f]{12}) -->\n(.*?)" + re.escape(end) + r"\n?", re.S)
        found = list(rx.finditer(text))
        if len(found) > 1:
            return Result("rules", "drift", f"{c['file']} holds {len(found)} shared:{bid} blocks; it must hold one")
        if not found:
            return Result("rules", "drift", f"{c['file']} has no shared:{bid} block (its rules are a hand copy); "
                                            "its owner replaces them with the block")
        m = found[0]
        mark, body = m.group(1), m.group(2)
        if body == tmpl and mark == sha12(tmpl):
            return Result("rules", "unchanged", f"block @{mark}")
        if sha12(body) != mark:
            return Result("rules", "drift", f"block edited locally (content @{sha12(body)}, marker @{mark}); "
                                            "not overwritten: propose the change to the template instead")
        new = text[:m.start()] + block + text[m.end():]
        self.w.write(c["file"], new)
        return Result("rules", "installed", f"block updated @{mark} -> @{sha12(tmpl)} (was behind the template)")

    def c_hooks(self):
        src_dir = self.hooks_from / "hooks"
        srcs = sorted(src_dir.glob("*.sh")) if src_dir.is_dir() else []
        if not srcs:
            return Result("hooks", "failed", f"no hooks found in {src_dir}")
        cover, statuses, notes = self._user_scope()
        n_new = n_same = 0
        covered, unknown = [], {}
        for s in srcs:
            rel = f".claude/hooks/{s.name}"
            dst = self.target / rel
            state, why = cover(rel)
            if state is None:
                unknown.setdefault(why, []).append(s.name)
            if state is True:  # user scope runs it from its source: no copy, an existing one kept
                covered.append(s.name)
                if dst.exists() and not os.access(dst, os.X_OK):
                    statuses.append("drift")
                    notes.append(f"{s.name} is not executable (a broken copy, whatever user scope runs)")
                else:
                    statuses.append("unchanged")
            elif not dst.exists():
                self.w.write(rel, s.read_bytes(), mode=0o755)
                n_new += 1
                statuses.append("installed")
            elif dst.read_bytes() != s.read_bytes():
                statuses.append("drift")
                notes.append(f"{s.name} differs from the source copy (not overwritten)")
            elif not os.access(dst, os.X_OK):
                statuses.append("drift")
                notes.append(f"{s.name} is not executable")
            else:
                n_same += 1
                statuses.append("unchanged")
        if covered:
            notes.append(f"covered by user scope: {', '.join(covered)} (not copied; a copy already here is kept)")
        elif self.user_scope_from is not None and not statuses.count("failed"):
            notes.append("user scope covers none of these hooks")
        for why, names in unknown.items():
            notes.append(f"user scope could not tell ({why}): treated as not covered for {', '.join(names)}")
        extra, p_statuses, p_notes = self._plugin_wants()
        st, note = self._settings([s.name for s in srcs if s.name not in covered], extra, drop=covered)
        statuses += [st, *p_statuses]
        if note:
            notes.append(note)
        notes += p_notes
        head = f"{n_new} installed, {n_same} unchanged of {len(srcs)}, against {src_dir}"
        return Result("hooks", worst(statuses), "; ".join([head, *notes]))

    def _user_scope(self):
        """(cover, statuses, notes) from the report given with --user-scope: the JSON
        the shared hooks source prints for its copies, of which only `user_scope` is
        read, never the user settings themselves. cover(rel) is (True | False | None,
        why) for the copy at rel, by the rule the shared checks read from the same
        report (_coverage). Without the report nothing is covered, and the line says so;
        a report not in that shape fails, and nothing is covered."""
        nothing = (lambda rel: (False, None))
        if self.user_scope_from is None:
            return nothing, [], ["user scope not checked (no --user-scope report given)"]
        try:
            rep = json.loads(self.user_scope_from.read_text())
        except (OSError, ValueError) as e:
            return nothing, ["failed"], [f"user-scope report {self.user_scope_from} unreadable "
                                         f"({e.__class__.__name__}); nothing treated as covered"]
        us, why = _user_scope_shape(rep)
        if why:
            return nothing, ["failed"], [f"user-scope report not in the shape read here ({why}); "
                                         "nothing treated as covered"]
        notes = [] if us["exists"] else [f"user scope: no user settings file ({us.get('settings')}), "
                                         "so nothing is covered"]
        return (lambda rel: _coverage(us, rel)), [], notes

    def _plugin_wants(self):
        """(wanted, statuses, notes) from the plug-in registry given with --plugins: the
        JSON the shared hooks source prints for the hooks it registers to run in place
        ({root, ok, plugins: [{name, applies_to, faults, registration}]}). A plug-in is
        proposed only where its applies_to resolves to this target. Its registration
        runs from the registry's root, so one that applies below the root fails rather
        than guess its command from there; roles: are outside setup's lane (needs-*)."""
        if self.plugins_from is None:
            return [], [], ["plug-in hooks not checked (no --plugins registry given)"]
        try:
            reg = json.loads(self.plugins_from.read_text())
        except (OSError, ValueError) as e:
            return [], ["failed"], [f"plug-in registry {self.plugins_from} unreadable "
                                    f"({e.__class__.__name__}); none proposed"]
        if (not isinstance(reg, dict) or reg.get("ok") is not True or not reg.get("root")
                or not isinstance(reg.get("plugins"), list)):
            return [], ["failed"], ["plug-in registry is not ok (its own check found a fault, or it "
                                    "lacks root or plugins); none proposed from it"]
        rel = roster_dir(self.target, Path(reg["root"]))
        wanted, statuses, notes, applied = [], [], [], []
        for p in reg["plugins"]:
            name = p.get("name") if isinstance(p, dict) else None
            regn = p.get("registration") if name else None
            if not name or not isinstance(regn, dict) or p.get("faults"):
                statuses.append("failed")
                notes.append(f"plug-in {name or '?'}: malformed, or faulty in its registry; not proposed")
                continue
            where = _applies(p.get("applies_to"), rel)
            if where == "no":
                continue
            if where == "unknown":
                statuses.append("failed")
                notes.append(f"plug-in {name}: applies_to={p.get('applies_to')!r} not understood; not proposed")
                continue
            if where == "roles":
                statuses.append("needs-harness")
                notes.append(f"plug-in {name}: applies_to={p['applies_to']} names roles, which setup "
                             f"cannot resolve; where they live, register: {json.dumps(regn)}")
                continue
            if rel != ".":
                statuses.append("failed")
                notes.append(f"plug-in {name} applies to {rel}, but its registration runs from the workspace "
                             f"top {reg['root']}; none given for {rel}, so none proposed")
                continue
            for event, groups in regn.items():
                for g in groups:
                    for h in g.get("hooks", []):
                        wanted.append((event, g.get("matcher"), h))
            applied.append(name)
        notes.append(f"plug-in hooks that apply here: {', '.join(applied) or 'none'}")
        return wanted, statuses, notes

    def _settings(self, names, extra=(), drop=()):
        """Registrations the source settings.json makes for these hooks, plus `extra`
        (event, matcher, hook) wanted besides, against the target's. A shared hook in
        `drop` runs at user scope: a per-repo registration of it would run it twice, so
        the proposal leaves it out (settings.json itself is never touched)."""
        try:
            src = json.loads((self.hooks_from / "settings.json").read_text())
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return "failed", f"source settings.json unreadable ({e.__class__.__name__})"
        tpath = self.target / ".claude" / "settings.json"
        text = _read(tpath)
        try:
            tgt = json.loads(text) if text is not None else {}
        except json.JSONDecodeError:
            return "failed", ".claude/settings.json does not parse; nothing proposed"
        wanted = []  # (event, matcher, hook object)
        for event, groups in (src.get("hooks") or {}).items():
            for g in groups:
                for h in g.get("hooks", []):
                    script = _script(h.get("command", ""))
                    if script in names:
                        wanted.append((event, g.get("matcher"), h))
        wanted += list(extra)
        missing = [w for w in wanted if not _registered(tgt, *w)]
        kept, twice = _without(tgt, {("hook", n) for n in drop})
        if not missing and not twice:
            return "unchanged", None
        prop = _merge(kept, missing)
        rel = ".claude/settings.proposed.json"
        body = json.dumps(prop, indent=2) + "\n"
        if _read(self.target / rel) != body:
            self.w.write(rel, body, commit=False)
        why = []
        if missing:
            why.append(f"settings.json lacks {len(missing)} registration(s)")
        if twice:
            why.append(f"settings.json registers {', '.join(twice)} per repo, which user scope also runs, so "
                       "it runs twice: the proposal leaves that registration out")
        return "needs-jacob", "; ".join(why) + f"; apply with: cp {rel} .claude/settings.json"

    def c_todo(self):
        c = self.comp["todo"]
        if (self.target / c["file"]).exists():
            return Result("todo", "unchanged", f"{c['file']} present")
        self.w.write(c["file"], _fill((TOOL_ROOT / c["template"]).read_text(), {"name": self.name}))
        return Result("todo", "installed", f"{c['file']} with the four standard headings")

    def c_check(self):
        c = self.comp["check"]
        f = self.target / c["file"]
        text = _read(f)
        if text is None:
            self.w.write(c["file"], (TOOL_ROOT / c["template"]).read_text(), mode=0o755)
            return Result("check", "installed", f"./{c['file']} stub that fails until the owner fills in the contract")
        if c["stub_marker"] in text:
            return Result("check", "needs-owner", f"./{c['file']} check is still the unfilled stub: fill in the contract")
        if not os.access(f, os.X_OK):
            return Result("check", "drift", f"./{c['file']} is not executable")
        if subprocess.run(["bash", "-n", str(f)], capture_output=True).returncode != 0:
            return Result("check", "drift", f"./{c['file']} does not parse")
        return Result("check", "unchanged", f"./{c['file']} present, executable, parses")

    def c_ignore(self):
        c = self.comp["ignore"]
        res = self._ignore_lines(c)
        if self.is_new:  # nothing tracked yet (and no repo at all in a dry run)
            return res
        tracked, err = _tracked_but_covered(self.target, [e["line"] for e in c["entries"]])
        if err:
            return Result("ignore", "failed", f"git ls-files: {err}")
        if not tracked:
            return res
        return Result("ignore", worst([res.status, "drift"]),
                      f"{', '.join(tracked)} tracked though a baseline line ignores it: a .gitignore cannot "
                      "untrack a committed file, and setup never does; `git rm --cached <path>` is the "
                      f"owner's call; {res.detail}")

    def _ignore_lines(self, c):
        entries = c["entries"]
        text = _read(self.target / c["file"])
        if text is None:
            self.w.write(c["file"], "\n".join([c["header"], *(e["line"] for e in entries)]) + "\n")
            return Result("ignore", "installed", f"{c['file']} with {len(entries)} baseline entries")
        seen, err = _ignored_by(self.target, [e["probe"] for e in entries])
        if err:
            return Result("ignore", "failed", f"git check-ignore: {err}")
        negated, missing = [], []
        for e in entries:
            src, pattern = seen.get(e["probe"], (None, None))
            if pattern is not None and pattern.startswith("!"):
                negated.append(f"{src} {pattern} un-ignores {e['probe']}")
            elif pattern is None:
                missing.append(e["line"])
        if negated:
            return Result("ignore", "drift", "; ".join(negated) + ": not changed (the owner's call)")
        if not missing:
            return Result("ignore", "unchanged", f"{c['file']} ignores every baseline entry")
        sep = "" if text == "" or text.endswith("\n") else "\n"
        new = text + sep + "\n".join(missing) + "\n"
        blocked, err = _overridden_negations(text, new)
        if err:
            return Result("ignore", "failed", f"git check-ignore: {err}")
        if blocked:
            return Result("ignore", "drift", f"{c['file']} lacks {', '.join(missing)}, but " + "; ".join(blocked)
                          + ": not changed, add them where they belong")
        self.w.write(c["file"], new)
        did = "would append" if self.dry_run else "appended"
        return Result("ignore", "installed", f"{did} {', '.join(missing)} to {c['file']}; existing lines untouched")

    def c_remote(self):
        r = _git(["remote", "get-url", "origin"], self.target) if self.target.exists() else None
        if r is not None and r.returncode == 0:
            self.repo_slug = _slug(r.stdout.strip())
            return Result("remote", "unchanged", f"origin {r.stdout.strip()}")
        if not self.github:
            return Result("remote", "none", "no origin; --github creates a public repo (--private on request)")
        owner = self.owner or self._gh_login()
        if not owner:
            return Result("remote", "failed", "no --owner given and `gh api user` did not answer")
        slug = f"{owner}/{self.name}"
        vis = "private" if self.private else "public"
        if self.dry_run:
            self.repo_slug = slug
            return Result("remote", "installed", f"would create github.com/{slug} ({vis}) and push")
        if _git(["rev-parse", "--verify", "-q", "HEAD"], self.target).returncode != 0:
            return Result("remote", "failed", "no commits to push; commit first, then re-run with --github")
        if subprocess.run([self.gh, "repo", "view", slug], capture_output=True).returncode == 0:
            return Result("remote", "failed", f"github.com/{slug} already exists; setup never pushes into an existing repo")
        err = self.w.create_github(self.gh, slug, self.private)
        if err:
            return Result("remote", "failed", err)
        return self._verify_remote(slug, vis)

    def _verify_remote(self, slug, vis):
        """Check the reported result, not the exit code: origin, the pushed sha, the visibility."""
        branch = _git(["branch", "--show-current"], self.target).stdout.strip()
        head = _git(["rev-parse", "HEAD"], self.target).stdout.strip()
        if _git(["remote", "get-url", "origin"], self.target).returncode != 0:
            return Result("remote", "failed", f"gh reported success but no origin is set (github.com/{slug})")
        ls = _git(["ls-remote", "origin", f"refs/heads/{branch}"], self.target).stdout.split()
        if not ls or ls[0] != head:
            return Result("remote", "failed", f"origin/{branch} is {ls[0][:7] if ls else 'absent'}, local HEAD {head[:7]}")
        got = subprocess.run([self.gh, "repo", "view", slug, "--json", "visibility", "--jq", ".visibility"],
                             capture_output=True, text=True).stdout.strip().lower()
        if got != vis:
            return Result("remote", "failed", f"github.com/{slug} is {got or 'unknown'}, asked for {vis}")
        self.repo_slug = slug
        return Result("remote", "installed", f"created github.com/{slug} ({vis}), pushed {branch} {head[:7]}")

    def c_agent(self):
        c = self.comp["agent"]
        if self.repo_slug:
            repo = f"github.com/{self.repo_slug}"
        elif self.target.exists() and _toplevel(self.target) == self.target:
            repo = "local, no remote yet"  # the roster's wording for a repo with no origin
        else:
            repo = "none yet"  # no repo at all (a dry run on a new folder)
        d = roster_dir(self.target, self.dir_base)
        # a field built from dir has no value when dir has none: null, never the path as typed
        values = {"name": self.name, "dir": d or "", "repo": repo}
        entry = {k: None if d is None and "{dir}" in v else _fill(v, values)
                 for k, v in c["entry"].items()}
        why = "" if d is not None else (
            f"{self.target} is not under {self.dir_base.resolve()}, so dir is null: re-run from the folder "
            "the roster's dirs are relative to, or pass --relative-to it; ")
        return Result("agent", "needs-" + c["needs"],
                      f"setup cannot see the roster; {why}add if absent: " + json.dumps(entry))

    def c_server(self):
        c = self.comp["server"]
        return Result("server", "needs-" + c["needs"], "no entry shape is defined yet (group servers are not built)")

    # ---- runner -----------------------------------------------------------

    def run(self):
        """Run every declared component in order. Raises Refused before any write."""
        self.is_new, self._existed_empty = preflight(self.target)
        results = []
        for c in self.spec["components"]:
            res = getattr(self, "c_" + c["name"])()
            results.append(res)
            if c["name"] == "repo" and res.status == "failed":
                break
        return results

    def c_commit(self):
        if not self.is_new:
            return Result("commit", "none", "an existing repo: setup never commits there, its owner does")
        if self.dry_run:
            n = sum(1 for _, keep in self.w.written if keep)
            return Result("commit", "installed", f"would commit the {n} file(s) setup wrote")
        err = self.w.commit_scaffold(f"setup: scaffold {self.name}")
        if err:
            return Result("commit", "failed", err)
        sha = _git(["rev-parse", "--short", "HEAD"], self.target).stdout.strip()
        n = sum(1 for _, keep in self.w.written if keep)
        return Result("commit", "installed", f"{sha} with exactly the {n} file(s) setup wrote")

    def _gh_login(self):
        r = subprocess.run([self.gh, "api", "user", "--jq", ".login"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None


def _script(command: str):
    m = re.search(r"\.claude/hooks/([^\s/]+)", command)
    return m.group(1) if m else None


def _ignored_by(repo: Path, probes):
    """{probe: (source:line, pattern)} for each probe the repo's OWN ignore files decide
    (the global excludes file and .git/info/exclude do not travel with a clone, so
    they do not count). A negation's pattern keeps its leading '!'. Returns (map, error)."""
    r = _git(["-c", "core.excludesFile=/dev/null", "check-ignore", "-v", "-n", "--no-index",
              "--", *probes], repo)
    if r.returncode not in (0, 1):
        return {}, r.stderr.strip() or f"exit {r.returncode}"
    out = {}
    for line in r.stdout.splitlines():
        info, _, path = line.partition("\t")
        src, _, rest = info.partition(":")
        num, _, pattern = rest.partition(":")
        if src and not src.startswith(".git/") and not Path(src).is_absolute():
            out[path] = (f"{src}:{num}", pattern)
    return out, None


GLOB = re.compile(r"[*?\[\\]")


def _overridden_negations(old: str, new: str):
    """Why appending turns `old` into `new` would undo a negation, as sentences ([] when
    it would not). Only the root .gitignore's negations count: a deeper .gitignore
    outranks the root, so a root append cannot override it. Each literal negation
    !B is tested by git itself on B as a file and as a folder: a path B the negation
    keeps before the append and an appended line ignores after it is overridden. A
    negation with a pattern in it (* ? [, an escape, or a '..') names no single path
    to test, so it blocks the append with that reason rather than a guess. Returns
    (sentences, error)."""
    lines = old.splitlines()
    blocked, probes = [], []
    for n, ln in enumerate(lines, 1):
        if not ln.startswith("!"):
            continue
        body = ln[1:].rstrip(" ")
        if not body.strip("/") or GLOB.search(body) or ".." in body.split("/"):
            blocked.append(f"{ln} (.gitignore:{n}) is a pattern, so whether an appended line re-ignores what "
                           "it keeps cannot be tested without guessing")
            continue
        probes.append(body.strip("/"))
    probes = list(dict.fromkeys(probes))
    for as_folders, suffix in ((False, ""), (True, "/")):
        if not probes:
            break
        verdicts, err = ignore_verdicts([old, new], probes, as_folders)
        if err:
            return [], err
        before, after = verdicts
        for q in probes:
            bn, bp = before.get(q, (0, ""))
            an, ap = after.get(q, (0, ""))
            if bp.startswith("!") and an > len(lines) and not ap.startswith("!"):
                blocked.append(f"{ap} would re-ignore {q}{suffix}, which {bp} (.gitignore:{bn}) keeps")
    return blocked, None


def _tracked_but_covered(repo: Path, lines):
    """Committed files a baseline line matches, minus those the repo's own ignore
    files deliberately keep (their last match is a negation). Matching is git's own
    (`ls-files -i -x`, the lines alone), so it is by meaning. Returns (paths, error)."""
    args = ["-c", "core.excludesFile=/dev/null", "ls-files", "-z", "--cached", "--ignored"]
    for ln in lines:
        args += ["-x", ln]
    r = _git(args, repo)
    if r.returncode != 0:
        return [], r.stderr.strip() or f"exit {r.returncode}"
    paths = [p for p in r.stdout.split("\0") if p]
    if not paths:
        return [], None
    seen, err = _ignored_by(repo, paths)
    if err:
        return [], err
    return [p for p in paths if not seen.get(p, (None, ""))[1].startswith("!")], None


_PROJECT_DIR = re.compile(r'^\s*"?\$(?:CLAUDE_PROJECT_DIR|\{CLAUDE_PROJECT_DIR\})"?/')


def _key(command: str):
    """What a registered command runs, by meaning: a shared hook by its name under
    .claude/hooks, anything else by its path from the project dir, quoting and the
    ${} form aside. None for an empty command."""
    script = _script(command)
    if script is not None:
        return ("hook", script)
    rest = _PROJECT_DIR.sub("", command or "", count=1).split()
    return ("path", rest[0].strip("\"'")) if rest else None


def _applies(applies_to, rel):
    """Does a plug-in apply at rel (the target relative to the registry's root, None
    when outside it)? "yes", "no", "roles" (setup cannot resolve a role) or "unknown"
    (a value outside the declaration vocabulary: never guessed)."""
    if not isinstance(applies_to, str):
        return "unknown"
    if applies_to == "all":
        return "yes" if rel is not None else "no"
    kind, _, names = applies_to.partition(":")
    items = [n for n in names.split(",") if n]
    if not items or kind not in ("repos", "roles"):
        return "unknown"
    if kind == "roles":
        return "roles"
    return "yes" if rel is not None and rel in {Path(n).as_posix() for n in items} else "no"


def _registered(tgt, event, matcher, hook):
    key = _key(hook.get("command", ""))
    for g in (tgt.get("hooks") or {}).get(event, []):
        if g.get("matcher") != matcher:
            continue
        if any(_key(h.get("command", "")) == key for h in g.get("hooks", [])):
            return True
    return False


def _tristate(v):
    return v is True or v is False or v is None


def _user_scope_shape(rep):
    """(user_scope, None) when the report carries one in the shape read here, else
    (None, why). The same fields the shared checks require of it, so a report one
    trusts the other does too."""
    us = rep.get("user_scope") if isinstance(rep, dict) else None
    if not isinstance(us, dict):
        return None, "no `user_scope` object"
    for key in ("exists", "error", "hooks"):
        if key not in us:
            return None, f"`user_scope` has no `{key}`"
    if not isinstance(us["exists"], bool):
        return None, "`user_scope.exists` is not true/false"
    if us["error"] is not None and not isinstance(us["error"], str):
        return None, "`user_scope.error` is neither null nor text"
    if not isinstance(us["hooks"], list):
        return None, "`user_scope.hooks` is not a list"
    for h in us["hooks"]:
        if not (isinstance(h, dict) and isinstance(h.get("file"), str) and isinstance(h.get("kind"), str)
                and "registered" in h and _tristate(h["registered"])
                and isinstance(h.get("test"), (str, type(None)))):
            return None, "a `user_scope.hooks` row is not {file, kind, test?, registered: true|false|null}"
    return us, None


def _coverage(us, rel):
    """(True | False | None, why): do the user settings run the shared hook the copy
    at rel stands for (rel is the hook, or the test of one)? The shared checks'
    rule, read from the same report: covered only when every `kind: source` row
    naming it is `registered: true`; any false is not covered; otherwise (null, or a
    `user_scope.error`) unknown, which is never covered. No user settings file: not
    covered, never an error."""
    if not us["exists"]:
        return False, "no user settings file"
    if us["error"] is not None:
        return None, us["error"]
    rows = [h for h in us["hooks"] if h["kind"] == "source" and rel in (h["file"], h.get("test"))]
    if not rows:
        return False, "no shared hook of that name there"
    regs = [h["registered"] for h in rows]
    if all(r is True for r in regs):
        return True, ""
    if any(r is False for r in regs):
        return False, "not registered there"
    return None, "registered: null"


def _without(tgt, keys):
    """(tgt minus every registration whose command runs one of `keys` (by _key), the
    names of what was left out). An emptied group or event goes too."""
    out = copy.deepcopy(tgt)
    gone = []
    hooks = out.get("hooks")
    if not keys or not isinstance(hooks, dict):
        return out, gone
    for event in list(hooks):
        groups = []
        for g in hooks[event]:
            keep = []
            for h in g.get("hooks", []):
                k = _key(h.get("command", ""))
                if k in keys:
                    gone.append(k[1])
                else:
                    keep.append(h)
            if keep or not g.get("hooks"):
                groups.append({**g, "hooks": keep} if "hooks" in g else g)
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    return out, list(dict.fromkeys(gone))


def _merge(tgt, missing):
    out = copy.deepcopy(tgt)
    hooks = out.setdefault("hooks", {})
    for event, matcher, hook in missing:
        groups = hooks.setdefault(event, [])
        group = next((g for g in groups if g.get("matcher") == matcher), None)
        if group is None:
            group = {"matcher": matcher, "hooks": []} if matcher is not None else {"hooks": []}
            groups.append(group)
        group.setdefault("hooks", []).append(copy.deepcopy(hook))
    return out


def _slug(url: str):
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return m.group(1) if m else None
