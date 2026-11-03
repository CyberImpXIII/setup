<!-- rendered by todo from todo.json (71 open, 69 closed in todo-history.json; seal ce7444909dfb): do not edit by hand, `todo check` fails on a hand edit. Change items with the todo CLI; a hand edit is recovered with `todo import`. -->
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
  2026-10-23 (tl-601): a full ./dev.sh check here went 31 of 45, 12 test parts, self and mutants red, every one on 'hooks list --json --source ... exited 1: lib/browser-drivers.sh: no test': another session's uncommitted, untracked files in tools/hooks/source (browser-drivers.sh 14:55, its test added 15:05). Counterfactual: the same listing exits 0 at 15:1x once the test file exists, setup's tree unchanged throughout. The scaffold setup tools/tab-digest committed at 14:54:07, before every one of those edits' mtimes, so it holds hooks' committed state (its prefer-recipes.sh equals hooks HEAD by non-comment lines; no 'browser driven through Bash' registration).
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
  · approved: jacob 2026-11-03: Jacob, planner window, 2026-11-03: dt-46 row 1 answered default-push (one setup dispatch, tl-558/su-111, PLAN-services.md §3 F3 'Default push, the fix')
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

- **su-118 · commit.sh does not push because `git config funnel.push` is unset, so 700aafb, 3458fd7 and c54553...**
  reported from emailTools to tools/setup in dispatch toolu_01Jp4vUxgyWQ3r1EbCfDee4Z, filed from the dispatch ledger by the delegation layer's report filer: commit.sh does not push because `git config funnel.push` is unset, so 700aafb, 3458fd7 and c545539 are local only -- input: `.claude/bin/commit.sh` in emailTools -- expected: a sanctioned push path
  · parent: tl-618
  · added: 2026-10-23

- **su-119 · re-render every copy of prefer-recipes.sh, test-prefer-recipes.sh, the new lib browser-drivers.sh...**
  reported from tools/hooks to tools/setup in dispatch toolu_01NEFfK5YJcieSwXMmoYfuKt, filed from the dispatch ledger by the delegation layer's report filer: re-render every copy of prefer-recipes.sh, test-prefer-recipes.sh, the new lib browser-drivers.sh and the Bash registration in each settings.proposed.json (tl-562) -- input: tools/hooks source at 34d6cfd -- expected: hooks copies shows no DRIFT/MISSING for them
  · parent: tl-630
  · added: 2026-10-23

- **su-122 · tools/hooks has no push record, so nothing committed through the verb reaches origin -- input: gi...**
  reported from tools/hooks to tools/setup in dispatch toolu_013Bac7MbeDv4uZR9VTvAvbs, filed from the dispatch ledger by the delegation layer's report filer: tools/hooks has no push record, so nothing committed through the verb reaches origin -- input: git -C tools/hooks config --bool funnel.push -- expected: true (then `tools/hooks/dev.sh commit --push`); also re-render bin/commit.sh, git-funnel.sh and test-git-funnel.sh everywhere (until then an installed verb answers --push with usage).
  · parent: tl-636
  · added: 2026-10-23

