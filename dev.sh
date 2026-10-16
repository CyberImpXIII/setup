#!/usr/bin/env bash
# The one pre-commit command for this repo: ./dev.sh check
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2

usage() {
  cat <<'EOF'
./dev.sh <command>

  check      the parts of check.parts.json (each test module, then each gate below but plans) via devtools/parts.py: [--resume | --only NAME...] [--json]; non-zero if any part fails
  test       the unit tests (tests/), trimmed to the result unless something fails
  hooks      the shared hook copies: present, executable, parse, their own tests pass (exit 3 there: UNCHECKED, gate exit 3), registered (PENDING: only in the proposal, for Jacob)
  files      the files the tool needs: present, executable where they must be, data parses
  audit      setup audit content, direction and deps (content and deps are UNCHECKED, so red, in a lone clone)
  self       ./setup --dry-run on this repo: nothing would be written, nothing drifted
  mutants    break each gate once in a throwaway copy, require red (devtools/mutants.json)
  plans DIR  setup plans DIR (not part of check: the plans belong to whoever holds DIR)
EOF
}

cmd_test() {
  local out code
  out=$(python3 -m unittest discover -s tests -t . 2>&1); code=$?
  if [ $code -ne 0 ]; then printf '%s\n' "$out"; else printf '%s\n' "$out" | grep -E '^(Ran|OK)' | paste -sd' ' -; fi
  return $code
}

registers() {  # registers SETTINGS_FILE NAME: does that settings file run .claude/hooks/NAME
  jq -e --arg n "$2" '[.hooks[][].hooks[].command | select(endswith("/.claude/hooks/" + $n))] | length > 0' "$1" >/dev/null 2>&1
}

cmd_hooks() {
  local fails=0 pending=0 unchecked=0 h name t out code why
  [ -f .claude/settings.json ] && jq -e . .claude/settings.json >/dev/null 2>&1 \
    || { echo "  FAIL  .claude/settings.json missing or does not parse"; return 1; }
  for h in .claude/hooks/*.sh; do
    name=$(basename "$h")
    [ -x "$h" ] || { echo "  FAIL  $name is not executable"; fails=$((fails+1)); }
    bash -n "$h" 2>/dev/null || { echo "  FAIL  $name does not parse"; fails=$((fails+1)); }
    case "$name" in test-*) continue ;; esac
    # settings.json is Jacob's (settings-guard blocks a session's write): a hook the
    # proposal setup wrote registers is PENDING his copy, said every run; one in
    # neither runs nowhere and nothing will make it run: FAIL
    if ! registers .claude/settings.json "$name"; then
      if [ -f .claude/settings.proposed.json ] && registers .claude/settings.proposed.json "$name"; then
        echo "  PENDING $name is registered only in .claude/settings.proposed.json: it does not run here until Jacob applies it (cp .claude/settings.proposed.json .claude/settings.json)"
        pending=$((pending+1))
      else
        echo "  FAIL  $name is not registered in .claude/settings.json (nor in a proposal: run ./setup .)"; fails=$((fails+1))
      fi
    fi
    t=".claude/hooks/test-$name"
    if [ ! -f "$t" ]; then echo "  FAIL  $name has no test-$name"; fails=$((fails+1)); continue; fi
    # a hook's own test answers like a gate: 0 pass, 3 UNCHECKED (it could not run
    # here, e.g. no sibling repo above a lone clone), anything else FAIL
    out=$(bash "$t" </dev/null 2>&1); code=$?
    if [ $code -eq 3 ]; then
      why=$(printf '%s\n' "$out" | grep -m1 -E '^[[:space:]]*UNCHECKED' | sed -E 's/^[[:space:]]*UNCHECKED:?[[:space:]]*//')
      echo "  UNCHECKED  test-$name: ${why:-exit 3 without saying why}"; unchecked=$((unchecked+1))
    elif [ $code -ne 0 ]; then
      echo "  FAIL  test-$name: exit $code"; printf '%s\n' "$out" | grep -E 'FAIL' | sed 's/^/        /'; fails=$((fails+1))
    fi
  done
  [ $fails -gt 0 ] && return 1
  # UNCHECKED is never a pass and never a FAIL: the gate exits 3 (check counts it red)
  if [ $unchecked -gt 0 ]; then echo "  note  hooks: $unchecked hook test(s) UNCHECKED: they did not run here, not a pass"; return 3; fi
  echo "  ok    hooks: $(ls .claude/hooks/*.sh | grep -vc /test-) hooks, each executable, passing its own test and registered ($pending of them only in the proposal, PENDING Jacob)"
}

