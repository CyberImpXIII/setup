<!-- rendered by todo from todo.json (96 open, 21 closed in todo-history.json; seal 8397ff2d1d36): do not edit by hand, `todo check` fails on a hand edit. Change items with the todo CLI; a hand edit is recovered with `todo import`. -->
# setup TODO

## Own bugs

- **su-1 · The hooks component renders the hook source's work tree, uncommitted edits and all**
  (found 2026-10-13: four repos -- knowledge-base, scripts,
  site-scrapers, tools/todo -- hold uncommitted hook copies, and tools/checks held
  an uncommitted runner 1.3.0 that a parts pass would have copied into ten repos).
  The parts component now renders the runner as its repo's HEAD holds it
  (`deps.committed`; `tests/test_parts_component.py` Committed; three mutants).
  The hooks side is not done: its listing (`hooks list --json --source`) and the
  comparator read the work tree. Fix: render from `git archive HEAD <source>` into
  a throwaway folder and pass that as `--source`, or refuse while
  `git status -- <source>` in the hooks repo is not empty.
  · added: 2026-10-15

- **su-2 · plans `--facts` grammar collides with prose mappings**
  : on the workspace
  2026-10-13 `setup plans . --facts` exit 1, 14 cited (13 not-declared, 1
  not-one-command): most are prose `x` → `y` mappings, and PLAN-architecture
  line 525 is the grammar's own `<cmd>` example. The plan's author picks: another
  arrow for prose, or a narrower grammar (a fact marked, e.g. `fact:`).
  · added: 2026-10-15