- **su-123 · tools/research `./dev.sh check` red on shared:hooks-installed (5 drifted copies, browser-drivers....**
  reported from tools/research to tools/setup in dispatch toolu_01H5EKRE2f8fWyHowujRQh7J, filed from the dispatch ledger by the delegation layer's report filer: tools/research `./dev.sh check` red on shared:hooks-installed (5 drifted copies, browser-drivers.sh missing) after tools/hooks 34d6cfd and 774780d -- input: cd tools/research && ./dev.sh check -- expected: `./setup tools/research --only hooks --rebuild` re-renders them, then I commit rs-31 and close tl-627.
  · parent: tl-639
  · added: 2026-10-23

- **su-127 · setup fanout renders into a repo nested inside another work tree that no node.json declares (addon-bench's candidate clone of emailTools)**
  Seen 2026-10-15 and again 2026-11-03: `./setup fanout hooks --root <workspace> --dry-run` from tools/setup -> '1 failed, 21 unchanged; failed: ../../addon-bench/candidates/graphify/work/src/emailTools' (hooks drift, 23 installed of 29). work_trees (setuplib/fanout.py:65) includes every nested work tree, and a candidate's clone keeps a .claude/hooks folder, so it counts as declaring the hooks. Moved here from su-9 (tl-669).
  · work: code
  · size: S
  · files: setuplib/fanout.py, components.json, tests/test_fanout.py
  · done when: setup fanout skips a git work tree nested inside another work tree unless the parent's node.json names it a child, and counts it; a test in tests/test_fanout.py with a mutant; the dry run above reports 0 failed
  · added: 2026-11-03

- **su-129 · mutate.py hides a cleanup failure (rmtree ignore_errors) and never sweeps a killed run's leftover run-*/ folder**
  devtools/mutate.py (setup's mutate component source, rendered into other repos) cleans up on exit, ^C and SIGTERM, but only SIGKILL aside (its docstring); its cleanup is shutil.rmtree(tmp, ignore_errors=True) (line 164), which hides a cleanup that left files, and no run sweeps a stale run-*/ left by a killed one (5 such folders, 515M, were removed by hand 2026-10-09). Moved here from su-24 (tl-669).
  · work: code
  · size: S
  · files: devtools/mutate.py
  · done when: a cleanup that leaves files is reported, not ignored; a run removes stale .mutants/run-*/ folders no live run owns; each with a test and a mutant
  · added: 2026-11-03

- **su-135 · nothing runs `setup plans --facts`, which reports 23 failing plan facts**
  Reported 2026-11-03 by the tl-677 inventory (relayed by the coordinator), confirmed the same day: `./setup plans <workspace> --facts` exits 1, 'facts: 23 cited (19 not-declared, 4 not-one-command)'; no dev.sh, check.parts.json, gates.json or .claude hook runs it (grep -rn 'plans.*--facts' .claude tools/*/dev.sh: no hits); only tests/test_facts.py exercises it. A gate that nothing runs reports no error and enforces nothing.
  · work: tooling
  · size: S
  · files: check.parts.json, gates.json
  · done when: a named caller runs `setup plans <root> --facts` (a check part here or the workspace's check), and its 23 findings are each fixed or routed to the plan's owner
  · added: 2026-11-03

- **su-136 · reported to setup: income's devtools/parts.py copy (1.3.0) drifts from the runner (1.6.0), shared and test.parts red**
  2026-11-03 (income agent, tl-670): ./dev.sh check gates 'shared' and 'test.parts' FAIL: 'parts drift: devtools/parts.py: its meaning differs from the source (copy 1.3.0; runner 1.6.0, tools/checks/checkslib/parts.py as committed) ... --rebuild overwrites it'. Not mine to re-render (setup owns the copy): 'setup income --only parts --rebuild'.
  · parent: inc-71
  · work: tooling
  · done when: setup re-renders income's devtools/parts.py to the committed runner and ./dev.sh check shows shared and test.parts ok
  · added: 2026-11-03

- **su-137 · I wrote counterpart su-136 into `/Users/Specter/Desktop/claudeTest/tools/setup/todo.json` via `to...**
  reported from income to tools/setup in dispatch toolu_01NRtif6efm5SH24RLyFxs1Z, filed from the dispatch ledger by the delegation layer's report filer: I wrote counterpart su-136 into `/Users/Specter/Desktop/claudeTest/tools/setup/todo.json` via `todo report`. It is uncommitted, and the drift is already fixed on income's side, so setup can close and commit it.
  · parent: tl-692
  · added: 2026-11-03

- **su-138 · check: test.contract and test.node time out (900s) only under the full parallel suite**
  2026-11-03: three full ./dev.sh check runs (load 79, 79, ~30-50) each 43/45, test.contract and test.node timeout at 900s inside the suite (--jobs 14, beside mutants 1394s and hooks 888s); alone via check --only at load ~50: test.contract ok 356s, test.node ok 421s. Blocks commit.sh (full check) for every setup commit under load; tl-669 store edits uncommitted because of it
  · work: tooling
  · size: S
  · files: check.parts.json, dev.sh
  · done when: ./dev.sh check passes test.contract and test.node in the full suite at the usual load (raise their timeout, or serialise them away from mutants/hooks)
  · handoff: done: timeout_s 2700 for test.contract, test.node and hooks in check.parts.json (probe: 323s/351s alone at load 40, time spread over many tests, so contention not a hang); next: full check via commit.sh with COMMIT_CHECK_TIMEOUT=5400; verify: .progress/check.json state passed, 45/45 (2026-11-03, at 8a5a826)
  · added: 2026-11-03

## Open decisions

- **su-10 · Should setup render a read-only stores.json at a node, built from every owner's cli.json store field, as the hub plan's Setup component asks?**
  PLAN-hub.md on origin/plan/hub
  (63cf780), its Setup component table's `stores.json` row, and PLAN-services.md §3
  step 3 ("Two more from the hub owner", item 1) say setup should render a
  read-only `stores.json` beside hub.json at a node. It would be built from every
  owner's cli.json `store` field, mode 0444, re-rendered on every run, and `drift`
  when it no longer matches. The hub hook and server would both read it. Note:
  `store` is optional in cli.json now (3a3c3db), so a storeless repo adds no row.
  tools/setup has no cli.json of its own yet.
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-services.md §3
  · hinges on: whether the hub's store-read route is wanted in the real workspace now, rather than only against its test fixture
  · recommend: yes
  · today: components.json names no stores.json (0 matches); the hub records it as setup's to render and not built (tools/hub/TODO.md hb-46) and reads a fixture's stores.json in its tests (hb-65)
  · problem: by the hub's own done-when (tools/hub/TODO.md:257), with no stores.json every Read of a store file is a plain Read, so the hub's store-read route does nothing outside its tests
  · added: 2026-10-15

- **su-14 · Should setup's dev.sh stub run the docs index's refresh for its repo (a template slot fed by the docs dependency), as PLAN-knowledge-base §11 'When refresh runs' says?**
  The index's owner asked for its refresh as a step in each repo's `dev.sh check`
  too: not done. dev.sh is the owner's once it exists, and the check template
  cannot name the index's command (content audit); it would need a dependency-fed
  template slot. Also: a declaration naming TODO.md makes a deleted TODO.md the
  docs line's drift (honest, but a second red for one cause). Open for Jacob.
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-knowledge-base.md §11
  · hinges on: whether a repo's changed docs may wait for knowledge-base's own refresh schedule; the stub reaches only repos created from now on, since setup never overwrites a dev.sh
  · recommend: no
  · today: templates/dev.sh names no docs refresh; of the workspace's dev.sh files (one and two levels down) only knowledge-base/dev.sh names kb-docs or knowledge-base; a docs declaration (kb-docs.tsv) exists in 2 repos, tools/setup and tools/tab-digest
  · problem: a doc changed in a repo stays stale in the shared docs index until knowledge-base's schedule runs; a slot in the stub would not reach any existing repo
  · added: 2026-10-15

- **su-19 · Should setup render and commit only its own paths into a repo whose tree holds other uncommitted work (git commit --only), as addon-bench asked, instead of refusing?**
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
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-architecture.md §11
  · hinges on: whether a render commit may land when the repo's check passed on a tree that also held someone else's uncommitted work
  · recommend: no
  · today: _clean_guard (setuplib/core.py:1754) refuses a render into a tree holding other changes; --no-commit renders without committing; the parts fan-out of 2026-10-20 recorded 10 repos refused as dirty (commit 9ab8f80, su-98)
  · problem: a shared change waits in every repo where someone has unrelated uncommitted work, until that owner commits or takes it with --no-commit
  · added: 2026-10-15

- **su-25 · Should setup's contract gate list (components.json gates) name checks' check-partial, so a --checks run fails a repo whose dev.sh reports a partial pass as green?**
  checks'
  TODO asks setup's contract list (components.json, today `check-json, accessor,
  services-valid, registry-matches, rendered-matches`) to name `check-partial`. Not added:
  no repo meets its contract yet, so every `--checks` run would read it UNCHECKED; hinges
  on whether an UNCHECKED contract gate should fail setup's checks line (PLAN-small-tasks §6).
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-small-tasks.md §6
  · hinges on: whether a contract gate few repos meet yet should turn setup's checks line red (c_gates fails the line on a contract gate that reports nothing)
  · recommend: no
  · today: the contract list is check-json, accessor, services-valid, registry-matches, rendered-matches (components.json); checks lists check-partial with applies_to=roles:audit; c_gates (setuplib/core.py:1232) runs each audit-role contract gate by name. unverified: how many repos meet check-partial today -- settle: checks one check-partial <repo> per repo
  · problem: a repo whose check prints a partial pass as success is not caught by setup --checks; adding the gate before repos meet it makes every --checks run read red
  · added: 2026-10-15

- **su-27 · Should the githooks pre-commit keep accepting only a staged tree equal to the one ./dev.sh check passed on (strict), rather than recording the index tree?**
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
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-hard-gates.md §7
  · hinges on: whether an unstaged edit the check saw may ever go into a commit unchecked; the other githooks choices (session marker, merge commits, --no-verify, activation) are in this item's evidence
  · recommend: yes
  · today: templates/githooks/check-pass:89-91 refuses a staged tree that is not the recorded one; pre-commit runs check-pass match (templates/githooks/pre-commit:16)
  · problem: in a repo with the gates on, a partial commit, or any commit while another agent's work sits uncommitted in the tree, is refused
  · added: 2026-10-15

- **su-28 · Should setup --node --rebuild verify each child's store against the data repo (PLAN-repo-setup §7.11's store row), rather than leave that to checks' stores-exported gate?**
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
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-repo-setup.md §7.11
  · hinges on: whether a second comparer of the stores in setup is worth it beside the shared stores-exported gate
  · recommend: no
  · today: c_data (setuplib/core.py:1080) imports a store and has no rebuild row; DATA_REPO arrives only by --data-repo or the environment, and the .claude/local.env loader it would come from does not exist (no .claude/local.env at the workspace top)
  · problem: a node rebuild says nothing about whether its children's stores match the data repo; today only checks' stores-exported says so
  · added: 2026-10-15

- **su-35 · Should a plain `setup <repo>` refuse to render hooks from a tools/hooks/source holding uncommitted edits, as `setup fanout` already does?**
  Another agent's
  uncommitted edit in tools/hooks/source is what setup installs (and, since `--rebuild`
  without `--node`, what it overwrites a drifted copy with: this matters more now). Options: install from
  `git show HEAD:` in the dependency, or refuse a dirty source. Hinges on whether a
  hooks agent's in-progress edit should ever reach other repos. Was live 2026-10-08
  (a dirty prefer-recipes.sh in the source turned every repo's hooks line to drift);
  that edit landed (tools/hooks 978e6cb..05a5ae4) and this repo's four copies were
  re-rendered with `--only hooks --rebuild` the same day. The decision stays open.
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-repo-setup.md §7.12
  · hinges on: whether a hooks agent's in-progress, uncommitted edit may ever reach other repos through a setup run
  · recommend: yes
  · today: c_hooks (setuplib/core.py:446) renders tools/hooks/source as its working tree holds it; setup fanout refuses a dirty source (setuplib/fanout.py:89 source_commit), and the parts and mutate components render the source's HEAD only (components.json lines 37, 39)
  · problem: another agent's half-finished hook edit is copied into whatever repo setup runs on, and every other repo's hooks line then reads drift, as on 2026-10-08 with a dirty prefer-recipes.sh
  · added: 2026-10-15

- **su-58 · Should PLAN-routing-tree §14 (and the hub plan's Setup component) stop promising a cli.json skeleton {store, cli, verbs: []}, since no skeleton passes checks' cli.schema.json?**
  (2026-10-05).
  No skeleton passes checks' cli.schema.json (`store` minLength/minItems 1, `cli`
  executable), and their `accessor` accepts no store with no cli.json, so writing one
  would turn every new repo red for nothing. The `cli` component reports `none`
  ("a repo with a store adds {store, cli, verbs}"). Hinges on the planner: change the
  plan's table row, or checks accepts an unfilled skeleton as needs-owner.
  · status: waiting-jacob
  · waits on: approval
  · pointer: PLAN-routing-tree.md §14
  · hinges on: whether checks would instead accept an unfilled skeleton as needs-owner, which would let setup write one
  · recommend: yes
  · today: c_cli (setuplib/core.py:1073) writes no cli.json and says so; the plans still promise the skeleton (PLAN-routing-tree.md:837, tools/hub/PLAN-hub.md:1309)
  · problem: a planner or the hub reading the plan expects setup to write a cli.json it never writes
  · added: 2026-10-15

## Unconfirmed suspicions

- **su-101 · test_two_level_tree flaked once under a parallel check run**
  2026-10-19: tests.test_node.Node.test_two_level_tree_from_an_empty_folder failed once (second --node run exit 1, 9.8s) while a full ./dev.sh check ran in parallel; five reruns alone passed. Cause unknown; the failing component was not captured
  · probe: python3 -m unittest tests.test_node.Node.test_two_level_tree_from_an_empty_folder, repeated
  · files: tests/test_node.py
  · added: 2026-10-19

- **su-120 · unverified: the own-copy gate and the commit funnel deadlock on every source change -- input: edi...**
  reported from tools/hooks to tools/setup in dispatch toolu_01NEFfK5YJcieSwXMmoYfuKt, filed from the dispatch ledger by the delegation layer's report filer: unverified: the own-copy gate and the commit funnel deadlock on every source change -- input: edit any installed source file in tools/hooks, then run commit.sh -- expected: a path to commit without hand-copying into .claude/
  · probe: edit any installed source file in tools/hooks, then run commit.sh
  · parent: tl-631
  · added: 2026-10-23

- **su-121 · unverified: hook files rendered into site-scrapers/.claude/hooks (ask-first, store-guard and othe...**
  reported from site-scrapers to tools/setup in dispatch toolu_012WkVPPdMzGarGAizJcPN1z, filed from the dispatch ledger by the delegation layer's report filer: unverified: hook files rendered into site-scrapers/.claude/hooks (ask-first, store-guard and others) are not wired in settings.json, so test/hooks.test.js fails on HEAD -- input: `node --test --test-name-pattern="every hook is wired" test/hooks.test.js` on a git-archive HEAD copy -- expected: wired, or the test treats settings.proposed.json as "not applied yet" the way check-hooks.sh does.
  · probe: `node --test --test-name-pattern="every hook is wired" test/hooks.test.js` on a git-archive HEAD copy
  · parent: tl-632
  · added: 2026-10-23

- **su-128 · unproven: the dry-run probe loop's --only filter is gated by no test**
  Unproven since 2026-10-13: the only-runs-everything mutant breaks the run loop's filter (setuplib/core.py:1677); the dry-run probe loop's own filter (setuplib/core.py:1747, `if self.only and c["name"] != self.only`) has no mutant in devtools/mutants.json. Moved here from su-12 (tl-669).
  · probe: in a scratch copy, delete the probe loop's two filter lines and run tests.test_only and tests.test_nocommit: green means nothing gates it
  · work: test
  · size: S
  · files: setuplib/core.py, devtools/mutants.json
  · added: 2026-11-03

- **su-131 · unproven: in checks' clone a plug-in registered at a node's top reads as drift**
  Unproven since 2026-10-05: in checks' clone a plug-in registered at the top would read as drift, because the render's path is the clone's (stands_for) and repos:. is matched against the registry root; CHECKS_ORIGIN is deliberately not read. No node with a plug-in exists to try it on. Moved here from su-55 (tl-669).
  · probe: checks one regenerate <node> on a node that carries a plug-in registered at its top
  · work: test
  · size: S
  · added: 2026-11-03

- **su-139 · unverified: commit.sh's 1800s check bound (COMMIT_CHECK_TIMEOUT) may be below this repo's full ./dev.sh check wall under load**
  2026-11-03 (su-138): mutants alone took 1394s inside a full suite at load 79 and hooks 888s; test.contract/test.node now get 2700s each, so the suite's wall under load can pass 1800s while every part is green, and commit.sh then reports check-failed
  · probe: the wall_s of .progress/check.json after a full ./dev.sh check at load >= 50; > 1800 settles it
  · files: check.parts.json
  · added: 2026-11-03

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

- **su-92 · Plans that create a tool must declare it in a Creates header line**
  setup plans (setuplib/fit.py, PLAN-architecture §9 step 2) requires a ## Fit heading only in a plan not done that declares > **Creates:** `<path>` in its first 25 lines; which plans create a tool is never guessed from prose, so an undeclared one is not seen. On 2026-10-18: 0 of 36 live plans declare it. The plan template for a new tool should carry the line
  · reported to: claudeTest on 2026-11-01 (no counterpart yet)
  · files: setuplib/fit.py
  · added: 2026-10-18

- **su-140 · unverified: parts.py gives no warning when a part uses most of its timeout_s, so a part creeping toward it is seen only when it times out**
  su-138: hooks ran 888s of its 900s in a full suite (2026-11-03) and nothing said so; test.contract/test.node passed earlier runs then timed out at 900s. Suggest: the run's text and progress file name each part that used > 75% of its timeout_s
  · reported to: checks on 2026-11-03 (no counterpart yet)
  · added: 2026-11-03

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

- **su-124 · setup plans: a verb for a plan's unnumbered preamble, so no plan text is edited by hand**
  setup plans edit and add address numbered sections only (setuplib/plans.py:5-8). The planner's memory lets the preamble be hand-edited until a verb exists (interim item in this store, ra-7.2). Wanted: a verb that replaces the text before the first numbered heading, with the same --digest guard.
  · parent: tl-650
  · work: code
  · files: setuplib/plans.py
  · added: 2026-10-31

- **su-125 · To tools/setup: code that reads todo.json or todo-history.json directly will break when todo moves to todo.db (td-60..62); read through the todo CLI or the todo.*.jsonl exports**
  From todo (tl-268). Probe: tools/todo/todo -C /Users/Specter/Desktop/claudeTest migrate --readers (95 lines in 30 files). Expected: readers go through the CLI or exports before the switch.
  · parent: tl-299
  · work: code
  · done when: no direct read of todo.json/todo-history.json remains in this repo, or the todo CLI/export is used instead
  · added: 2026-10-31

- **su-126 · setup spawns the whole environment, the harness included, on a new machine**
  Jacob, 2026-11-02 (external audit ra-13.2): "I think the harness should be able to be \"spawned\" from the setup, so while the harness is the source in our case, I want to be able to download setup and have it set-up everything on a different computer." PLAN-portable-env.md (2026-10-02) has init owned by the harness, calling setup per repo; this turns it around: setup is the one download, and it sets up the harness (.claude) too, from the names record (PLAN-architecture.md §13.1) once one exists on the new machine. The plan's 'Owner: harness for init' line needs Jacob's wording when this is taken up.
  · parent: tl-653
  · work: tooling
  · added: 2026-11-02

- **su-130 · setup's user-scope coverage rule is a second copy of the hooks rule until the staged _coverage change lands**
  setup's _coverage (setuplib/core.py) restates the hooks-installed coverage rule. tools/hooks now carries the verdict in the report (tools/hooks 2de3cfa, 'user scope carries the coverage verdict', user_scope.covered). A change making _coverage read that verdict is staged in this repo, uncommitted, by another session (seen 2026-11-03 09:30: setuplib/core.py, tests/test_userscope.py, tests/test_githooks.py, devtools/mutants.json). Moved here from su-37 (tl-669).
  2026-11-03 ~10:10: that staged change is gone from the index and the work tree (core.py equals HEAD 8a5a826), with no commit, stash or branch holding it; whoever staged it discarded it or holds it elsewhere. The second copy stands until someone lands it.
  · work: code
  · size: S
  · files: setuplib/core.py, tests/test_userscope.py
  · done when: setuplib/core.py's _coverage reads user_scope.covered and decides nothing itself, committed with its tests and mutants
  · added: 2026-11-03

- **su-132 · audit-terms.json roster_names is a copy of the roster, re-probed by hand on each roster change**
  audit-terms.json roster_names is a hand copy of the roster's agent names that are not repo names (the direction audit forbids reading the roster); refreshed after the agent renames in 8a72911. 'checks run .' on 2026-11-03 reports no-roster UNCHECKED: 'names half not run: no roster names passed (--names)'. Moved here from su-45 (tl-669).
  · work: code
  · size: S
  · files: audit-terms.json
  · done when: roster_names is gone and checks' no-roster names half runs here
  · retire: when a caller runs checks' no-roster here with the roster's names (checks all --names), delete roster_names
  · added: 2026-11-03

- **su-133 · user scope, once it registers the shared hooks: dev.sh hooks, the --user-scope default, and a created repo's settings.json**
  Follow-ups for when user scope registers the shared hooks (decision 19, PLAN-context-hygiene §6, approved 2026-10-04). On 2026-11-03 'hooks copies .. --json' reports user_scope exists, 19 hook rows, every one registered: false, so none of these bites yet. (1) dev.sh hooks requires each copy registered in this repo's settings.json, so dropping per-repo registrations once user scope covers them turns it red; it should accept user-scope coverage from the same report (was su-38). (2) --user-scope and --plugins have no default; dependencies.json now names tools/hooks, so a default could run its CLI (was su-36, su-41; --plugins at the top is refused since su-40). (3) a created repo whose hooks render is empty gets no settings.json, so no permission mode, though PLAN-repo-setup §7.9 says the file holds one (was su-50). Moved here from su-36, su-38, su-41, su-50 (tl-669).
  · work: code
  · size: S
  · files: dev.sh, setup, setuplib/core.py
  · done when: once user scope registers the shared hooks: dev.sh hooks accepts its coverage, --user-scope has a default or a recorded reason not to, and a created repo's settings.json question is answered; each with a test
  · added: 2026-11-03

- **su-134 · the docs declaration (kb-docs.tsv) is in 2 repos; most owners have not had it installed**
  The docs declaration (kb-docs.tsv) is in 2 repos on 2026-11-03 (tools/setup, tools/tab-digest), while PLAN-knowledge-base §11 step 3 has each owner add its declaration through setup. setup fanout's declared_by names rules, hooks, parts and mutate, not docs, so a declaration reaches a repo only through a setup run there. The hook half of su-8 is done: the hooks fan-out dry run of 2026-11-03 found 21 repos unchanged. Moved here from su-8 (tl-669).
  · work: tooling
  · size: S
  · files: components.json
  · done when: each repo the docs index should read declares its docs, by setup runs per owner or a docs entry in setup fanout; or the plan says which repos are left out
  · added: 2026-11-03
