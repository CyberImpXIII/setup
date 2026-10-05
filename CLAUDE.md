# setup

Brings one git repo (or a new folder) to the shared baseline, from its path
alone: the shared-rules block of `CLAUDE.md`, the shared hooks and a settings
proposal, `TODO.md`, a `./dev.sh check` stub that fails until it is filled in,
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
| also propose the plug-in hooks that apply | `--plugins FILE`: the JSON tools/hooks' `./hooks plugins --json` prints (a plug-in runs in place from its owner's repo, never copied); one whose registration would run from below the registry's root fails rather than guess |
| also create the GitHub repo | `--github` (public by default), `--private` on request, `--owner O` |
| what each component does, and the statuses | `./setup components` |
| check a folder of plans | `./setup plans <dir>` |
| before committing | `./dev.sh check` (tests, hooks, files, audits, self, mutants) |
| what is open | `TODO.md` |

**What setup never does:** write to a path it refused (a non-empty folder that is
not a repo, a subfolder of a repo, a new repo nested in a work tree, a missing
parent); overwrite something that differs (that is `drift`, reported); touch
`settings.json` (it writes `settings.proposed.json` and prints the copy command);
commit in a repo it did not create; push into a GitHub repo that already exists.
Every write goes through `setuplib/fsw.py`, the one place `--dry-run` is
enforced, and a test fails if any other module writes.

**Statuses**, worst first: `failed`, `drift` (both exit 1), `needs-jacob`,
`needs-owner`, `needs-harness`, `installed`, `none`, `unchanged`. A refused path
exits 2. `--dry-run` reports `installed` for what it would write.

**Every gate is proven able to fail.** `devtools/mutants.json` breaks each gate
once in a throwaway copy and requires red; `./dev.sh check` runs it, and a
mutant whose code moved is STALE and fails the check until it is updated.

**A lone clone is red, on purpose.** Two gates need the workspace around this
folder: `hooks` (the shared troubleshooting hook's own test fails when it cannot
find its sibling, because the hook then enforces nothing; that test belongs to
the hooks source) and `audit content` (no sibling repos to compare against:
`UNCHECKED`, exit 3). Neither reads as a pass. `checks.json` holds this repo's
parameters for the shared checks runner (`no-roster`: the audit data files
excluded, as they are from this repo's own audits; `hooks`, `todo` and
`harness` allowed, being component names and the lane owner `needs harness`
prints, which the direction audit still checks phrase by phrase).

### The shared hooks

`.claude/hooks/` holds the three shared hooks and their tests, copied byte for
byte from tools/hooks' `source/hooks/` (the one source): they are both this
repo's own enforcement and the default source `setup` installs from, so they
lag the source until reinstalled, and the hooks line says what it compared
against. **Never hand-edit them**; a change is
made in the canonical copy and copied to all. `./dev.sh hooks` checks they are
present, executable, registered in `.claude/settings.json`, and pass their own
tests. That they equal the other copies is checked from outside, once this
folder is registered with the cross-repo hook check (TODO.md).

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
