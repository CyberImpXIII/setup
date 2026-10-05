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
- **Defaulting the hooks source to tools/hooks/source: asked by the dispatcher
  2026-10-04, not built.** Evidence relayed from data-bridge: `setup --dry-run` there
  printed `hooks unchanged ... 6 unchanged of 6` while `hooks copies` printed DRIFT
  for 5 of those files, because setup compared against its own `.claude/hooks/`, which
  lagged the source. Fixed for today by reinstalling those copies (59ed067; re-run
  after it: data-bridge byte-equal to the source, setup `unchanged` correctly). The
  class stays: whenever the source moves first, setup's "unchanged" means "agrees with
  my stale copy". Mitigated, not solved: the hooks line now says `against <dir>`.
  Not built because it is PLAN-tools-folder §9 (1), which the plan and the top-level
  TODO say waits on Jacob's yes, and because it collides with the content audit (the
  decision above). Hinges on: Jacob's yes on §9 (1), then the dependency decision.
- **A replace path for a drifted hook copy** (three agents report setup has none;
  dispatcher, 2026-10-04: record, do not decide). Evidence: today's reinstall here was
  6 hand `cp`s from tools/hooks/source/hooks/ because `setup . --hooks-from
  ../hooks/source` reports all 6 as drift "not overwritten". Options: an explicit
  flag (e.g. `--replace-hooks`, never default) that overwrites a copy differing from
  the source, or §9 (1)'s "header refreshed" path, which replaces only copies equal by
  meaning and still leaves a logic change (today's case) to a hand copy. Hinges on:
  whether setup may ever overwrite a file in a repo it did not create (CLAUDE.md
  "What setup never does" says no today). Waits on Jacob (planner decisions 33-35);
  not built. **Moot for the applies_to=all hooks once user scope is on** (2026-10-04,
  `--user-scope`): a covered hook runs from its one source, so its per-repo copy is
  neither replaced nor read (a drifted copy of a covered hook is no longer drift).
  It stays live for any hook user scope does not cover (a `repos:` hook, or before
  Jacob applies the user-scope proposal).
- **`--user-scope` has no default** (built 2026-10-04, decision 19). The workspace run
  is `./setup <path> --user-scope <(cd tools/hooks && ./hooks copies .. --json)`; without
  it the hooks line says "user scope not checked" and behaviour is as before. A default
  would name the sibling tool: same dependency decision as above.
- **The coverage rule is a second copy of tools/checks' `hooks-installed` rule**
  (`_coverage` and `_user_scope_shape` in setuplib/core.py), not a shared helper:
  setup may not import a sibling tool (content/direction audits; the dependency
  decision above), and checks' rule lives in a check script that runs on import.
  Gated: the rule's cases are tests here with mutants (tests/test_userscope.py), and
  the shape by a live test that runs the real `hooks copies --json` against scratch
  user settings (`hooks userscope --out` into a temp folder, HOME pointed there too).
  NOT gated: that the two copies agree by meaning if checks' rule changes. Settle
  when the dependency decision lands (then both read one helper), or checks exposes
  the rule in checkslib and a workspace test here calls both on one fixture.
- **After Jacob applies user scope, every repo still registering the shared hooks per
  repo runs them twice** until its settings.json drops them. Setup's proposal does
  that only when run with `--user-scope` on each repo (the proposal is still his to
  apply). This repo too: its own `./dev.sh hooks` REQUIRES each copy registered in
  `.claude/settings.json`, so applying the drop here turns that gate red. Needs a
  decision once user scope is on: `dev.sh hooks` accepts user-scope coverage (read
  from the same report) or keeps per-repo registration here deliberately.
- **Plug-ins whose registration runs from below the registry's root fail** (built
  2026-10-04, `--plugins`): tools/hooks gives one `registration`, with a command
  relative to the workspace top, so it is correct only for applies_to `repos:.`. A
  plug-in applying to another repo (or `all`, on any repo but the top) is `failed`
  with the reason, never a guessed path. Hinges on tools/hooks giving a per-repo
  registration if one is ever needed (none is today: kb-pointers is `repos:.`).