- **su-3 · The baseline `.gitignore` does not ignore `.progress/`**
  (2026-10-15): a repo
  whose `dev.sh check` hands its parts to the rendered runner (`devtools/parts.py`)
  gets an untracked `.progress/` (the runner's progress file and part logs). Added
  here by hand; the baseline (components.json `ignore`) should carry it once a repo
  has the `parts` component. Probe: `./setup <repo with parts> --dry-run` after a
  check, then `git status --short`.
  · added: 2026-10-15

- **su-4 · plans add / edit: the second digest check (just before the write) has no fixture**
  ; the mutant set covers the first only.
  · added: 2026-10-15

- **su-5 · A lone clone's `./dev.sh check` is red on `hooks`, `mutants` and `audit`.**
  By
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
  component fails without `--hooks-from`. Settled 2026-10-08 (this folder rsynced
  to the scratchpad, `git init`, `./dev.sh test`): 318 tests, 88 failures, 11
  errors, 43 skipped. By module: test_node 38, test_userscope 15, test_plugins 10,
  test_data 8, test_settings_new 7, test_contract 7, test_remote 3, test_ignore 3,
  test_idempotent 2, test_fixture 2, test_dryrun 2, test_refuse 1, test_deps 1;
  nearly all `1 != 0` / `(1, status)`: setup exits 1 on the hooks line's `failed`
  (no dependency). So a lone clone's `test` gate is red too (CLAUDE.md now says so).
  Open, not decided: give those fixtures a planted hook source (`--hooks-from`, as
  test_hooks' LoneClone does) so only the LoneClone classes depend on the
  workspace; ~100 call sites, worth it only if a lone clone's check is ever meant
  to be green.
  · added: 2026-10-15

- **su-6 · A fresh clone's `./dev.sh hooks` FAILs 7 hooks as registered nowhere**
  (probe 2026-10-08, `git clone` to the scratchpad): `settings.proposed.json` is
  gitignored, so a clone has only Jacob's settings.json (3 registrations). True (they
  run nowhere there) and the line says `run ./setup .`; it clears once Jacob applies
  the proposal here (Open decisions, "7 hooks here run only once..."). The same probe
  found the income agent's report true: a hook test's exit 3 (UNCHECKED: no
  site-scrapers above) read as FAIL. Fixed 2026-10-08: UNCHECKED with its reason,
  gate exit 3 (`tests/test_hooks_gate.py`, three mutants).
  · added: 2026-10-15

- **su-7 · The agent line's `"repo"` reads "none yet" in a dry run on a new folder**
  ,
  though the real run would make a local repo and print "local, no remote yet".
  Deliberate: it reports the target as it is now (dispatcher's brief, 2026-10-04).
  · added: 2026-10-15

- **su-78 · other repos' .claude/lib/ledger.sh and test-store-guard.sh copies now drift and need a reinstall ...**
  reported from tools/hooks to tools/setup in dispatch toolu_012AsDNG3r1uaCmkzk1wzHZx, filed from the dispatch ledger by the delegation layer's report filer: other repos' .claude/lib/ledger.sh and test-store-guard.sh copies now drift and need a reinstall (OWED). Earlier F3 layer-2 report still stands.
  · parent: tl-224
  · added: 2026-10-16

- **su-79 · `--only parts --rebuild` cannot update a runner copy in a repo whose `.claude/settings.json` is J...**
  reported from addon-bench to tools/setup in dispatch toolu_015nN2HPVFRy29Mgm4jujvfn, filed from the dispatch ledger by the delegation layer's report filer: `--only parts --rebuild` cannot update a runner copy in a repo whose `.claude/settings.json` is Jacob's uncommitted wiring-apply without committing that file, and it refuses any tree with other uncommitted work -- input: `tools/setup/setup addon-bench --only parts --rebuild --overwrite-uncommitted --dry-run` -- expected: a way to render the runner that leaves settings.json out of the commit.
  · parent: tl-227
  · added: 2026-10-16

- **su-80 · no hook render can land in this repo. `setup tools/transcripts` rendered, then its own commit was...**
  reported from tools/transcripts to tools/setup in dispatch toolu_01Munq7FZhSWnF48mx4aMgi7, filed from the dispatch ledger by the delegation layer's report filer: no hook render can land in this repo. `setup tools/transcripts` rendered, then its own commit was refused by this repo's pre-commit hook and it put everything back. `--only hooks --rebuild` refuses a dirty tree, although its help says it never commits. -- input: `tools/setup/setup tools/transcripts [--only hooks --rebuild]` -- expected: `--rebuild` writes without committing, as its help says.
  · parent: tl-243
  · added: 2026-10-16

- **su-81 · .githooks/check-pass refuses every commit while the uncommitted .claude/settings.json is in the t...**
  reported from tools/context-hygiene to tools/setup in dispatch toolu_01NWqt286g6ioVGc9Rz7AeoR, filed from the dispatch ledger by the delegation layer's report filer: .githooks/check-pass refuses every commit while the uncommitted .claude/settings.json is in the tree -- input: tools/context-hygiene, check passed on tree f606de85c194, staged tree 7db2b50d7982 -- expected: a commit of the store files to go through while settings.json stays uncommitted.
  · parent: tl-245
  · added: 2026-10-16

- **su-82 · the installed copies of store-guard.sh, test-store-guard.sh, ledger.sh, prefer-recipes.sh and wri...**
  reported from tools/hooks to tools/setup in dispatch toolu_01P2QUjhfZGL3aQ5foWPuX2W, filed from the dispatch ledger by the delegation layer's report filer: the installed copies of store-guard.sh, test-store-guard.sh, ledger.sh, prefer-recipes.sh and write-targets.sh no longer match the source in income, scripts, knowledge-base and tools/checks; the source changes were intended -- input: `tools/hooks/hooks copies` -- expected: re-render them from tools/hooks/source.
  · parent: tl-247
  · added: 2026-10-16

- **su-83 · parts.py is now 1.1.0, so `tools/setup/devtools/parts.py` and the copies it rendered into repos (...**
  reported from tools/checks to tools/setup in dispatch toolu_01UsoP3YSofAzhSbJhhJbU2p, filed from the dispatch ledger by the delegation layer's report filer: parts.py is now 1.1.0, so `tools/setup/devtools/parts.py` and the copies it rendered into repos (1.0.0) differ until setup re-renders them -- input: `cmp tools/setup/devtools/parts.py tools/checks/checkslib/parts.py` -- expected: setup re-renders.
  · parent: tl-249
  · added: 2026-10-16

- **su-84 · check-pass hashes `git add --all` of the working tree, so a commit can never pass while another s...**
  reported from tools/transcripts to tools/setup in dispatch toolu_01AMZayunWGyknYwA7iG5Jjn, filed from the dispatch ledger by the delegation layer's report filer: check-pass hashes `git add --all` of the working tree, so a commit can never pass while another session's unstaged change is in it -- input: transcripts tree with unstaged .claude/settings.json, commit of all other paths -- expected: a way to check the staged tree or name excluded paths.
  · parent: tl-258
  · added: 2026-10-16

- **su-96 · practice ids live in gates.json `practices.rows[].id`; `rules[].id` holds the CLAUDE.md section r...**
  reported from tools/checks to tools/setup in dispatch toolu_018yA82V2Y591W3oYWd3ofnY, filed from the dispatch ledger by the delegation layer's report filer: practice ids live in gates.json `practices.rows[].id`; `rules[].id` holds the CLAUDE.md section rows -- input: setuplib/practices.py resolving `## Practices` ids -- expected: resolve against practices.rows[].id (settles su-89; tl-307 closed). Also: checks holds a copy of todo's sqlstore.py until step 10.2.
  · parent: tl-359
  · added: 2026-10-19

- **su-98 · devtools/parts.py in each repo is still 1.3.0 and lacks --jobs/uses -- input: checks checkslib/pa...**
  reported from tools/checks to tools/setup in dispatch toolu_01RTRCd7BG3nGNiNv96j65Qw, filed from the dispatch ledger by the delegation layer's report filer: devtools/parts.py in each repo is still 1.3.0 and lacks --jobs/uses -- input: checks checkslib/parts.py 1.4.0 (0be97db) -- expected: reinstalled through each repo's parts component.
  2026-10-20: ./setup fanout parts --root <top> --dry-run: 12 repos drift (copy 1.3.0 vs runner 1.4.0, checks 0be97db): addon-bench, applications, emailTools, income, scriptingTools/chronjobScheduler, scriptingTools/data-bridge, scripts, tools/hooks, tools/research, tools/todo, tools/transcripts, tools/wizard; usage rebuilt (su-99), setup rebuilt (49f2dc3). Fix: ./setup fanout parts --rebuild --agent setup commits into each owner's repo: needs each repo clean, so expect failed rows where trees are dirty
  2026-10-20 (tl-488): ./setup fanout parts --repos tools/research tools/transcripts --rebuild --agent setup: committed research 8e79242, transcripts 09a6a57 (each cmp-equal to checks HEAD 0be97db checkslib/parts.py; each ./dev.sh test test.parts ok; neither has a remote, nothing pushed). The other 10 refused by fanout as not clean, owners' uncommitted edits, never swept in: addon-bench, applications, chronjobScheduler, data-bridge, tools/hooks (.claude/settings.json, TODO.md); emailTools, income, scripts (+ .claude/hooks and .claude/lib copies; income todo.json); tools/todo (README.md, devtools/mutants.json, tests/test_practices.py, todo stores); tools/wizard (staged tl-455 work: tests/helpers.py, wizards/architecture.json, .claude/lib/ledger.sh).
  2026-10-20 (tl-499): ./setup fanout parts --root ../.. --rebuild --dry-run: 1 would-commit (data-bridge), 7 unchanged (knowledge-base, context-hygiene, hub, research, setup, transcripts, usage), 9 refused as not clean. ./setup fanout parts --repos ../../scriptingTools/data-bridge --root ../.. --rebuild --agent setup: committed 361225f after a green check (30/30 parts), copy cmp-equal to checks HEAD 0be97db, pushed to origin. Left, each refused for owners' uncommitted edits (never swept): addon-bench, applications, chronjobScheduler, tools/hooks (.claude/settings.json, TODO.md); emailTools (+ .claude/hooks/store-guard.sh, test-store-guard.sh, .claude/lib/ledger.sh); income (same + todo.json); scripts (+ prefer-recipes/store-guard hooks and tests, .claude/lib/ledger.sh, write-targets.sh, todo.json, .claude/bin/, ...); tools/todo (README.md, devtools/mutants.json, tests/test_practices.py, todo stores); tools/wizard (.claude/lib/ledger.sh, tests/helpers.py, wizards/architecture.json).
  · parent: tl-376
  · done when: ./setup fanout parts --root ../.. --dry-run lists no repo as drift (copy 1.3.0): each of the 10 remaining repos rebuilt by ./setup fanout parts --repos <repo> --root ../.. --rebuild --agent setup once its owner has committed or cleared its tree
  · done check: ./setup fanout parts --root ../.. --dry-run
  · handoff: done: data-bridge 361225f (pushed), research 8e79242, transcripts 09a6a57; usage committed its own (7e22666). next: 9 dirty repos (addon-bench, applications, chronjobScheduler, emailTools, income, scripts, tools/hooks, tools/todo, tools/wizard), each once its owner clears its tree; verify: ./setup fanout parts --root ../.. --rebuild --dry-run (2026-10-20) (2026-10-20, at 48bfcce)
  · approved: jacob 2026-10-20: Jacob 2026-10-20 typed: 2) yes (fan-out of the 1.4.0 runner copy to the 12 repos)
  · added: 2026-10-19

- **su-106 · the commit-msg hook (core.hooksPath) is set in only 4 of 20 repos, and 618 of 978 commits since 2...**
  reported from tools/research to tools/setup in dispatch toolu_01UN1CyFQG8Z7QD9MeEmRrBq, filed from the dispatch ledger by the delegation layer's report filer: the commit-msg hook (core.hooksPath) is set in only 4 of 20 repos, and 618 of 978 commits since 2026-10-01 have no Agent trailer -- input: git -C <repo> config core.hooksPath -- expected: .githooks in all 20 (G5)
  · parent: tl-475
  · added: 2026-10-20

- **su-107 · an unedited older render is called `drift` and is replaced only with `--rebuild`; 10 repos fail `...**
  reported from scriptingTools/data-bridge to tools/setup in dispatch toolu_01EzoxpRduj6yVXXYQKCrQHJ, filed from the dispatch ledger by the delegation layer's report filer: an unedited older render is called `drift` and is replaced only with `--rebuild`; 10 repos fail `fanout parts` this way -- input: `./setup scriptingTools/data-bridge --only parts --dry-run` -- expected: reported as outdated and re-rendered by the fanout (unverified: may be intended policy).
  · parent: tl-497
  · added: 2026-10-20

- **su-110 · emailTools devtools/parts.py is stale (1.3.0 vs 1.4.0), and cfc946e is unpushed alongside uncommi...**
  reported from emailTools to tools/setup in dispatch toolu_01JSTDoEP9cPktEn3mYvnnTh, filed from the dispatch ledger by the delegation layer's report filer: emailTools devtools/parts.py is stale (1.3.0 vs 1.4.0), and cfc946e is unpushed alongside uncommitted .claude edits -- input: cd emailTools && ./dev.sh check -- expected: 12 of 12; the fix the test names: tools/setup/setup emailTools --only parts --rebuild
  · parent: tl-526
  · added: 2026-10-20

- **su-111 · `funnel.push` is unset in every repo, so commit.sh never pushes and git-funnel blocks a typed pus...**
  reported from emailTools to tools/setup in dispatch toolu_01SEZwfH6rtrMr5Zv3qg9M9w, filed from the dispatch ledger by the delegation layer's report filer: `funnel.push` is unset in every repo, so commit.sh never pushes and git-funnel blocks a typed push -- input: `commit.sh -C emailTools ...` -> "not pushed (no push record: git config funnel.push is not true)" -- expected: setup writes funnel.push=true for repos with an origin, or a sanctioned push path.
  · parent: tl-558
  · added: 2026-10-22

- **su-114 · chronjobScheduler has no funnel.push record, so commit.sh never pushes and the hook blocks a raw ...**
  reported from scriptingTools/chronjobScheduler to tools/setup in dispatch toolu_015sxuVPq4STrfadTnx5wNVs, filed from the dispatch ledger by the delegation layer's report filer: chronjobScheduler has no funnel.push record, so commit.sh never pushes and the hook blocks a raw push -- input: commit.sh -C scriptingTools/chronjobScheduler ... -- expected: commits reach origin
  · parent: tl-574
  · added: 2026-10-22

- **su-115 · addon-bench has no push record (`git config --bool funnel.push` unset), so commit.sh never pushes...**
  reported from addon-bench to tools/setup in dispatch toolu_01U4Wct8vnsomxxg3oGrrnUr, filed from the dispatch ledger by the delegation layer's report filer: addon-bench has no push record (`git config --bool funnel.push` unset), so commit.sh never pushes and 8a06525 sits ahead 1 of origin/master -- input: cd addon-bench && git config funnel.push -- expected: true (the remote origin exists)
  · parent: tl-583
  · added: 2026-10-22

- **su-116 · tools/checks has no `git config funnel.push` record, so commit.sh never pushes and 51cbafb, fdc62...**
  reported from tools/checks to tools/setup in dispatch toolu_01DNYWHyzimCzvnSdgBcuu4U, filed from the dispatch ledger by the delegation layer's report filer: tools/checks has no `git config funnel.push` record, so commit.sh never pushes and 51cbafb, fdc629f, 9525576 sit unpushed -- input: `commit.sh -C tools/checks "<msg>" checkslib/sqlstore.py` -- expected: pushed to origin/main.
  · parent: tl-593
  · added: 2026-10-22

- **su-117 · services.json `push` is refused by the shared schema, so the push component reports needs-owner everywhere**
  checks' services.schema.json has additionalProperties false: a scratch repo with services.json {"name":"r","push":true,...} gives 'FAIL services-valid: services.json: schema: $: unknown key `push`' (checks one services-valid). So no repo can record the push decision that the push component (2015390) reads, and the skeleton leaves it out. Today every live repo with an origin reports needs-owner (dry run: emailTools, usage, checks, hub, site-scrapers).
  · parent: tl-570
  · work: code
  · size: S
  · files: services.json
  · done when: checks accepts an optional boolean push; the skeleton services.json carries it; each repo's owner records push (usage and checks false, per PLAN-services §3 F3 step 5) and ./setup <repo> --only push reports installed or unchanged
  · added: 2026-10-22

## Open decisions

- **su-8 · Hook re-renders and kb-docs.tsv into other repos: blocked on permission**
  (2026-10-15, coordinator's PLAN-repo-setup §7.10 and PLAN-knowledge-base §11
  step 3). `setup <repo> --only hooks --rebuild --no-commit` was denied by the
  permission system in tools/transcripts and in this repo, so nothing was
  re-rendered; this repo's `self` gate stays red on `.claude/lib/ledger.sh`. Dry
  runs: ledger.sh, store-guard.sh and test-store-guard.sh drifted in addon-bench,
  applications, emailTools, income, chronjobScheduler, data-bridge, tools/checks,
  tools/hub, tools/research, tools/usage; ledger.sh only in tools/transcripts and
  tools/wizard; knowledge-base and scripts also want commit.sh, git-funnel.sh and
  their tests (needs-jacob); site-scrapers and tools/todo refused (uncommitted
  store-guard copies). `--only docs` dry run: kb-docs.tsv `installed` in every
  repo but this one; would commit in 11 clean repos, needs-owner in 8 dirty ones.
  Hinges on Jacob granting writes into other repos (or each owner running it).
  · added: 2026-10-15

- **su-9 · `setup fanout` (built 2026-10-13, interrupted; tested and committed 2026-10-15).**
  Not yet run on the real workspace. Choices open to Jacob: (1) repos run one after
  another, not in parallel (each repo's check may be heavy; parallel across
  processes is a later flag); (2) the check run is `./dev.sh check` in the repo that
  commits (for the workspace top's hooks: the `.claude` repo's own check); (3) the
  source commit is the source repo's HEAD, refused while the rendered-from paths are
  dirty; for `parts` the runner is read from HEAD already, so nothing more is
  required; (4) a discovered repo the component is not for is counted, not listed;
  (5) `dev.sh` stubs (named in the plan) are not a fanout component: setup never
  overwrites an existing dev.sh, so there is nothing to fan out.
  Own bug, seen 2026-10-15 in `setup fanout hooks --dry-run` from the workspace top:
  discovery enters a git repo nested inside another work tree that no node.json
  declares (`addon-bench/candidates/graphify/work/src/emailTools`, a candidate's
  clone) and lists it as a repo to render into. Expected: skip a nested repo unless
  its parent's node.json names it a child (setup's own nesting rule), counted.
  Not fixed yet.
  · added: 2026-10-15

- **su-10 · A node's `stores.json` (proposed by the hub owner, 2026-10-13; not built, wait for a dispatch carrying an approval line).**
  PLAN-hub.md on origin/plan/hub
  (63cf780), its Setup component table's `stores.json` row, and PLAN-services.md §3
  step 3 ("Two more from the hub owner", item 1) say setup should render a
  read-only `stores.json` beside hub.json at a node. It would be built from every
  owner's cli.json `store` field, mode 0444, re-rendered on every run, and `drift`
  when it no longer matches. The hub hook and server would both read it. Note:
  `store` is optional in cli.json now (3a3c3db), so a storeless repo adds no row.
  tools/setup has no cli.json of its own yet.
  · added: 2026-10-15

- **su-11 · core.hooksPath is unset in 11 of the 14 rendered repos (probe 2026-10-13, by design, reported by applications).**
  Set: emailTools, tools/wizard, tools/transcripts.
  Unset: applications, income, chronjobScheduler, data-bridge, hub, usage, hooks,
  research, addon-bench, checks, setup itself. setup sets it only when nothing would
  be refused for want of wiring; in applications the githooks line (needs-owner)
  names what is missing: its dev.sh does not run `.githooks/check-pass record`, and no
  `--checks CLI`. Gated: test_githooks `test_a_check_that_does_not_record_its_pass_leaves_them_off`,
  mutant githooks-on-when-unready (red 2026-10-13). Open: the rendered hooks'
  headers say only "Runs once core.hooksPath points at this folder", not what
  setup waits for; changing the templates makes every existing copy drift.
  · added: 2026-10-15

- **su-12 · Suspicion, unproven: the dry-run probe's `--only` filter has no mutant.**
  The
  `only-runs-everything` mutant now breaks the run loop's filter (`not in (self.only,
  "commit")`, core.py); the probe loop's `if self.only and c["name"] != self.only`
  (the old target, it survived there 2026-10-13) is gated by nothing known. Probe:
  delete those two lines and run `tests.test_only` and `tests.test_nocommit`.
  · added: 2026-10-15

- **su-13 · The --rebuild guard is mostly shadowed by S2's clean-tree rule**
  : a dirty copy is
  refused by both, so its mutants are held by ignored copies (and --no-commit), the
  one case the clean-tree rule lets through (2026-10-13: three mutants retargeted).
  · added: 2026-10-15

- **su-14 · The docs component (built 2026-10-13, d07bff9) writes the declaration only.**
  The index's owner asked for its refresh as a step in each repo's `dev.sh check`
  too: not done. dev.sh is the owner's once it exists, and the check template
  cannot name the index's command (content audit); it would need a dependency-fed
  template slot. Also: a declaration naming TODO.md makes a deleted TODO.md the
  docs line's drift (honest, but a second red for one cause). Open for Jacob.
  · added: 2026-10-15

- **su-15 · `--no-commit` (built 2026-10-13, e5da70a), used once.**
  Rendered, not
  committed, into tools/wizard and tools/transcripts (8 hook files each: commit.sh,
  git-funnel.sh and its test, prefer-recipes.sh and its test, test-store-guard.sh,
  lib/ledger.sh, lib/write-targets.sh); `checks one hooks-installed` green in both
  after. Their owners commit them with their own work. Unverified: that their full
  checks are then green (other parts may be red for other reasons).
  · added: 2026-10-15

- **su-16 · The pass's render commits in 11 other repos are local, not pushed**
  (applications,
  emailTools, income, chronjobScheduler, data-bridge, hub, usage, hooks, research,
  addon-bench, checks): each owner pushes. After them: applications' check is red
  on its own dev.sh hook list (lists fewer hooks than `.claude/hooks` now holds),
  income's on `test.parts` (3 tests against the old runner's output, parts 1.3.0
  now); both reported to their owners.
  · added: 2026-10-15

- **su-17 · The workspace top's `.claude` repo is dirty**
  (` M settings.json`,
  `?? settings.json.bak`): `--only hooks` there (c4f052e) is refused until its
  owner commits or cleans it. `--no-commit` would render there now.
  · added: 2026-10-15

- **su-18 · Plan steps (PLAN-services §4 step 6.1, §3 G1/G5), built 2026-10-13**
  (`setuplib/steps.py`, `setup plans steps`, `setup plans <dir> --steps`,
  `tests/test_steps.py`). Choices made here, open to the plan owners: (1) a steps
  heading is one whose title STARTS with Steps, Phase or Handoff (a literal prefix,
  so "Phased rollout" or "Handoffs that survive..." count too; say if that is
  wrong); (2) an owner is the leading backticked names before a colon: setup cannot
  read the roster, so a name is not checked against it; (3) G5's "evidence dated
  after the plan's date" is not built: a plan has no defined date field;
  (4) a store item is looked up only through `--todo CLI` (`CLI -C <repo> get <id>`,
  JSON `closed`); without it the step is `unchecked`, never guessed. G2's failing
  rule is held: the gate prints a `note steps:` line counting unplaceable steps and
  never fails on them. On the workspace 2026-10-13: 152 steps, 111 unplaceable
  (most plans carry no owner names yet).
  · added: 2026-10-15

- **su-19 · S2, the render commits itself (PLAN-architecture §11), built 2026-10-13**
  (`tests/test_render_commit.py`). Choices open to Jacob: (1) **a commit the repo's
  own git hooks refuse leaves the render written, unstaged, line `needs-owner`**
  (first built as a rollback; changed the same day on transcripts' report, relayed
  by the coordinator, that a rollback means no render can ever land in a gated
  repo). The four repos with core.hooksPath=.githooks (emailTools,
  tools/context-hygiene, tools/transcripts, tools/wizard) refuse setup's commit
  (commit-msg wants an `Agent:` trailer in a session, pre-commit a recorded check
  pass of that tree), so there the owner runs `./dev.sh check` and commits; the
  next setup run refuses that tree until then. Settles if setup could pass the
  gates itself (an `--agent` trailer, then the repo's check before committing).
  (2) The data component's store, written by the repo CLI, is not in the render
  commit. (3) A node parent whose children are nested repos may list them as
  untracked: the parent then reads dirty; unverified -- settle: `./setup <node>
  --node --dry-run` on a real node and read the commit line. (4) A dry run on a
  dirty tree says `needs-owner` ("a real run would be refused"). (5) **Open for
  Jacob:** addon-bench asks that a run into a dirty tree render and commit only
  the rendered paths (its tree holds his uncommitted wiring-apply settings.json,
  not equal to the proposal). The plan says "refuses to render into a repo whose
  tree is dirty", so that is what is built; `git commit --only` would make the
  narrower rule safe, and it is one condition in `_clean_guard` if he says so.
  (6) An uncommitted deletion of a copy setup would restore is a change git does
  not hold, so it refuses too (tests commit the deletion first).
  · added: 2026-10-15

- **su-20 · The full suite under load, 2026-10-13**
  : one run (42 min, load ~57) had
  `test_contract.LiveContract.test_a_verb_the_check_command_does_not_implement_turns_the_line_red`
  red (gates `failed`, not `drift`); alone it passed in 19 s. unverified: a timeout
  in the checks CLI under load -- settle: rerun the full suite on an idle machine.
  · added: 2026-10-15

- **su-21 · `setup plans show|list|edit` and section status, built 2026-10-09**
  (PLAN-todo-tool
  §9 step 6, PLAN-services §3 step 2). Choices made here, open to the plan owners:
  (a) the status marker is `<!-- status: open|approved|done -->` on the first line
  under a numbered heading. PLAN-todo-tool §9 step 6 fixes the values ("a `status:`
  per section (open, approved, done)") but not the form; an HTML comment keeps it out
  of the rendered plan. 0 of the 308 numbered sections in the top-level plans carry
  one today, so `setup plans list` shows them all as unstated until planners add them. (b) `show` puts `digest <sha256>` on stderr so stdout stays the section;
  a caller that merges the streams gets it as a last line. (c) An edit into a CRLF plan
  keeps every byte outside the section but writes the replacement's own lines with LF
  (except its last line end). (d) The digest is re-checked just before the write by the
  same `stale()` the first check uses; no test isolates that second call (the window
  between the gate and the write cannot be opened from a test without a hook in the
  code). (e) An edit cannot add a section (a replacement with a new heading at its
  level is refused) and cannot touch an unnumbered heading such as `## Setup component`.
  · added: 2026-10-15

- **su-22 · `./dev.sh check` red on 2026-10-09 from tools/hooks' uncommitted work**
  (reported
  in the dispatch report, not fixed): `source/hooks/store-guard.sh` (untracked there)
  made the hooks dependency's `list --json` exit 1, so `self` and `mutants` were
  BASELINE-RED here. Same root as "The hook source is the dependency's working tree"
  below. `.claude/settings.json` here is also modified and not by this session; left
  unstaged.
  · added: 2026-10-15

- **su-23 · Hook-copy re-render 2026-10-09 (dispatched, Jacob's "Yes I approve all"), partial.**
  `--only hooks --rebuild` run and committed+pushed (rendered paths only) in addon-bench,
  applications, emailTools, income, knowledge-base, chronjobScheduler, data-bridge,
  scripts, site-scrapers, tools/setup; hooks moved to e2242bc mid-task (test-no-inline-blobs),
  re-rendered again in all of those but data-bridge (refused, exit 2: its own uncommitted
  test-no-inline-blobs.sh, another agent's, now differs from the source). `./dev.sh check`
  here is red only from the hooks fault (store-guard.sh unregistered in tools/hooks
  source/settings.json, so the proposal omits it): `hooks` gate, two test_userscope
  tests, and their BASELINE-RED mutants. Second pass at hooks eb09868: tools/hooks, hub,
  todo, usage rendered and committed; transcripts rendered, left uncommitted (stamp gate).
  `hooks copies` then: 14 of 19 pass. Still differing, each a Jacob/owner step:
  tools/checks (untracked store-guard.sh/test-store-guard.sh byte-equal to hooks b393ccd,
  an old render; needs `--overwrite-uncommitted`, which the classifier denied and the
  dispatcher reserved for Jacob); data-bridge, context-hygiene, wizard (refused, exit 2:
  an uncommitted test-no-inline-blobs.sh byte-equal to hooks 05a5ae4, an Oct 8 render
  nobody committed; its owner commits or discards it, then `--rebuild`); top level (not
  a git repo, and its .claude/ is harness's: skipped). The hub commit 03f33d2's message
  names dd23d32 (a tools/hooks .claude commit) instead of source eb09868; content correct.
  · added: 2026-10-15

- **su-24 · mutate.py leaves runs behind when killed.**
  5 `.mutants/run-*` folders from Oct 4-5
  (515M; no unwritable dirs, so not a permission failure: most likely killed before its
  `finally`) were removed 2026-10-09. `shutil.rmtree(tmp, ignore_errors=True)` would also
  hide a real failure. Open: sweep stale `run-*` at the start of a run (none running),
  and report a cleanup that left files rather than ignoring it.
  · added: 2026-10-15

- **su-25 · check-partial in `gates.contract` (asked by checks, 2026-10-09; open).**
  checks'
  TODO asks setup's contract list (components.json, today `check-json, accessor,
  services-valid, registry-matches, rendered-matches`) to name `check-partial`. Not added:
  no repo meets its contract yet, so every `--checks` run would read it UNCHECKED; hinges
  on whether an UNCHECKED contract gate should fail setup's checks line (PLAN-small-tasks §6).
  · added: 2026-10-15

- **su-26 · hooks source test files lack +x.**
  `source/hooks/test-no-secrets.sh`,
  `test-primary-guard.sh`, `test-push-gate.sh` are 100644 in tools/hooks; setup renders
  copies +x, so tools/hooks' own `.claude/` copies read `mode` on every `--rebuild`.
  Reported to hooks in the 2026-10-09 hand-back.
  · added: 2026-10-15

- **su-27 · githooks (PLAN-hard-gates §7 phase 2), built 2026-10-05; decisions for Jacob.**
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
  · added: 2026-10-15

- **su-28 · §7.11 data component, built 2026-10-05; three parts of §7.11 not built here.**
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
  · added: 2026-10-15

- **su-29 · §7.12 built 2026-10-05: the hooks component renders from the hooks dependency**
  (`dependencies.json`, `setuplib/deps.py`, `setup audit deps`). This settles three
  old items: reading `hooks list --json`, defaulting the source to tools/hooks/source
  (the data-bridge "6 unchanged of 6" against a stale copy), and the content-audit
  collision (dependencies.json is exempt from content and gated by `audit deps`).
  Also fixed: `setup <repo> --dry-run` on an old six-file repo said "0 installed, 6
  unchanged of 6" (the income report); it now lists the 22 files the listing names
  (`test_old_six_file_repo_gets_the_rest_installed`). Still open, below.
  · added: 2026-10-15

- **su-30 · Drifted hook copies: `--rebuild` without `--node` built 2026-10-05 (§7.12, Jacob's yes).**
  Per repo: `./setup <repo> --only hooks --rebuild` from the workspace top, then
  the owner reviews `git diff` and commits (setup never commits there). Not run on any
  real repo here (the dispatcher routes it per owner). Choices made, open to Jacob:
  (1) the uncommitted-work guard refuses the whole run (exit 2, nothing written) rather
  than keeping the one file, so an owner sees it before anything moves; it counts only
  files the listing renders in scope that differ from the source (an owner's own hook
  beside them, or a dirty copy already equal to the source, never blocks); untracked
  and ignored copies count as uncommitted (git cannot restore them). (2) A dry run with
  `--rebuild` refuses too (it predicts the real run). (3) A copy differing only in its
  executable bit is kind `mode`, fixed by `--rebuild` too. (4) Every run now prints a
  line per hook file that differed (a new repo's whole render collapses to one line in
  text; `--json` `hook_files` lists each). Moot for any hook user scope covers.
  (5) The scope is a rule, not a folder list: a file the listing renders into a folder
  directly under `.claude/` (components.json `scope_root`), because the direction audit
  forbids setup's code and data to name the delegation layer's library folder by path;
  `test_every_file_the_listing_renders_is_in_scope` fails if the hooks tool adds a
  destination outside it.
  · added: 2026-10-15

- **su-31 · An active core.hooksPath no longer gets setup's gates while unready**
  (fixed
  2026-10-05, from emailTools' §7.12 step 2 run: setup at 13c6691 would have written
  commit-msg into its active `.githooks/` with git-stamp unregistered, refusing every
  session commit, setup's own output first). Now withheld (`runs` in components.json,
  tests `test_an_active_hooks_path_*`). Probe the same day, `git config core.hooksPath`
  in the 16 locations `hooks copies ../..` names: only emailTools has it set (its own
  `.githooks/pre-commit`); 12 others hold an inert `.githooks/commit-msg` from earlier
  runs (hooksPath unset). emailTools' githooks line stays `drift`: its own pre-commit is
  not the template, and merging the two is its owner's call. Open: a repo's own hook in
  `runs` is never wrapped or chained; whether setup should ever chain is undecided.
  · added: 2026-10-15

- **su-32 · Other repos owe a reinstall (§7.12 step 2, dispatched per owner).**
  `hooks copies
  <top> --gate <loc>` showed ~18-21 non-ok files per location before this change;
  `setup <repo>` now installs the MISSING ones. Not run here (the brief: step 2).
  · added: 2026-10-15

- **su-33 · 7 hooks here run only once Jacob applies the proposal.**
  `./setup .` rendered the
  dependency's 10 hooks and 2 libraries; `.claude/settings.json` (Jacob's) registers 3,
  so `./dev.sh hooks` prints 7 `PENDING` lines and passes. Settle: Jacob runs `cp
  .claude/settings.proposed.json .claude/settings.json` here.
  · added: 2026-10-15

- **su-34 · The checks dependency is named but not read yet.**
  `dependencies.json` names
  tools/checks so a future `checks run .` in the stub can resolve it; nothing in code
  consumes it today (`_used_by` says so). `audit deps` still gates it.
  · added: 2026-10-15

- **su-35 · The hook source is the dependency's working tree, not a commit.**
  Another agent's
  uncommitted edit in tools/hooks/source is what setup installs (and, since `--rebuild`
  without `--node`, what it overwrites a drifted copy with: this matters more now). Options: install from
  `git show HEAD:` in the dependency, or refuse a dirty source. Hinges on whether a
  hooks agent's in-progress edit should ever reach other repos. Was live 2026-10-08
  (a dirty prefer-recipes.sh in the source turned every repo's hooks line to drift);
  that edit landed (tools/hooks 978e6cb..05a5ae4) and this repo's four copies were
  re-rendered with `--only hooks --rebuild` the same day. The decision stays open.
  · added: 2026-10-15

- **su-36 · `--user-scope` has no default**
  (built 2026-10-04, decision 19). The workspace run
  is `./setup <path> --user-scope <(cd tools/hooks && ./hooks copies .. --json)`; without
  it the hooks line says "user scope not checked" and behaviour is as before. A default
  would name the sibling tool: same dependency decision as above.
  · added: 2026-10-15

- **su-37 · The coverage rule is a second copy of tools/checks' `hooks-installed` rule**
  (`_coverage` and `_user_scope_shape` in setuplib/core.py), not a shared helper:
  setup may not import a sibling tool (content/direction audits; the dependency
  decision above), and checks' rule lives in a check script that runs on import.
  Gated: the rule's cases are tests here with mutants (tests/test_userscope.py), and
  the shape by a live test that runs the real `hooks copies --json` against scratch
  user settings (`hooks userscope --out` into a temp folder, HOME pointed there too).
  NOT gated: that the two copies agree by meaning if checks' rule changes. Settle
  when the dependency decision lands (then both read one helper), or checks exposes
  the rule in checkslib and a workspace test here calls both on one fixture.
  · added: 2026-10-15

- **su-38 · After Jacob applies user scope, every repo still registering the shared hooks per repo runs them twice**
  until its settings.json drops them. Setup's proposal does
  that only when run with `--user-scope` on each repo (the proposal is still his to
  apply). This repo too: its own `./dev.sh hooks` REQUIRES each copy registered in
  `.claude/settings.json`, so applying the drop here turns that gate red. Needs a
  decision once user scope is on: `dev.sh hooks` accepts user-scope coverage (read
  from the same report) or keeps per-repo registration here deliberately.
  · added: 2026-10-15

- **su-39 · Plug-ins whose registration runs from below the registry's root fail**
  (built
  2026-10-04, `--plugins`): tools/hooks gives one `registration`, with a command
  relative to the workspace top, so it is correct only for applies_to `repos:.`. A
  plug-in applying to another repo (or `all`, on any repo but the top) is `failed`
  with the reason, never a guessed path. Hinges on tools/hooks giving a per-repo
  registration if one is ever needed (none is today: kb-pointers is `repos:.`).
  · added: 2026-10-15

- **su-41 · `--plugins` has no default.**
  The workspace run is `./setup . --plugins <(cd
  tools/hooks && ./hooks plugins --json)` from the top; without the flag the hooks line
  says "plug-in hooks not checked". A default would name the sibling tool: same
  dependency decision as above.
  · added: 2026-10-15

- **su-43 · Hook copies here are a ninth copy.**
  `tools/setup` is now in site-scrapers'
  `check-hooks.sh` DECLARED (seen 2026-10-04), and `hooks copies` in tools/hooks
  compares every copy by meaning. unverified: knowledge-base's copy of that check
  declares it too -- settle (from knowledge-base): `grep -n tools/setup check-hooks.sh`.
  · added: 2026-10-15

- **su-44 · `--github` is public by default**
  (the dispatcher's brief and PLAN-tools-folder),
  while PLAN-repo-setup §2 says private. Followed the brief; the plan text is the
  dispatcher's to update.
  · added: 2026-10-15

- **su-45 · `audit-terms.json` `roster_names` is a copy of the roster**
  (not read from it:
  the direction audit forbids that). Probe run 2026-10-04: the roster's agent
  names that are not also repo names are exactly the seven listed (harness,
  deep-work, dispatcher, planner, email-tools, job-import-scripts,
  cron-scheduler); the rest are repo names the content audit discovers. Not stale
  today; re-probed 2026-10-08 (`agents.sh list`, 21 agents, against the 16 repos
  `audit content` discovers): still exactly those seven. Retire it when a caller runs tools/checks' `no-roster` here with the
  names (`checks all --names`, reported to harness by checks); `checks.json`
  already makes that run green (checked 2026-10-04 with the roster's names).
  Until then, re-run the probe on each roster change.
  · added: 2026-10-15

- **su-46 · A root `.gitignore` negation with a pattern in it (`!keep*.txt`) still blocks the append as drift**
  (2026-10-04): literal negations are now tested by git in a
  scratch repo (as a file and as a folder), but a pattern names no single path, and
  a representative path would be a guess. No workspace `.gitignore` holds a
  pattern negation (probe: `grep -n '^!'` over them, 2026-10-08): addon-bench and
  site-scrapers hold literal ones (`!.env.example`, `.sample`, `.template`), which
  do not block (`setup <repo> --dry-run --only ignore`: unchanged / installed).
  Revisit if a pattern negation appears.
  · added: 2026-10-15

- **su-47 · The negation test covers the negated path itself, not files inside a kept folder**
  (decided 2026-10-04): after `build/*` and `!build/keep/`, an appended
  `*.bak` ignores `build/keep/x.bak`, which is the baseline doing its job, not an
  override (the negation's last match is the folder, not the file). Hinges on
  whether an owner ever means "keep everything in here" by a folder negation.
  · added: 2026-10-15

- **su-48 · `check --json` validated by subprocess, not by a vendored schema**
  (2026-10-05).
  The stub's `--json` is held to a reviewed fixture in `tests/fixtures/` anywhere;
  this repo's own is the shared runner's (`devtools/parts.py`, since 2026-10-15:
  `devtools/checkjson.py`, the second emitter, is gone), held to a canned
  three-part suite; both are held to the real `check-json` validator (the shared
  checks CLI, run on scratch repos) in the workspace, with the old `{"ok","error"}`
  shape as the counterfactual. No copy of the schema or its validator lives here.
  Cost: a schema change upstream is caught only in the workspace.
  · added: 2026-10-15

- **su-49 · Repos set up before 2026-10-05 keep the old stub's `{"ok": false, "error"}`**
  :
  setup never overwrites `dev.sh` (an existing stub is `needs-owner`). Probe run
  2026-10-05, `grep -l SETUP-STUB */dev.sh */*/dev.sh` from the workspace top: none
  carry the stub today, so nothing to migrate (re-run 2026-10-08: still none).
  · added: 2026-10-15

- **su-50 · A created repo whose render is empty gets no settings.json**
  (§7.9, built
  2026-10-05). With `--user-scope` covering every shared hook and no plug-in applying,
  nothing is missing, so the hooks line is `unchanged` and no file is written or
  committed. §7.9 says the file also holds "the permission mode", but the render (the
  source settings.json) carries hooks only, so a created repo carries no permission
  mode either. Hinges on: whether every created repo must carry a settings.json (then
  write the empty render too) and whether a permission mode belongs in the source.
  · added: 2026-10-15

- **su-51 · PLAN-repo-setup §2 and §7.6 still say setup only writes `settings.proposed.json`**
  ;
  §7.9 is the exception, built here. The plan text is the planner's to reconcile.
  · added: 2026-10-15

- **su-52 · node.json is read twice: by setuplib/node.py and by tools/checks' contract**
  (built
  2026-10-05, §7.5/§7.10). Setup may not import a sibling tool, so `load` mirrors
  checks' `schema/node.schema.json` and its x-rules; the live tests (test_node
  LiveChecks: `checks run` on every repo of a two-level tree, and `checks one
  rendered-matches|regenerate` ok on a scaffold, fail on a committed edit) hold the
  readings together, both ways. Built against checks' then-UNCOMMITTED node schema
  (96ceef9 plus their working tree, 2026-10-05). One rule is setup's own: a child
  inside another child is refused (checks accepts it); a record glob matching nothing
  is not flagged (as in checks).
  · added: 2026-10-15

- **su-53 · Two comparers of a rebuild exist by design**
  : setup's per-file report and checks'
  regen engine (which distrusts the generator and counts from git and bytes). Only
  `failed` exits 1 here; drift and unaccounted are progress, `regenerate` is the gate.
  · added: 2026-10-15

- **su-54 · A generated file setup does not render is `failed`**
  : node.json's one `rebuild`
  is setup's, so a second generator (a file another tool renders) has no place yet.
  Hinges on the plan saying how a node composes generators.
  · added: 2026-10-15

- **su-55 · In checks' clone a plug-in registered at the top reads as drift**
  : the render's
  path is the clone's (`stands_for`), so `repos:.` matched against the registry root
  fails there. CHECKS_ORIGIN is deliberately not read (coupling). Unverified until a
  node with a plug-in exists -- settle: `checks one regenerate .` on that node.
  · added: 2026-10-15

- **su-56 · Should a parent's .gitignore list its child paths?**
  Today a nested child shows as
  untracked `child/` in the parent and both readers skip it as a child. Not decided.
  · added: 2026-10-15

- **su-57 · A node with children needs a registry**
  (checks' registry-matches): settled
  2026-10-05 (§14.8). Setup renders `registry.proposed.json`; the fixtures copy it to
  the registry node.json names (Jacob's step) and pass `checks run` on every repo.
  · added: 2026-10-15

- **su-58 · §14.8's `cli.json` skeleton `{store, cli, verbs: []}` is not installed**
  (2026-10-05).
  No skeleton passes checks' cli.schema.json (`store` minLength/minItems 1, `cli`
  executable), and their `accessor` accepts no store with no cli.json, so writing one
  would turn every new repo red for nothing. The `cli` component reports `none`
  ("a repo with a store adds {store, cli, verbs}"). Hinges on the planner: change the
  plan's table row, or checks accepts an unfilled skeleton as needs-owner.
  · added: 2026-10-15

- **su-59 · The registry renders only `services`**
  (2026-10-05): §14.6 also gives a registry
  roles, owners and the server entry, which have no defined shape here (and roles are
  the roster's, which setup must not read). Hinges on the hub's registry plan.
  · added: 2026-10-15

- **su-60 · A fresh node with children exits 1 under `--checks` until Jacob applies the registry proposal**
  : registry-matches is red (children, no `registry`), and that is
  the true state; the registry line says `needs-jacob` with the copy command.
  · added: 2026-10-15

- **su-61 · `check-json` is gated to the audit role in checks, so `checks run` skips it**
  ; the
  gates component runs it by name (`checks one`), since it is a §14.8 contract gate.
  On this repo it takes ~4 min (the full suite); every `--checks` run on a repo with a
  real suite pays it. Hinges on checks (a shape-only mode) or accepting the cost.
  · added: 2026-10-15

- **su-62 · Setup's own run under `--checks` is red**
  (2026-10-05, before this commit):
  `hooks-installed` fails, `.claude/hooks/ask-first.sh` missing here (the shared source
  has a hook this repo's copies lack), and `check-json` errored (exit 1) while this
  suite was mid-change. Re-checked 2026-10-08 with `../checks/checks run .` (not
  `./setup . --checks`, which could set core.hooksPath here: githooks decision (5),
  Jacob's): ask-first.sh is no longer missing; `rules-gated` (new since) was red, no
  row for "Keeping these rules in sync", fixed by this repo's own `gates.json` (two
  gate rows; `./dev.sh files` parses it); `hooks-installed` was red on
  prefer-recipes.sh and its test (drift against tools/hooks' then-uncommitted edit).
  Since landed (978e6cb..05a5ae4, tree clean) and re-rendered here 2026-10-08 with
  `./setup . --only hooks --rebuild` (Jacob's yes for drifted repos, same day): four
  files rewritten (logic), no-inline-blobs.sh, prefer-recipes.sh and their tests.
  Not re-run under `checks run .` since.
  · added: 2026-10-15

- **su-63 · The `parts` component, built 2026-10-10**
  (top TODO Q6, PLAN-small-tasks §7
  step 2). Choices made here, open to Jacob and the checks owner:
  (a) destination `devtools/parts.py`: devtools/ exists in 15 repos, no `parts.py`
  anywhere yet; components.json `parts.file` is the one place to change it.
  (b) compared by meaning with this repo's own `setuplib/pymeaning.py` (AST dump,
  docstrings included), not a comparator from checks: checks has none. Better
  owned there (`checkslib` exposing `meaning()`, named as the checks dependency's
  `comparator`), as hooks owns hookslib.copies; then pymeaning goes.
  (c) in the node `render` list: a new folder's scaffold commits the copy, so
  `--node --rebuild` must regenerate it byte for byte (test_node's SCAFFOLD). A
  node.json written before 2026-10-10 does not list `devtools/parts.py` among its
  generated files, so its rebuild ignores the copy until the owner adds it.
  (d) a lone clone: parts is `failed` (no source), like hooks without --hooks-from.
  (e) the stub dev.sh (templates/) does not call the runner yet, nor does this
  repo's: the copy is installed, nothing runs it. That wiring is §7's next step.
  (f) no `parts-installed` gate in checks; the agreement is gated here only for
  this repo (`ThisRepo`, mutant `runner-copy-stale`). A checks gate would cover
  every repo: suggest it to checks.
  Copies rendered so far: this repo only. Other repos get it on their next `./setup`.
  · added: 2026-10-15

## Unconfirmed suspicions

- **su-101 · test_two_level_tree flaked once under a parallel check run**
  2026-10-19: tests.test_node.Node.test_two_level_tree_from_an_empty_folder failed once (second --node run exit 1, 9.8s) while a full ./dev.sh check ran in parallel; five reruns alone passed. Cause unknown; the failing component was not captured
  · probe: python3 -m unittest tests.test_node.Node.test_two_level_tree_from_an_empty_folder, repeated
  · files: tests/test_node.py
  · added: 2026-10-19

## Reported to other owners

- **su-65 · checks (2026-10-05, via the dispatcher):**
  checks (2026-10-05, via the dispatcher): PLAN-hard-gates §3 row 6 says the
  pre-commit runs no-secrets on the *staged diff*; `checks one no-secrets <repo>`
  scans tracked plus would-be-committed working-tree files, so a secret staged and
  then deleted from the working tree is not seen. The githooks pre-commit calls it
  as is (`one no-secrets <top> --json`). Expected: a `--staged` mode, or the plan
  amended. To hooks: `git commit --no-verify` skips the githooks gates; git-stamp.sh
  (or phase 3) is the only place that can refuse it. (Settled 2026-10-05, §7.12: this
  repo now renders git-stamp.sh and write-ledger.sh from the hooks dependency, and a
  new repo is wired from its settings.json.)
  · reported to: checks on 2026-10-05 (no counterpart yet)
  · added: 2026-10-15

- **su-66 · checks (2026-10-05, via the dispatcher):**
  checks (2026-10-05, via the dispatcher): setup now consumes node.json
  (`setuplib/node.py` mirrors schema/node.schema.json), so a schema change there
  needs a matching change here; the live tests in tests/test_node.py go red if not.
  Divergence: setup refuses a child inside another child, checks accepts it.
  `setup . --node --rebuild` exits 1 only on a failed line (their engine reads any
  non-zero exit as a `rebuild` finding, which is then correct).
  · reported to: checks on 2026-10-05 (no counterpart yet)
  · added: 2026-10-15

- **su-67 · checks (2026-10-05, via the dispatcher):**
  checks (2026-10-05, via the dispatcher): `checks one check-json tools/setup`
  took 242.7 s against check-json's 280 s limit (an earlier run, 228.5 s): this
  suite (123 tests + 67 mutants) is near the cap and will cross it as mutants
  grow. PLAN-agent-groups §4.4 already says raise the limit; this is the evidence.
  Also: check-json proves shape only. This repo's `--json` once printed a valid
  report with every gate after `hooks` reading `fail` and no finding, from a bash
  variable leak (fixed here, gate runs in a subshell, mutant `own-json-gate-clobbers`);
  check-json passed it. Not a bug in checks, a reason for each repo's own wiring test.
  · reported to: checks on 2026-10-05 (no counterpart yet)
  · added: 2026-10-15

- **su-68 · knowledge-base (2026-10-04, via the dispatcher):**
  knowledge-base (2026-10-04, via the dispatcher): its TODO observation that
  this CLAUDE.md's "Keeping these rules in sync" names only `../../CLAUDE.md` is
  stale (it names all nine hand-synced copies; `tests/test_sync_list.py`'s live
  comparison passes). The section's prose was reworded (commit "CLAUDE.md: sync
  section"): it now says why the block-carrying tool folders stay out of the list.
  Their item can be closed.
  · reported to: knowledge-base on 2026-10-04 (no counterpart yet)
  · added: 2026-10-15

- **su-69 · checks (2026-10-04, via the dispatcher):**
  checks (2026-10-04, via the dispatcher): take the mutant runner as `checks
  mutants [PATH]` (td-9 decision above; start from tools/todo's copy, which has
  the `edits` list). And to todo: td-9 is decided that way, so it waits on checks.
  · reported to: checks on 2026-10-04 (no counterpart yet)
  · added: 2026-10-15

- **su-71 · hub (2026-10-04, via the dispatcher):**
  hub (2026-10-04, via the dispatcher): the `ignore` component is new (fixes the hub
  scaffold leaving `.claude/settings.proposed.json` untracked and writing no
  `.gitignore`). Every repo set up before it lacks the baseline entries:
  `tools/hub` first (its owner re-runs `./setup tools/hub` from the workspace
  root and commits the appended `.gitignore`), then the rest on their next run.
  · reported to: hub on 2026-10-04 (no counterpart yet)
  · added: 2026-10-15

- **su-89 · Practice ids resolve against gates.json rules[].id; step 7.2 (tl-283) has not landed PRACTICES rows there yet**
  setup plans resolves each ## Practices id and each approved decision's gate: row in tools/checks/gates.json rules[].id (dependencies.json checks.registry). If 7.2 puts practice rows under another key or file, every cited id fails as unresolved; checks to confirm the rows keep rules[].id, or tell setup
  2026-10-19 checks' tl-321 report (checks 18489e8, relayed by the coordinator): practice ids live at gates.json practices.rows[].id; rules[].id holds the CLAUDE.md section rows. So setuplib/practices.py must resolve ## Practices ids against practices.rows[].id, not rules[].id
  · reported to: checks on 2026-10-18 (no counterpart yet)
  · files: setuplib/practices.py, dependencies.json
  · added: 2026-10-18

- **su-92 · Plans that create a tool must declare it in a Creates header line**
  setup plans (setuplib/fit.py, PLAN-architecture §9 step 2) requires a ## Fit heading only in a plan not done that declares > **Creates:** `<path>` in its first 25 lines; which plans create a tool is never guessed from prose, so an undeclared one is not seen. On 2026-10-18: 0 of 36 live plans declare it. The plan template for a new tool should carry the line
  · reported to: planner on 2026-10-18 (no counterpart yet)
  · files: setuplib/fit.py
  · added: 2026-10-18

## Plan steps

- **su-88 · `setup`**
  made by todo sync-plans 2026-10-18 from PLAN-hard-gates.md §7 step 2:
  **`setup`:** the `git-hooks` component (`core.hooksPath`, `commit-msg`, `pre-commit` calling the repo's `./dev.sh check` stamp and `no-secrets`), the `commit-msg` hook stamping his own terminal commits (§8 answer 2), `needs-jacob` for the registrations. ~40k.
  · status: waiting-jacob
  · waits on: approval
  · tags: plan:PLAN-hard-gates.md§7
  · plan pins: PLAN-hard-gates.md§7 as of 2026-10-18 (sha256 d10974a2ca5d)
  · plan step: PLAN-hard-gates.md §7 step 2, hash 2b5f6c4f0a6b
  · added: 2026-10-18

## Notes

- **su-64 · 2026-10-10, via the dispatcher (top TODO Q6 (b)):**
  2026-10-10, via the dispatcher (top TODO Q6 (b)): `./setup <repo> --only hooks
  --rebuild` re-rendered the drifted hook copies in 14 repos (addon-bench,
  applications, emailTools, income, knowledge-base, scriptingTools/chronjobScheduler,
  scriptingTools/data-bridge, scripts, site-scrapers, tools/hooks, tools/hub,
  tools/setup, tools/todo, tools/usage); each now clean in `hooks copies` and
  `checks one hooks-installed` ok. Committed here only (a066d36); the other 13 hold
  the uncommitted render (store-guard.sh, test-no-inline-blobs.sh,
  test-store-guard.sh, lib/extra-stores.sh) for their owners to commit. The four
  skipped then (tools/checks, tools/context-hygiene, tools/transcripts, tools/wizard)
  were re-rendered later that day once their owners were idle: every uncommitted
  `.claude/hooks`/`.claude/lib` file there equalled, byte for byte, some committed
  version of its source file in tools/hooks (stale renders, no hand work), so
  `--rebuild --overwrite-uncommitted` ran; each now `checks one hooks-installed` ok,
  nothing outside `.claude/hooks` and `.claude/lib` changed, nothing committed there
  (wizard's index still holds its older staged test-no-inline-blobs.sh: its owner
  stages the render). `hooks copies` now differs only at the workspace top (not a
  repo, harness-owned). Possible feature, not built: the refusal could treat an
  uncommitted copy equal to a committed source version as safe to overwrite, which
  is what was checked by hand here. To hooks and Jacob: this repo's `hooks` gate, two
  test_userscope tests and 3 mutants' baselines are red because store-guard.sh is
  not registered in tools/hooks `source/settings.json` (already in hooks/TODO.md);
  that file needs Jacob's yes.
  · added: 2026-10-15

- **su-70 · 2026-10-04, via the dispatcher, to the planner:**
  2026-10-04, via the dispatcher, to the planner: the check component and §9 (1)
  both need setup to name a sibling tool, which its content audit forbids; the
  proposal is under Open decisions.
  · added: 2026-10-15

- **su-86 · To setup: check-pass refuses every commit while Jacob's uncommitted .claude/settings.json is in the tree**
  2026-10-15 ~21:30: ./dev.sh check passed 24 of 24 and recorded tree f606de85c194, which includes the uncommitted .claude/settings.json change (made 20:45 by someone else; it now equals settings.proposed.json, so likely Jacob's wiring --apply -- unverified). git commit of TODO.md, todo.json, todo-history.json was refused by .githooks/pre-commit (check-pass match: staged tree 7db2b50d7982 != f606de85c194). Q6b says settings.json stays uncommitted and untouched, so no commit can pass here until it is committed, stashed, or check-pass leaves it out. The store edits stay staged, uncommitted.
  · parent: ch-66
  · work: code
  · size: M
  · done when: check-pass (setup's githooks) lets a commit through when the only unstaged change is .claude/settings.json Jacob owns, or Jacob commits his settings change; the staged store edits here are then committed
  · added: 2026-10-17

- **su-93 · To setup: data-bridge/.claude/settings.json has an uncommitted render adding git-funnel.sh and two store-guard.sh entries**
  From data-bridge (6.3/6.4). Probe: git -C scriptingTools/data-bridge diff .claude/settings.json. Expected: committed by setup, or reverted, with store-guard listed once.
  · parent: tl-306
  · work: code
  · size: S
  · done when: diff clean; store-guard registered once
  · added: 2026-10-19

- **su-94 · To setup: check-pass refuses a partial commit of an owner-only file (settings.json) in transcripts and context-hygiene because their trees hold other sessions' WIP (su-84/su-86)**
  From setup's own run (tl-285 session); noted, unapproved. Expected: check-pass match tolerates a partial commit of an owner-only file.
  · parent: tl-309
  · work: code
  · size: M
  · done when: settings.json can be committed in both repos
  · added: 2026-10-19

- **su-95 · To setup: tools/hub fails hooks-installed: ledger.sh, store-guard.sh, test-store-guard.sh drift from the hooks source (not covered by user scope)**
  From hub (tl-316). Probe: tools/hub ./dev.sh check, 'checks' part. Expected: green after setup tools/hub --only hooks --rebuild. Same drift family as tl-278 (hooks) and tl-309.
  · parent: tl-320
  · work: code
  · size: S
  · done when: hub checks part green
  · added: 2026-10-19

- **su-100 · checks' sqlstore.py copy waits on a 'step 10.2' that does not cover it**
  checks' tl-321 report says checks holds a copy of todo's sqlstore.py (held equal by a test) until 'your step 10.2 settles where the shared copy lives'. PLAN-architecture §9 step 10.2 (tl-313, services.json description) says nothing about sqlstore and no PLAN names it: the reference resolves to no step. Ask the coordinator which step owns the shared copy's location
  · added: 2026-10-19

- **su-102 · Workspace repos show services drift until step 10.3 adds their descriptions**
  Since tl-313 an existing services.json without a description is services drift (exit 1) on ./setup <repo> (not with --only another component). Every workspace repo lacks one until step 10.3 drafts them; the shared checks read the same absence as a lag (registered), setup as drift, per PLAN-architecture §9 step 10.2's wording
  · done when: step 10.3's drafts applied in each repo; ./setup <repo> --dry-run shows services unchanged
  · added: 2026-10-19
