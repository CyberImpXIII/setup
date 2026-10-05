# setup TODO

## Own bugs

- **A lone clone's `./dev.sh check` is red on `hooks`, `mutants` and `audit`.** By
  design since 2026-10-04 (CLAUDE.md, "A lone clone is red, on purpose"):
  `test-troubleshooting.sh` (a shared hook test, owned by tools/hooks: its own
  TODO.md's first bug) fails with "site-scrapers NOT FOUND above" outside the
  workspace, which also turns the `hooks-gate` mutant's baseline red; and
  `./setup audit content` now exits 3 on UNCHECKED (it exited 0 before, a gate
  that looked green while not running). The content audit is proven by the
  planted-workspace tests, which run anywhere, and the exit-3 path by
  `test_the_cli_exits_non_zero_when_it_could_not_run` and its mutant. Nothing
  left here to fix unless tools/hooks changes how its test finds its sibling.
- **The agent line's `"repo"` reads "none yet" in a dry run on a new folder**,
  though the real run would make a local repo and print "local, no remote yet".
  Deliberate: it reports the target as it is now (dispatcher's brief, 2026-10-04).

## Open decisions

- **The check component installing `checks run .` (planner: yes, PLAN-tools-folder
  §8) collides with the content audit.** Not built, 2026-10-04. The stub would
  have to name the runner's path (`tools/checks/checks`), and `./dev.sh audit
  content` fails setup on naming any discovered repo, path or command; the same
  holds for setup's own `dev.sh` adopting it. §9 (1) (the hooks component
  defaulting to `tools/hooks/source`) has the same collision. Proposal for the
  planner: one data file exempt from the content audit, like `audit-terms.json`
  is from the direction audit, naming the sibling tools setup installs FROM
  (dependencies, not targets), gated by "each named dependency is a discovered
  repo, or UNCHECKED"; setup resolves the runner relative to the target at
  install time and the stub still fails until the owner adds their suite. An
  existing repo's `dev.sh` is never edited (setup does not overwrite); at most
  it is reported `needs-owner` when its check does not call the runner.
  Hinges on: whether setup may depend on named sibling tools at all.
- **The `hooks` component reading `./hooks list --json` (tools/hooks' report) is
  PLAN-tools-folder §9 (1), which awaits Jacob's yes** (top-level TODO.md, "Jacob's
  yes needed on §9 (1), (2)"). Not built, 2026-10-04; it also needs the decision
  above. Gates it would ship with are in §9 (1).
- **td-9 (tools/todo: `devtools/mutate.py` duplicated from here), decided
  2026-10-04: the runner moves to tools/checks, not into a setup component.** A
  component would install one copy per repo, the eight-copies problem again; the
  procedure belongs in one place and each repo's `devtools/mutants.json` is the
  data. Shape: `checks mutants [PATH]` running PATH's mutants.json in throwaway
  copies, with todo's additions (the `edits` list, the read-only chmod). Then
  this repo and todo call it from `dev.sh check` and delete their copies, add
  beside then delete. Until then this copy is the original and todo's the
  extended one; neither is changed (no fork, no third copy). Needs the
  dependency decision above for setup's own `dev.sh` to call it. Reported below.
- **Hook copies here are a ninth copy.** `tools/setup` is now in site-scrapers'
  `check-hooks.sh` DECLARED (seen 2026-10-04), and `hooks copies` in tools/hooks
  compares every copy by meaning. unverified: knowledge-base's copy of that check
  declares it too -- settle (from knowledge-base): `grep -n tools/setup check-hooks.sh`.
- **`--github` is public by default** (the dispatcher's brief and PLAN-tools-folder),
  while PLAN-repo-setup §2 says private. Followed the brief; the plan text is the
  dispatcher's to update.
- **`audit-terms.json` `roster_names` is a copy of the roster** (not read from it:
  the direction audit forbids that). Probe run 2026-10-04: the roster's agent
  names that are not also repo names are exactly the seven listed (harness,
  deep-work, dispatcher, planner, email-tools, job-import-scripts,
  cron-scheduler); the rest are repo names the content audit discovers. Not stale
  today. Retire it when a caller runs tools/checks' `no-roster` here with the
  names (`checks all --names`, reported to harness by checks); `checks.json`
  already makes that run green (checked 2026-10-04 with the roster's names).
  Until then, re-run the probe on each roster change.
- **A root `.gitignore` negation with a pattern in it (`!keep*.txt`) still blocks
  the append as drift** (2026-10-04): literal negations are now tested by git in a
  scratch repo (as a file and as a folder), but a pattern names no single path, and
  a representative path would be a guess. No workspace `.gitignore` holds any
  negation today (probe: `grep -n '^!'` over them, 2026-10-04). Revisit if one does.
- **The negation test covers the negated path itself, not files inside a kept
  folder** (decided 2026-10-04): after `build/*` and `!build/keep/`, an appended
  `*.bak` ignores `build/keep/x.bak`, which is the baseline doing its job, not an
  override (the negation's last match is the folder, not the file). Hinges on
  whether an owner ever means "keep everything in here" by a folder negation.

## Unconfirmed suspicions

(none open)

## Reported to other owners

- 2026-10-04, via the dispatcher, to checks: take the mutant runner as `checks
  mutants [PATH]` (td-9 decision above; start from tools/todo's copy, which has
  the `edits` list). And to todo: td-9 is decided that way, so it waits on checks.
- 2026-10-04, via the dispatcher, to the planner: the check component and §9 (1)
  both need setup to name a sibling tool, which its content audit forbids; the
  proposal is under Open decisions.
- 2026-10-04, via the dispatcher: the `ignore` component is new (fixes the hub
  scaffold leaving `.claude/settings.proposed.json` untracked and writing no
  `.gitignore`). Every repo set up before it lacks the baseline entries:
  `tools/hub` first (its owner re-runs `./setup tools/hub` from the workspace
  root and commits the appended `.gitignore`), then the rest on their next run.
- Done, seen 2026-10-04: the roster entry and its `"repo"`
  (`github.com/CyberImpXIII/setup`); `setup plans` wired into `agents.sh check`
  (`check_plans`); this CLAUDE.md in the rules-sync lists (the live
  `test_sync_list` comparison passes); DECLARED in site-scrapers. The
  "Constraints" end-marker suspicion is settled: the generator copies that section
  from the top-level CLAUDE.md, which has no markers, and `.claude/agents/setup.md`
  holds no `/shared` marker.