- **kb-pointers cannot be proposed today: the workspace top is not a git repo, and
  setup refuses it** (run 2026-10-04 from the top: `setup . --dry-run --plugins
  <(...)` -> "refused: ... is not empty, and is not a git work tree"). kb-pointers is
  `repos:.`, the top only. The `--plugins` machinery is proven with the live registry
  re-rooted at a scratch repo (the proposal held exactly its `registration`). Needs a
  decision, not built: a settings-only mode for a non-repo folder (only the hooks
  component, the proposal written, nothing else), or the dispatcher/harness writes
  the top's proposal from `hooks plugins --json` directly. Hinges on whether setup
  should ever touch a folder that is not a repo.
- **`--plugins` has no default.** The workspace run is `./setup . --plugins <(cd
  tools/hooks && ./hooks plugins --json)` from the top; without the flag the hooks line
  says "plug-in hooks not checked". A default would name the sibling tool: same
  dependency decision as above.
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

- **`check --json` validated by subprocess, not by a vendored schema** (2026-10-05).
  The stub's `--json` and this repo's own (`devtools/checkjson.py`) are held to
  reviewed fixtures in `tests/fixtures/` anywhere, and to the real `check-json`
  validator (the shared checks CLI, run on scratch repos) in the workspace, with the
  old `{"ok","error"}` shape as the counterfactual. No copy of the schema or its
  validator lives here (a copy would need a second validator: duplicated procedure).
  Cost: in a lone clone only the fixtures hold; a schema change upstream is caught
  only in the workspace. `devtools/checkjson.py` is a second emitter beside checks'
  `checkslib/devjson.py` (setup may not import a sibling tool): agreement by meaning
  is gated by the live validator test, not by a shared helper. Revisit with the
  dependency decision above.
- **Repos set up before 2026-10-05 keep the old stub's `{"ok": false, "error"}`**:
  setup never overwrites `dev.sh` (an existing stub is `needs-owner`). Probe run
  2026-10-05, `grep -l SETUP-STUB */dev.sh */*/dev.sh` from the workspace top: none
  carry the stub today, so nothing to migrate.

- **A created repo whose render is empty gets no settings.json** (§7.9, built
  2026-10-05). With `--user-scope` covering every shared hook and no plug-in applying,
  nothing is missing, so the hooks line is `unchanged` and no file is written or
  committed. §7.9 says the file also holds "the permission mode", but the render (the
  source settings.json) carries hooks only, so a created repo carries no permission
  mode either. Hinges on: whether every created repo must carry a settings.json (then
  write the empty render too) and whether a permission mode belongs in the source.
- **PLAN-repo-setup §2 and §7.6 still say setup only writes `settings.proposed.json`**;
  §7.9 is the exception, built here. The plan text is the planner's to reconcile.

## Unconfirmed suspicions

(none open)

## Reported to other owners

- 2026-10-05, via the dispatcher, to checks: `checks one check-json tools/setup`
  took 242.7 s against check-json's 280 s limit (an earlier run, 228.5 s): this
  suite (123 tests + 67 mutants) is near the cap and will cross it as mutants
  grow. PLAN-agent-groups §4.4 already says raise the limit; this is the evidence.
  Also: check-json proves shape only. This repo's `--json` once printed a valid
  report with every gate after `hooks` reading `fail` and no finding, from a bash
  variable leak (fixed here, gate runs in a subshell, mutant `own-json-gate-clobbers`);
  check-json passed it. Not a bug in checks, a reason for each repo's own wiring test.

- 2026-10-04, via the dispatcher, to knowledge-base: its TODO observation that
  this CLAUDE.md's "Keeping these rules in sync" names only `../../CLAUDE.md` is
  stale (it names all nine hand-synced copies; `tests/test_sync_list.py`'s live
  comparison passes). The section's prose was reworded (commit "CLAUDE.md: sync
  section"): it now says why the block-carrying tool folders stay out of the list.
  Their item can be closed.

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
