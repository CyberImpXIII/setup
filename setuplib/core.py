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

from .fsw import Writer

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


def worst(statuses):
    return min(statuses, key=PRECEDENCE.index)


class Setup:
    def __init__(self, target: Path, *, label: str, name: str, dry_run: bool,
                 github: bool = False, private: bool = False, owner=None,
                 hooks_from=None, gh: str = "gh", spec=None):
        self.target = target
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
        self.w = Writer(target, dry_run)
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
        statuses, notes = [], []
        n_new = n_same = 0
        for s in srcs:
            rel = f".claude/hooks/{s.name}"
            dst = self.target / rel
            if not dst.exists():
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
        st, note = self._settings([s.name for s in srcs])
        statuses.append(st)
        if note:
            notes.append(note)
        head = f"{n_new} installed, {n_same} unchanged of {len(srcs)}"
        return Result("hooks", worst(statuses), "; ".join([head, *notes]))

    def _settings(self, names):
        """Registrations the source settings.json makes for these hooks, against the target's."""
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
        missing = [w for w in wanted if not _registered(tgt, *w)]
        if not missing:
            return "unchanged", None
        prop = _merge(tgt, missing)
        rel = ".claude/settings.proposed.json"
        body = json.dumps(prop, indent=2) + "\n"
        if _read(self.target / rel) != body:
            self.w.write(rel, body, commit=False)
        return "needs-jacob", (f"settings.json lacks {len(missing)} registration(s); "
                               f"apply with: cp {rel} .claude/settings.json")

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
        repo = f"github.com/{self.repo_slug}" if self.repo_slug else "none yet"
        entry = {k: _fill(v, {"name": self.name, "dir": self.label, "repo": repo})
                 for k, v in c["entry"].items()}
        return Result("agent", "needs-" + c["needs"],
                      "setup cannot see the roster; add if absent: " + json.dumps(entry))

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


def _registered(tgt, event, matcher, hook):
    script = _script(hook.get("command", ""))
    for g in (tgt.get("hooks") or {}).get(event, []):
        if g.get("matcher") != matcher:
            continue
        if any(_script(h.get("command", "")) == script for h in g.get("hooks", [])):
            return True
    return False


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
