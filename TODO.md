# setup TODO

## Own bugs

- **`./dev.sh hooks` and the `hooks-gate` mutant only pass inside the workspace.**
  `test-troubleshooting.sh` (a shared hook test, not ours to edit) fails with
  "site-scrapers NOT FOUND above" when the repo is cloned elsewhere. Mutant copies
  live in `.mutants/` inside this repo for that reason. In a lone clone, check
  will be red on `hooks`: accurate (the hook enforces nothing there), but noted.
- **Outside the workspace `./setup audit content` prints UNCHECKED and exits 0**
  (no sibling repos to compare against). The audit itself is proven by the
  planted-workspace tests, which run anywhere.

## Open decisions

- **Hook copies here are a ninth copy, counted by nobody yet.** `.claude/hooks/`
  holds the three shared hooks copied byte for byte from `applications`
  (identical to `site-scrapers`' canonical copies, 2026-10-03). Until
  `tools/setup` is added to `DECLARED` in `site-scrapers/check-hooks.sh` (and
  `knowledge-base`'s copy of that check), `site-scrapers`' `./dev.sh check`
  reports this folder as "holds twinned hooks but is not in DECLARED", and
  nothing checks these copies equal the others (`./dev.sh hooks` checks only that
  they are present, registered and pass their own tests). Registering the copy is
  a harness / site-scrapers job (routing-tree §12 S1 takes over hook copies);
  reported through the dispatcher on 2026-10-03.
- **The plans gate runs here only as a test.** `./setup plans <dir>` works, but
  wiring it into the workspace check (PLAN-repo-setup §3 "Every plan has a setup
  section") belongs to the delegation layer's own check: harness's job, reported
  2026-10-03.
- **`--github` is public by default** (the dispatcher's brief and PLAN-tools-folder),
  while PLAN-repo-setup §2 says private. Followed the brief; the plan text is the
  dispatcher's to update.
- **The agent entry's `dir` is the path as typed, relative to where setup runs.**
  Run from the workspace root (`tools/setup/setup tools/x`) to get a roster-ready
  `dir`. Could become a `--relative-to` flag if it bites.

## Unconfirmed suspicions

- **`audit-terms.json` `roster_names` is a copy of the roster** and goes stale when
  an agent is added. Not read from the roster on purpose (the direction audit
  forbids it). Probe: compare it with the roster list after the next roster
  change.
- **The `Constraints that don't bend` heading now sits inside a marked block,** with
  `<!-- /shared -->` right after its last bullet. The roster generator copies that
  section verbatim for agents that skip the top-level file; whether it would carry
  the end marker along is unverified. Settle (harness): generate with this folder
  on the roster and read the rendered definition.

## Reported to other owners

- 2026-10-03, via the dispatcher: register `tools/setup` hook copies (DECLARED, in
  `site-scrapers` and `knowledge-base`); add the roster entry; wire `setup plans`
  into the workspace check; add `tools/setup/CLAUDE.md` to the rules-sync lists
  (top-level CLAUDE.md, `site-scrapers/test/rules-sync.test.js`,
  `knowledge-base ./dev.sh sync`).
