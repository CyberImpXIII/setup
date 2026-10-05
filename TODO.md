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
  Since §7.12 (2026-10-05) `audit deps` is UNCHECKED there too, and the hooks
  component fails without `--hooks-from`. unverified: which other test modules go
  red in a lone clone because their fixtures use the default hook source (the
  LoneClone classes in test_hooks and test_deps are the only ones proven) --
  settle: copy this folder outside the workspace, `git init`, `./dev.sh test`.
- **The agent line's `"repo"` reads "none yet" in a dry run on a new folder**,
  though the real run would make a local repo and print "local, no remote yet".
  Deliberate: it reports the target as it is now (dispatcher's brief, 2026-10-04).

- **Setup's own `record_pass` in dev.sh has no test or mutant** (2026-10-05):
  recording only on a green check is proven for the stub contract only by reading.
  Running `./dev.sh check` from a test recurses into the whole suite. Settle: a test
  that runs `cmd_check` with GATES overridden to one stub gate (dev.sh would need a
  `GATES` env override, which is itself a seam to guard).

## Open decisions

- **githooks (PLAN-hard-gates §7 phase 2), built 2026-10-05; decisions for Jacob.**
  (1) *Strict match*: pre-commit accepts only a staged tree equal to the working
  tree the check passed on, so a partial commit (staging some changes, leaving
  others) is refused, and so is any commit in a tree holding another agent's
  uncommitted work. Open: keep strict, or record the *index* tree instead (then an
  unstaged edit the check saw goes in unchecked). (2) *CLAUDECODE as the session
  marker* (probed: set in every Bash call of a session): a `!` command typed in
  Claude Code has it too, so Jacob's own commit from there is refused unstamped;
  and a cron or script commit outside any session is stamped `Agent: jacob` (false
  attribution). (3) A merge commit in a session (`git pull`, `git merge`) runs
  commit-msg and carries no Agent trailer (git-stamp stamps `git commit` only), so
  it is refused. (4) `git commit --no-verify` skips both hooks; only a session hook
  can block it (reported to hooks, below). (5) Activation is gated: core.hooksPath
  is set only when the check records its pass, `--checks` is given, git-stamp.sh is
  wired, and the default hooks folder is empty. Since §7.12 the source is the hooks
  dependency, which registers git-stamp.sh, so a new repo is wired (githooks
  `installed` in tests/test_fixture.py); an existing one waits on its settings. (6) The plan names it `git-gates` (§7a) and
  `git-hooks` (§7); built as `githooks` (a component name is a method name).
  (7) `resumed_from` waits on harness `progress.sh`; the seam is `check-pass record
  --resumed-from K/N`. gates.json (§7a) is phase 3, not built here.

- **§7.11 data component, built 2026-10-05; three parts of §7.11 not built here.**
  (1) The `--node --rebuild` store row (`emerged`, `same`, `drift`, `state`): the
  rebuild renders into a scratch copy and has no store to compare; it needs `verify`
  on an existing store, which setup leaves to the shared `stores-exported`. Open:
  build it as "run verify on each child's store in a rebuild", or drop it for the
  gate. (2) Data-repo commits "scoped to the exporting tool's folder" belong to the
  export (the `write` service, §14.6), not to setup's import: no setup code commits
  in the data repo. (3) `DATA_REPO` arrives by `--data-repo` or the environment;
  the `.claude/local.env` loader (PLAN-portable-env §3.1) does not exist yet, so
  nothing exports it today. Also open: a tool with a store and no export yet (its
  folder absent from the data repo): its `import` decides (exit non-zero: setup's
  line is failed). And the plan says cli.json "declares `stores`"; the shared
  schema's field is `store` (string or list): setup follows the schema.
- **§7.12 built 2026-10-05: the hooks component renders from the hooks dependency**
  (`dependencies.json`, `setuplib/deps.py`, `setup audit deps`). This settles three
  old items: reading `hooks list --json`, defaulting the source to tools/hooks/source
  (the data-bridge "6 unchanged of 6" against a stale copy), and the content-audit
  collision (dependencies.json is exempt from content and gated by `audit deps`).
  Also fixed: `setup <repo> --dry-run` on an old six-file repo said "0 installed, 6
  unchanged of 6" (the income report); it now lists the 22 files the listing names
  (`test_old_six_file_repo_gets_the_rest_installed`). Still open, below.
- **Replacing a drifted hook copy waits on Jacob (§7.12 end).** A copy whose logic
  differs from the source is `drift` and byte-unchanged under a plain run and under
  `--rebuild`; only a copy equal by meaning is rewritten ("header refreshed"). Options:
  an explicit flag (never default), or `--rebuild` overwriting in a repo setup did not
  create. Hinges on: whether setup may ever overwrite logic in a repo it did not
  create. The five DRIFT files in other repos stay until then. Moot for any hook user
  scope covers (`--user-scope`): its per-repo copy is neither replaced nor read.
- **Other repos owe a reinstall (§7.12 step 2, dispatched per owner).** `hooks copies
  <top> --gate <loc>` showed ~18-21 non-ok files per location before this change;
  `setup <repo>` now installs the MISSING ones. Not run here (the brief: step 2).
- **7 hooks here run only once Jacob applies the proposal.** `./setup .` rendered the
  dependency's 10 hooks and 2 libraries; `.claude/settings.json` (Jacob's) registers 3,
  so `./dev.sh hooks` prints 7 `PENDING` lines and passes. Settle: Jacob runs `cp
  .claude/settings.proposed.json .claude/settings.json` here.
