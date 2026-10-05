#!/usr/bin/env bash
# The one pre-commit command for this repo: ./dev.sh check
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2

usage() {
  cat <<'EOF'
./dev.sh <command>

  check      every gate below, in order; non-zero if any fails (--json: the one schema, via devtools/checkjson.py)
  test       the unit tests (tests/), trimmed to the result unless something fails
  hooks      the shared hook copies: present, executable, parse, registered, their own tests pass
  files      the files the tool needs: present, executable where they must be, data parses
  audit      setup audit content + setup audit direction (content is UNCHECKED, so red, in a lone clone)
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

cmd_hooks() {
  local fails=0 h name t out
  [ -f .claude/settings.json ] && jq -e . .claude/settings.json >/dev/null 2>&1 \
    || { echo "  FAIL  .claude/settings.json missing or does not parse"; return 1; }
  for h in .claude/hooks/*.sh; do
    name=$(basename "$h")
    [ -x "$h" ] || { echo "  FAIL  $name is not executable"; fails=$((fails+1)); }
    bash -n "$h" 2>/dev/null || { echo "  FAIL  $name does not parse"; fails=$((fails+1)); }
    case "$name" in test-*) continue ;; esac
    jq -e --arg n "$name" '[.hooks[][].hooks[].command | select(endswith("/" + $n))] | length > 0' \
      .claude/settings.json >/dev/null || { echo "  FAIL  $name is not registered in .claude/settings.json"; fails=$((fails+1)); }
    t=".claude/hooks/test-$name"
    if [ ! -f "$t" ]; then echo "  FAIL  $name has no test-$name"; fails=$((fails+1)); continue; fi
    if ! out=$(bash "$t" 2>&1); then
      echo "  FAIL  test-$name:"; printf '%s\n' "$out" | grep -E 'FAIL' | sed 's/^/        /'; fails=$((fails+1))
    fi
  done
  [ $fails -eq 0 ] && echo "  ok    hooks: $(ls .claude/hooks/*.sh | grep -vc /test-) hooks, each executable, registered and passing its own test"
  return $((fails > 0))
}

cmd_files() {
  local fails=0 f
  for f in setup dev.sh templates/dev.sh tests/fake_gh.py tests/fake_checks.py devtools/mutate.py devtools/checkjson.py; do
    [ -x "$f" ] || { echo "  FAIL  $f missing or not executable"; fails=$((fails+1)); }
  done
  for f in components.json audit-terms.json devtools/mutants.json checks.json tests/fixtures/*.json; do
    jq -e . "$f" >/dev/null 2>&1 || { echo "  FAIL  $f missing or does not parse"; fails=$((fails+1)); }
  done
  for f in CLAUDE.md TODO.md .gitignore $(jq -r '.components[] | (.template, .head) // empty' components.json 2>/dev/null); do
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

GATES=(test hooks files audit self mutants)

# The role each gate's failure belongs to, in --json (code, tests, audit, docs):
# a surviving mutant is a missing test; the audits are audit's; the rest is code.
gate_role() { case "$1" in audit) echo audit ;; mutants) echo tests ;; *) echo code ;; esac; }

# --json: stdout is exactly one document (devtools/checkjson.py), each gate's
# output captured to a scratch file so its finding lines become the failures.
cmd_check() {
  local json=0 g code fails=0 capdir="" dest rows=() tree=""
  [ "${1:-}" = "--json" ] && json=1
  # the tree the gates run on, taken first, so an edit made meanwhile is never recorded as checked
  [ -x .githooks/check-pass ] && tree=$(.githooks/check-pass tree 2>/dev/null)
  [ $json -eq 1 ] && capdir=$(mktemp -d 2>/dev/null)
  for g in "${GATES[@]}"; do
    if [ $json -eq 1 ]; then
      dest=/dev/null; [ -n "$capdir" ] && dest="$capdir/$g"
      ( "cmd_$g" ) >"$dest" 2>&1; code=$?  # a subshell: a gate cannot touch this loop's variables
      rows+=("$g:$(gate_role "$g"):$code:$dest")
    else echo "== $g"; ( "cmd_$g" ); code=$?; fi
    [ $code -ne 0 ] && fails=$((fails+1))
  done
  if [ $json -eq 1 ]; then
    python3 devtools/checkjson.py "${rows[@]}"; code=$?
    [ -n "$capdir" ] && rm -rf "$capdir"
    [ $code -eq 0 ] && record_pass "$tree" >&2
    return $code
  fi
  [ $fails -eq 0 ] && echo "check: all ${#GATES[@]} gates green" || echo "check: $fails of ${#GATES[@]} gates FAILED"
  [ $fails -eq 0 ] && record_pass "$tree"
  return $((fails > 0))
}

# A green check records the tree it ran on for the git pre-commit hook (the githooks
# component); a tree that changed while the gates ran is not recorded. Not recording
# never turns a green check red: the commit is what is refused.
record_pass() {
  [ -n "$1" ] || return 0
  .githooks/check-pass record --from "$1" || echo "check: green, but the pass was not recorded (see above)"
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
