# setup

Brings one git repo (or a new folder) to the shared baseline, from its path
alone: the shared-rules block of `CLAUDE.md`, the shared hooks and a settings
proposal (in a repo setup creates, `settings.json` itself, committed), `TODO.md`, a `./dev.sh check` stub that fails until it is filled in,
a baseline `.gitignore` (the proposal, local env files, backups: in an existing
one only what git does not already ignore is appended; a negation of an entry,
an append that would re-ignore what a negation keeps, and a committed file an
entry covers are drift), and on request a GitHub repo. Spec: `PLAN-repo-setup.md` §2 one level up from
`tools/`, minus the `agent` and `server` components, which belong to the
delegation layer: setup prints "needs harness" and the line to add instead.

**Content-agnostic.** Nothing here knows what a target repo does or names one.
What gets installed is data (`components.json`, `templates/`); `./dev.sh audit`
fails if setup's code, data or templates name a repo, a repo path or a repo
command, or read the delegation layer.

| doing this | use |
|---|---|
| set a repo up, or see its drift | `./setup <path> [--dry-run]`; run it from the folder the roster's `dir` is relative to, or pass `--relative-to DIR` (the agent line's `dir` is null when `<path>` is not under it) |
| where the shared hooks come from (PLAN-repo-setup §7.12) | `dependencies.json` names the sibling tools setup installs FROM (tools/hooks, tools/checks): the hooks component runs the hooks dependency's `list --json --source <its source>` and renders every file it names (hooks, their tests, the libraries), compared by that tool's one comparator (`hookslib.copies.meaning`, imported from where the dependency resolved, refused if found elsewhere). Absent: `installed`; equal by meaning: rewritten, "header refreshed"; logic differs: `drift`, byte-unchanged unless `--rebuild` (next row). Each file that differed gets a line: `hooks <action> <file> (<kind>)` (`hook_files` in `--json`; vocabulary in `setup components`). `--hooks-from DIR` overrides the source; without the dependency it is DIR's `hooks/*.sh`, byte for byte. `setup audit deps` gates the file: each dependency a discovered repo, its CLI executable, its source a folder; nothing discovered is UNCHECKED (exit 3). The file is exempt from `audit content` only (`tests/test_deps.py`) |
| replace hook copies whose logic drifted from the source (§7.12, Jacob's yes 2026-10-05) | `./setup <repo> --only hooks --rebuild` (the per-repo line; without `--only` the other components run as usual). In any repo, created by setup or not: a copy the listing renders into a folder directly under `.claude/` (the hooks, `.claude/hooks/`, and their libraries, `.claude/lib/`) is overwritten from the source, its line `rewritten (logic)` (or `bytes` without the dependency, `mode` when only the executable bit differed); nothing else is ever overwritten (components.json `hooks.rebuild.scope_root`; `tests/test_rebuild.py` holds every listed file inside it). **Refused, exit 2, nothing written** while such a copy differs from the source and holds changes git does not (staged, unstaged, untracked or ignored); `--overwrite-uncommitted` lifts that. Setup never commits there: the owner reviews `git diff` and commits. `--dry-run` shows the lines. `tests/test_rebuild.py` |
| the shared suite runner (PLAN-small-tasks §7 step 2) | the `parts` component renders the checks dependency's `runner` (dependencies.json: `checkslib/parts.py`) byte for byte to `devtools/parts.py` (components.json `parts.file`), so a repo's `dev.sh check` can hand its parts to it. Compared by meaning with `setuplib/pymeaning.py` (the Python syntax tree, docstrings included: the runner's usage is its docstring; comments and layout aside): absent `installed`, byte-equal `unchanged`, equal by meaning rewritten ("header refreshed"), otherwise `drift` (the line names both versions), byte-unchanged unless `--rebuild` (`./setup <repo> --only parts --rebuild`; refused while the copy holds changes git does not, as for hooks). The dependency's own repo gets none (it runs the source); a lone clone fails. The copy is out of both audits' scope, like the hook copies. This repo's own copy agreeing with the source is `tests/test_parts_component.py` (`ThisRepo`) and the `self` gate. In the node `render` list, so a node scaffold's copy regenerates byte for byte under `--node --rebuild` (a rebuild's render stands for the real path: the source repo gets none there either) |
| also propose the plug-in hooks that apply | `--plugins FILE`: the JSON tools/hooks' `./hooks plugins --json` prints (a plug-in runs in place from its owner's repo, never copied); one whose registration would run from below the registry's root fails rather than guess |
| skip the shared hooks user scope already runs | `--user-scope FILE`: the JSON tools/hooks' `./hooks copies <top> --json` prints; only its `user_scope` is read (never the user settings). A hook every `kind: source` row of which is `registered: true` is not copied and not registered per repo in the proposal (it would run twice); the line says `covered by user scope: <files>`. `null`, an `error`, or no user settings file: not covered, behaviour unchanged. The rule is tools/checks' `hooks-installed` rule, mirrored (setup may not import a sibling tool); an existing copy is never deleted |
| also create the GitHub repo | `--github` (public by default), `--private` on request, `--owner O` |
| set up a node and its children | `--node`: reads `<path>/node.json` (the shared checks' shape: `rebuild`, `generated`, `record`, `children`, `registry`; `setuplib/node.py` mirrors their schema, `tests/test_node.py`'s live tests hold the two readings together). Each child is set up in turn, created as a repo nested in the node when absent (never `--github`); one with its own node.json recurses |
| re-render a node's generated files | `--node --rebuild` (PLAN-repo-setup §7.10): renders the baseline afresh in a throwaway folder for this path and name, writes each generated file over the tree's copy, and prints one line per file: `regenerated`, `drift` (written: `git diff` is the finding), `record`, `unaccounted`, `failed`. Only `failed` exits 1; the zero-drift gate is the shared checks' `regenerate`, which runs this in a clone. **Run it on fixtures and scratch copies, not the real top level**; `--dry-run` writes nothing |
| the contract files (PLAN-routing-tree §14.8) | every run: `services.json` (the skeleton: the name and its `check` entry) and `checks.json` (the baseline: no parameter set) when absent, an existing one the owner's; `cli.json` never (no skeleton passes its schema: the owner writes it with the store). In a node run, once the children are set up, `registry.proposed.json`: the union of the services.json files under the node, for Jacob to copy to the registry node.json names (gitignored, like the settings proposal; only `services` is rendered) |
| run the shared checks as setup's last step | `--checks CLI` (no default: setup names no sibling): after everything is rendered, `CLI list`, `CLI run <path>`, then `CLI one <gate> <path>` for each contract gate in components.json `gates.contract` that `run` left out (one gated to a role), in sequence. A fail is `drift`, an error or a fault `failed`, unchecked named; a contract gate the CLI lacks or that reports nothing fails the line. Children run their own. Never in a dry run or a rebuild. `tests/test_contract.py` holds it to the real CLI (live) and to `tests/fake_checks.py` |
| generate a store from the data repo (PLAN-repo-setup §7.11) | the `data` component: when `cli.json` declares `import` and `verify` and nothing its `store` names is on disk, `<cli> import` then `<cli> verify --json` in the repo, with `DATA_REPO` (`--data-repo DIR`, else the environment; setup reads no instance file) passed through; the tool picks `$DATA_REPO/<its folder>/`. `installed` only when the store is on disk afterwards and every verified item is `same`; differs/missing, no report, or a non-zero exit over all `same` is `failed`; `unavailable` is needs-jacob, never a pass. An existing store is never dropped (part of one: needs-owner); DATA_REPO unset or not a folder: needs-jacob, nothing run; a cli or store path outside the repo: drift, nothing run. The import goes through `Writer.run_repo_cli`. Children get the same DATA_REPO. `tests/test_data.py` (fake: `tests/fake_store.py`; live: accessor and stores-exported) |
| the git-side gates (PLAN-hard-gates §7 phase 2) | the `githooks` component: `.githooks/commit-msg` (a session's commit must carry `Agent:`, never `Agent: jacob`; one outside a session is stamped `Agent: jacob`; every commit gets `check: full / resumed from K/N / none`), `.githooks/pre-commit` (the staged tree is the one `./dev.sh check` passed on, and `checks one no-secrets` is ok) and `.githooks/check-pass` (the one recorder and matcher; a repo's check runs `check-pass tree` first and `check-pass record --from TREE` when green, as this repo's dev.sh does). `--checks CLI` is kept in the clone's git config `githooks.checks`. core.hooksPath is set only when nothing would be refused for want of wiring, never in a new repo, never over another one. Where core.hooksPath already names `.githooks` (set by the repo's owner), the hooks git runs (components.json `runs`) are withheld, not written, while anything is unready (git-stamp unregistered: needs-jacob), so setup's own output stays committable. `tests/test_githooks.py` |
| one component alone (e.g. only the hook copies) | `./setup <path> --only <component>`: an existing repo only (a new folder is refused), never with `--node`. `tests/test_only.py` |
| what each component does, and the statuses | `./setup components` |
| check a folder of plans | `./setup plans <dir>`: also each section status marker (`<!-- status: open\|approved\|done -->` on the first line under a numbered heading; none is unstated) and no section number carried twice; the ok line, last, counts the sections by status |
| one plan section, by number (PLAN-todo-tool §9 step 6) | `./setup plans show <file> §<n>`: stdout is the section exactly, stderr `digest <sha256>`; `./setup plans list <dir> [--all]` lists the sections not done (`setuplib/plans.py`, `tests/test_plans.py`) |
| replace one plan section (PLAN-services §3) | `./setup plans edit <file> §<n> --from <src> --digest <sha256>`: refused unless the file still has the digest `show` printed, the folder's `setup plans` is green before and would stay green after, and `<src>` is that one section; every byte outside it is kept; written through fsw.py |
| before committing | `./dev.sh check` (tests, hooks, files, audits, self, mutants) |
| the check as JSON | `./dev.sh check --json`: the one schema every repo prints (tools/checks holds it), one check per gate, each finding line a failure (`devtools/checkjson.py`); the stub setup installs prints its red report. Proven by fixtures here and, in the workspace, by the real validator (`tests/test_checkjson.py`); no copy of the schema lives here |
| what is open | `TODO.md` |

**What setup never does:** write to a path it refused (a non-empty folder that is
not a repo, a subfolder of a repo, a new repo nested in a work tree unless that
tree's node.json declares it a child, a missing parent); overwrite something that
differs (that is `drift`, reported), with three exceptions: `--node --rebuild`
writes a generated file's render over a committed copy so `git diff` shows the
drift, and never writes a record or a generated file with uncommitted changes;
`--rebuild` without `--node` overwrites a hook copy whose logic drifted from the
source, in any repo, but only a file the hooks listing renders under
`.claude/hooks/` or `.claude/lib/` (never `settings.json`, never a repo's own
`.githooks/pre-commit`, never anything setup does not render), and likewise the
runner copy `devtools/parts.py`, and refuses the
whole run while one of those copies holds changes git does not, unless
`--overwrite-uncommitted` (with `--only`, only that component's copies are read); and a hook or runner copy equal to its source by meaning is
rewritten as "header refreshed" in every run, which by construction changes no
logic. Never touch an
existing repo's `settings.json` (it writes `settings.proposed.json` and prints the
copy command), including on a later run in a repo it created; commit in a repo it
did not create; push into a GitHub repo that already exists.
Every write goes through `setuplib/fsw.py`, the one place `--dry-run` is
enforced, and a test fails if any other module writes. **The one exception for
settings** (PLAN-repo-setup §7.9): in a repo it is creating, where nothing of
Jacob's exists yet, setup writes `.claude/settings.json` from the same render the
proposal would hold and puts it in the scaffold commit, with no proposal beside it
(`tests/test_settings_new.py` holds the file equal to that proposal, byte for byte).

**Statuses**, worst first: `failed`, `drift` (both exit 1), `needs-jacob`,
`needs-owner`, `needs-harness`, `installed`, `none`, `unchanged`. A refused path
exits 2. `--dry-run` reports `installed` for what it would write.

**Every gate is proven able to fail.** `devtools/mutants.json` breaks each gate
once in a throwaway copy and requires red; `./dev.sh check` runs it, and a
mutant whose code moved is STALE and fails the check until it is updated.

**A lone clone is red, on purpose.** Two gates need the workspace around this
folder: `hooks` (the shared troubleshooting hook's own test fails when it cannot
find its sibling, because the hook then enforces nothing; that test belongs to
the hooks source), `audit content` and `audit deps` (no sibling repos to compare
against: `UNCHECKED`, exit 3). The hooks component fails too unless
`--hooks-from DIR` is passed (no dependency to install from), so `test` is red as
well: every test whose fixture runs setup with the default hook source (99 of 318
on 2026-10-08, in 13 modules; TODO.md). None reads as a pass. `checks.json` holds this repo's
parameters for the shared checks runner (`no-roster`: the audit data files
excluded, as they are from this repo's own audits; `hooks`, `todo` and
`harness` allowed, being component names and the lane owner `needs harness`
prints, which the direction audit still checks phrase by phrase).

### The shared hooks

`.claude/hooks/` and `.claude/lib/` are a rendered copy like any other repo's
(PLAN-repo-setup §7.12): `./setup .` renders them from the hooks dependency
(every hook its listing names, with its test, and the libraries), and they are
no longer what setup installs from. **Never hand-edit them**; a change is made
in tools/hooks' source and re-rendered. `./dev.sh hooks` checks each is
present, executable, parses, passes its own test and is registered in
`.claude/settings.json`; one registered only in `settings.proposed.json` prints
`PENDING` (it does not run until Jacob copies the proposal: settings.json is
his) and one in neither is FAIL. That they agree with the source by meaning is
`tests.test_hooks` (`hooks copies --gate`) and the hooks tool's own check.

<!-- shared:rules@7867132c3871 -->
## Shared rules

This block is installed by the setup tool from its template. **Do not edit it
here:** setup reports an edit inside the markers as `edited locally` and will not
overwrite it. Change the template in the setup tool, then re-run setup in each
repo. A rule that belongs to this repo alone goes outside the markers.

## Never write an inline script blob — ENFORCED, not advised

A `PreToolUse` hook (`.claude/hooks/no-inline-blobs.sh`) blocks `python3 -c`,
`node -e` and heredocs feeding an interpreter.

| what you are doing | where it goes |
|---|---|
| a read or check you will repeat | a `./dev.sh` subcommand |
| anything touching stored data | that tool's own CLI — never raw SQL |
| a genuine one-off | a script file, then run the file |

Second time you type something, it becomes a subcommand. Don't ask.

## Wall clock is not a cost — tokens are

**Cost here means tokens and AI usage. Nothing else.** This machine is powerful and loads many pages at once. If something takes a while but is purely Puppeteer — headless, in a subprocess, returning a small result — it is **not expensive**, and "it takes a minute" is not an argument against it.

The distinction is that the page never enters anyone's context. A browser loads it, a few hundred bytes of JSON come back, and the model reads those. A run that takes 60 seconds and returns 400 bytes is cheaper than one that takes 2 seconds and returns 40KB.

So: **do not optimise for speed, do not batch to save seconds, do not skip a measurement because it is slow.** Prefer the thorough run. Spend wall clock freely to avoid a second round trip through the model, which is the thing that actually costs.

What DOES still count: output size, because it lands in context — and anything that would provoke a site into blocking us. When in doubt about whether a cost is real, ask whether a token is spent on it.

## Keep an active TODO

**Jacob's rule, and it belongs in every copy of these rules.** Every repo here
keeps a `TODO.md`, and every agent keeps it current. An issue you noticed and
neither fixed, reported, nor wrote down is **lost when the session ends** — and
the next session pays to rediscover it.

It holds four things:

- **your own bugs** — including the ones you caused and worked around
- **open decisions**, with what each one hinges on
- **unconfirmed suspicions, labelled as such**, naming the probe that would
  settle them. A suspicion worth having is worth recording before it is proven
- **what you reported to another owner**, so the next session doesn't report it
  again, and so a stalled report is visible rather than assumed handled

**Add items when you notice them, not at the end of the session** — the end is
exactly when context runs out. Delete them when they are done; a TODO nobody
trims stops being read.

A finding recorded with its evidence is worth more than one recorded as a
worry: say what you ran, what you saw, and what you concluded.

## Report a problem in someone else's code to whoever owns it

**Jacob's directive, and it belongs in every copy of these rules — like the
hooks.** When you find a bug, a wrong result, a status that overstates what
works, or a missing guard in code another agent owns, **tell that agent.** Do
not fix it silently, do not route around it, and do not leave it to be
rediscovered.

- `ListAgents` to find the owner, `SendMessage` to report it. Say what you
  observed, the exact input or parameters, what you expected, and what you did
  on your own side in the meantime. A session without those tools (a dispatched
  agent, a cloud run) puts the report in its final message and in `TODO.md`.
- **Both alternatives cost more.** Fixing it yourself clobbers their work and
  skips the checks their repo has for a reason. Routing around it hides a
  fixable fault behind a workaround, and the next consumer pays for it again.
- **Report the unconfirmed findings too**, labelled as such, naming the probe
  you ran — so the owner can tell evidence from inference.
- If nobody owns it, or the owner is unresponsive, say so to Jacob rather than
  quietly absorbing the problem.

## Gate the seams — STANDING DIRECTIVE

**Any change that creates an interface gates it in the same change** — a gate, a test, or an audit. If you cannot see how to check something, say so rather than leaving it unchecked and unmentioned.

The gap is never in the feature; it is in the seam between two things that each work. Recorded because each of these was live and invisible in this folder: four copies of a hook kept in step by a comment; two hooks installed in 2 of 4 tool folders, so a rule applied depending on which directory a session started in; both resolving a sibling repo by a fixed `../..`, so elsewhere they exited 0 and enforced nothing *while still looking installed*; every hook header promising "fails open" with nothing testing it; a `usage()` on a hardcoded line range, bumped wrong three times, truncating its own help while the tool kept working.

**A guard that is present, reports no error, and does not run is the worst state available, because you stop looking.**

If your change adds one of these, check it in the same change: a second copy of anything (do the copies agree, by *meaning* not bytes); a file something needs to work (present, executable, parses); a documented list (documented == implemented, both directions); a vocabulary code consumes (every key consumed, every consumed key present); an accessor meant to be the only way in (audit that nothing bypasses it); a fallback or fail-open path (test the failure, not the success); a promise in a comment (check it, or delete the promise).

## Make the wrong thing impossible, not discouraged

A constraint that lives only in a document is an intention; one enforced by code
is a constraint.

**Keep new work to that standard.** If you find yourself relying on future-you
to be careful, that is the signal to write a guard instead.

## A wrong answer is worse than a failure

Most of the expensive bugs in this folder produced *plausible* output rather than an error: a salary string reported as a location, a search filter that never filtered, a parameter that changed nothing, an `href` pointing at a company page while being read as a job link. Each one was confidently wrong and therefore invisible.

- **Prefer `null` over a guess.** If a value can't be found, say so.
- **Prove a feature does something.** Anything that accepts an input and might ignore it needs a test that the input *changes the output*. "It ran without erroring" is not evidence.
- **A claim is earned, never asserted.** Don't mark something working, verified or done because you believe it is — make it provable by a run, and let the run set it.
- **Check the reported result, not the exit code.** A process can exit 0 having done nothing, and can exit non-zero while carrying the data you wanted.
- **Verify counterfactuals.** Before concluding X caused Y, check that Y doesn't happen without X. Several long investigations here ended with a cause that was never tested against its own negation.

## Don't duplicate procedure — the unique thing is the data

When two things do the same work against different inputs, the work belongs in one parameterised place and the inputs stay separate. A near-duplicate that drifts is harder to find than a missing feature, and both copies look correct in isolation.

If an existing helper *almost* fits, add a parameter to it rather than forking it. If a literal inside shared code belongs to one caller's domain, it is a parameter with a documented default — not a constant.

## Parallelism: structured, and never silent about what failed

- **Use promise combinators, not ad-hoc concurrency.** Fire-and-forget promises, or a loop that starts work without awaiting it, lose both ordering and failures. Everything concurrent goes through `Promise.all` / `Promise.allSettled` (or the language equivalent) so there is one place that knows what was started and what came back.
- **Prefer `Promise.allSettled` when troubleshooting.** `Promise.all` rejects on the *first* failure and throws away every other result, including the ones that succeeded — which is exactly the comparative information you need when working out why something broke. Reach for `Promise.all` only when fail-fast is genuinely what you want (a later step can't run without all the earlier ones).
- **Report per-branch outcomes, never just the first error.** When N things run in parallel, say which succeeded and which failed, and for the failures, where. A summary that surfaces one exception and drops the rest hides the pattern — "3 of 12 failed, all on the same step" is the finding; "one thing threw" isn't.
- **Prefer parallelising across processes over inside one.** Module-level state (progress trackers, caches, counters) is written on the assumption that one job runs per process. Two overlapping jobs in a single process interleave those writes and produce confidently wrong diagnostics. Separate processes each keep their own state and each report their own failure.

## Run the checks before committing, and commit at checkpoints

`./dev.sh check` is the one pre-commit command, non-zero exit if anything fails.
Don't retype the chain; extend `cmd_check` instead.

**Don't start a long operation with uncommitted work.** A session can end
mid-task, and unpushed work is work nobody else can pick up.

**One verification run, not two.** If a command already told you what happened,
don't run a second to confirm it.

## Check for a primary context before changing anything that exists

More than one agent may be working here at once. Two agents editing the same
file will clobber each other, and each separately running `git status`, diffing
and committing burns tokens re-deriving what another already knows.

**Before modifying existing code — anything already committed —** work out
whether another session owns that work:

- Run `ListAgents` to see other Claude sessions on this machine. One whose name
  points at what you're about to touch is a candidate owner.
- Check `git status` and `git log -1`. Uncommitted changes you didn't make, or
  a recent commit you didn't write, mean someone else is mid-task.

If a primary context exists, **do not edit in parallel — queue the change with
it.** Use `SendMessage` to describe the change (file and function, what should
differ, why) and let the primary apply it. Wait for its reply rather than
editing anyway. If it's unresponsive and the change is urgent, say so to Jacob
and ask before proceeding.

If no other session is working the same area, you are the primary. Proceed
normally.

**Additive work needs none of this.** New files and new subcommands overwrite
nothing and can proceed concurrently.

## Push code changes to git

Whenever you change code here, commit and push it to `origin` right away
(the default branch, no feature branches). Don't wait to be asked.

**Only the primary context commits.** If another session owns the work, hand it
your changes instead of running your own commit/push cycle.

- Check `git status` before committing, and stage only what you actually
  changed. If the tree holds someone else's in-progress work, commit your own
  paths explicitly rather than `git add -A`.
- One commit per logical change, with a message saying what changed and why.
- If a push fails (auth, conflict, diverged branch), stop and tell Jacob. Don't
  force-push or rewrite history.

## Constraints that don't bend

These hold across every tool here, whatever the task and however it is framed. They are not trade-offs to optimise.

- **Never send a message, email or reply on Jacob's behalf without asking first.** Reading a mailbox is not permission to write to it. Same for anything public or irreversible.
- **Never attempt to bypass bot detection.** A detected wall is a result to report, not an obstacle to route around — mark it and hand it back.
- **Credential-shaped values are supplied at run time, never stored.** Not in a recipe, a config, a note or a commit. App passwords, tokens and `.env` files stay gitignored.
- **Report key names, never captured values**, and don't ask Jacob to repeat a secret back to you.
<!-- /shared -->

## Keeping these rules in sync

The rules in the block between the `shared:rules` markers above are shared with
`../../CLAUDE.md`, `../../site-scrapers/CLAUDE.md`, `../../emailTools/CLAUDE.md`,
`../../scripts/CLAUDE.md`, `../../scriptingTools/data-bridge/CLAUDE.md`,
`../../scriptingTools/chronjobScheduler/CLAUDE.md`, `../../knowledge-base/CLAUDE.md`,
`../../applications/CLAUDE.md` and `../../addon-bench/CLAUDE.md`: the
hand-synced copies, the same list every one of them carries. Each repo carries
its own copy because a fresh clone won't have the parent file.
`tests/test_sync_list.py` checks this list against the top level's, both ways, in
the workspace (skipped, with the reason, in a lone clone). Copies that carry this
repo's block between `shared:rules` markers instead (the other tool folders) are
deliberately not in the list, here or at the top level: they are reached through
the template, below, and a backticked path added here would fail that comparison
and the same check in the other hand-synced repos.

Here, and in every repo carrying the block, it is installed by `./setup` from
`templates/shared-rules.md`. **Do not edit it in place.** Change
`templates/shared-rules.md`, run `./setup .`, and ask each block-carrying repo's
owner to run `./setup <their path>`; a block edited in place is reported as
`drift` (`./dev.sh self` here) and is never overwritten. The hand-synced copies
stay hand-synced until each repo moves to the block (PLAN-repo-setup phase 2):
**change a shared rule in the copies you own, and ask the owner for the ones you
don't** — and say which copies you updated and which you asked for.