- **The checks dependency is named but not read yet.** `dependencies.json` names
  tools/checks so a future `checks run .` in the stub can resolve it; nothing in code
  consumes it today (`_used_by` says so). `audit deps` still gates it.
- **The hook source is the dependency's working tree, not a commit.** Another agent's
  uncommitted edit in tools/hooks/source is what setup installs. Options: install from
  `git show HEAD:` in the dependency, or refuse a dirty source. Hinges on whether a
  hooks agent's in-progress edit should ever reach other repos.
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

- **node.json is read twice: by setuplib/node.py and by tools/checks' contract** (built
  2026-10-05, §7.5/§7.10). Setup may not import a sibling tool, so `load` mirrors
  checks' `schema/node.schema.json` and its x-rules; the live tests (test_node
  LiveChecks: `checks run` on every repo of a two-level tree, and `checks one
  rendered-matches|regenerate` ok on a scaffold, fail on a committed edit) hold the
  readings together, both ways. Built against checks' then-UNCOMMITTED node schema
  (96ceef9 plus their working tree, 2026-10-05). One rule is setup's own: a child
  inside another child is refused (checks accepts it); a record glob matching nothing
  is not flagged (as in checks).
- **Two comparers of a rebuild exist by design**: setup's per-file report and checks'
  regen engine (which distrusts the generator and counts from git and bytes). Only
  `failed` exits 1 here; drift and unaccounted are progress, `regenerate` is the gate.
- **A generated file setup does not render is `failed`**: node.json's one `rebuild`
  is setup's, so a second generator (a file another tool renders) has no place yet.
  Hinges on the plan saying how a node composes generators.
- **In checks' clone a plug-in registered at the top reads as drift**: the render's
  path is the clone's (`stands_for`), so `repos:.` matched against the registry root
  fails there. CHECKS_ORIGIN is deliberately not read (coupling). Unverified until a
  node with a plug-in exists -- settle: `checks one regenerate .` on that node.
- **Should a parent's .gitignore list its child paths?** Today a nested child shows as
  untracked `child/` in the parent and both readers skip it as a child. Not decided.
- **A node with children needs a registry** (checks' registry-matches): settled
  2026-10-05 (§14.8). Setup renders `registry.proposed.json`; the fixtures copy it to
  the registry node.json names (Jacob's step) and pass `checks run` on every repo.
- **§14.8's `cli.json` skeleton `{store, cli, verbs: []}` is not installed** (2026-10-05).
  No skeleton passes checks' cli.schema.json (`store` minLength/minItems 1, `cli`
  executable), and their `accessor` accepts no store with no cli.json, so writing one
  would turn every new repo red for nothing. The `cli` component reports `none`
  ("a repo with a store adds {store, cli, verbs}"). Hinges on the planner: change the
  plan's table row, or checks accepts an unfilled skeleton as needs-owner.
- **The registry renders only `services`** (2026-10-05): §14.6 also gives a registry
  roles, owners and the server entry, which have no defined shape here (and roles are
  the roster's, which setup must not read). Hinges on the hub's registry plan.
- **A fresh node with children exits 1 under `--checks` until Jacob applies the
  registry proposal**: registry-matches is red (children, no `registry`), and that is
  the true state; the registry line says `needs-jacob` with the copy command.
- **`check-json` is gated to the audit role in checks, so `checks run` skips it**; the
  gates component runs it by name (`checks one`), since it is a §14.8 contract gate.
  On this repo it takes ~4 min (the full suite); every `--checks` run on a repo with a
  real suite pays it. Hinges on checks (a shape-only mode) or accepting the cost.
- **Setup's own run under `--checks` is red** (2026-10-05, before this commit):
  `hooks-installed` fails, `.claude/hooks/ask-first.sh` missing here (the shared source
  has a hook this repo's copies lack), and `check-json` errored (exit 1) while this
  suite was mid-change. Re-check after the commit: `./setup . --checks ../checks/checks`.

## Unconfirmed suspicions

(none open)

## Reported to other owners

- 2026-10-05, via the dispatcher, to checks: PLAN-hard-gates §3 row 6 says the
  pre-commit runs no-secrets on the *staged diff*; `checks one no-secrets <repo>`
  scans tracked plus would-be-committed working-tree files, so a secret staged and
  then deleted from the working tree is not seen. The githooks pre-commit calls it
  as is (`one no-secrets <top> --json`). Expected: a `--staged` mode, or the plan
  amended. To hooks: `git commit --no-verify` skips the githooks gates; git-stamp.sh
  (or phase 3) is the only place that can refuse it. (Settled 2026-10-05, §7.12: this
  repo now renders git-stamp.sh and write-ledger.sh from the hooks dependency, and a
  new repo is wired from its settings.json.)

- 2026-10-05, via the dispatcher, to checks: setup now consumes node.json
  (`setuplib/node.py` mirrors schema/node.schema.json), so a schema change there
  needs a matching change here; the live tests in tests/test_node.py go red if not.
  Divergence: setup refuses a child inside another child, checks accepts it.
  `setup . --node --rebuild` exits 1 only on a failed line (their engine reads any
  non-zero exit as a `rebuild` finding, which is then correct).

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