cmd_files() {
  local fails=0 f
  for f in setup dev.sh templates/dev.sh tests/fake_gh.py tests/fake_checks.py devtools/mutate.py; do
    [ -x "$f" ] || { echo "  FAIL  $f missing or not executable"; fails=$((fails+1)); }
  done
  for f in components.json dependencies.json audit-terms.json devtools/mutants.json checks.json gates.json check.parts.json tests/fixtures/*.json; do
    jq -e . "$f" >/dev/null 2>&1 || { echo "  FAIL  $f missing or does not parse"; fails=$((fails+1)); }
  done
  # the runner copy is run by python3, never executed: present (its mode is the source's)
  for f in CLAUDE.md TODO.md .gitignore devtools/parts.py $(jq -r '.components[] | (.template, .head) // empty' components.json 2>/dev/null); do
    [ -f "$f" ] || { echo "  FAIL  $f missing"; fails=$((fails+1)); }
  done
  bash -n templates/dev.sh 2>/dev/null || { echo "  FAIL  templates/dev.sh does not parse"; fails=$((fails+1)); }
  # a component installing a folder of scripts (githooks): each one present and parsing
  for f in $(jq -r '.components[] | select(.templates and .files) | .templates as $t | .files[] | "\($t)/\(.)"' components.json 2>/dev/null); do
    { [ -f "$f" ] && bash -n "$f" 2>/dev/null; } || { echo "  FAIL  $f missing or does not parse"; fails=$((fails+1)); }
  done
  [ $fails -eq 0 ] && echo "  ok    files: present, executable and parsing"
  return $((fails > 0))
}

cmd_audit() {
  local code=0
  ./setup audit content || code=1
  ./setup audit direction || code=1
  ./setup audit deps || code=1
  return $code
}

cmd_self() {
  local out code bad
  out=$(./setup . --dry-run --json); code=$?
  bad=$(printf '%s' "$out" | jq -r '.results[] | select(.status == "installed" or .status == "drift" or .status == "failed") | "  FAIL  \(.component) \(.status): \(.detail)"')
  if [ $code -ne 0 ] || [ -n "$bad" ]; then
    printf '%s\n' "${bad:-  FAIL  ./setup exited $code}"; return 1
  fi
  echo "  ok    self: $(printf '%s' "$out" | jq -r '[.results[].status] | group_by(.) | map("\(length) \(.[0])") | join(", ")')"
}

cmd_mutants() { python3 devtools/mutate.py "$@"; }

cmd_plans() {
  [ $# -eq 1 ] || { echo "usage: ./dev.sh plans DIR"; return 2; }
  ./setup plans "$1"
}

# check: each test module and each gate above but plans, as the parts of
# check.parts.json, run by the shared runner devtools/parts.py (PLAN-small-tasks
# §3, §5; the parts component renders it): each part with its own timeout, its
# result written to the progress file ($PROGRESS_FILE, default .progress/check.json)
# as it ends, --resume re-running only the parts whose files changed or that did
# not pass, --json the one schema (a part that exits 3 is `unchecked`). With
# CHECK_PARTS=<file> it runs that file's parts instead (the shared check-partial
# gate's fixture, and this repo's own tests of check).
#
# A green run of this repo's whole suite records the tree it ran on for the git
# pre-commit hook (the githooks component), on stderr so --json stays one
# document. Never recorded: a run of other parts or of some (--only), a tree that
# changed meanwhile (check-pass refuses), or a run in which a part said UNCHECKED
# (green by the schema, never a pass). Not recording never turns a green check
# red: the commit is what is refused.
cmd_check() {
  local a record=1 resume=0 tree="" code pf state rf args
  for a in "$@"; do
    case "$a" in --only) record=0 ;; --resume) resume=1 ;; esac
  done
  [ -n "${CHECK_PARTS:-}" ] && record=0
  # the tree the parts run on, taken first, so an edit made meanwhile is never recorded as checked
  [ $record = 1 ] && [ -x .githooks/check-pass ] && tree=$(.githooks/check-pass tree 2>/dev/null)
  python3 devtools/parts.py run "${CHECK_PARTS:-check.parts.json}" "$@"; code=$?
  { [ $code -eq 0 ] && [ $record = 1 ] && [ -n "$tree" ]; } || return $code
  pf=${PROGRESS_FILE:-.progress/check.json}
  state=$(jq -r 'if (.passed_steps | length) == .total and .state == "passed" then "all" else "partial" end' "$pf" 2>/dev/null)
  if [ "$state" != all ]; then
    echo "check: green, but not every part passed (one said UNCHECKED, or $pf is unreadable): the pass was not recorded" >&2
    return $code
  fi
  args=(--from "$tree")
  if [ $resume = 1 ]; then
    # parts.py writes resumed_from "K/N at <time>" when it skipped parts, null on a full run
    rf=$(jq -r 'if .resumed_from == null then "-" else (.resumed_from | capture("^(?<r>[0-9]+/[0-9]+) at ").r) end' "$pf" 2>/dev/null)
    [ -n "$rf" ] || { echo "check: green, but the resume point in $pf could not be read: the pass was not recorded" >&2; return $code; }
    [ "$rf" != - ] && args+=(--resumed-from "$rf")
  fi
  .githooks/check-pass record "${args[@]}" >&2 || echo "check: green, but the pass was not recorded (see above)" >&2
  return $code
}

case "${1:-}" in
  check)   shift; cmd_check "$@" ;;
  test)    cmd_test ;;
  hooks)   cmd_hooks ;;
  files)   cmd_files ;;
  audit)   cmd_audit ;;
  self)    cmd_self ;;
  mutants) shift; cmd_mutants "$@" ;;
  plans)   shift; cmd_plans "$@" ;;
  ""|-h|--help|help) usage ;;
  *) echo "unknown command: $1"; usage; exit 2 ;;
esac
