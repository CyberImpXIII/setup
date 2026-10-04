#!/usr/bin/env bash
# The one pre-commit command for this repo: ./dev.sh check
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 2

usage() {
  cat <<'EOF'
./dev.sh <command>

  check      every gate below, in order; non-zero if any fails (--json: {"ok": bool, "gates": {...}})
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
  local fails=0 h name t
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
  for f in setup dev.sh templates/dev.sh tests/fake_gh.py devtools/mutate.py; do
    [ -x "$f" ] || { echo "  FAIL  $f missing or not executable"; fails=$((fails+1)); }
  done
  for f in components.json audit-terms.json devtools/mutants.json checks.json; do
    jq -e . "$f" >/dev/null 2>&1 || { echo "  FAIL  $f missing or does not parse"; fails=$((fails+1)); }
  done
  for f in CLAUDE.md TODO.md .gitignore $(jq -r '.components[] | (.template, .head) // empty' components.json 2>/dev/null); do
    [ -f "$f" ] || { echo "  FAIL  $f missing"; fails=$((fails+1)); }
  done
  bash -n templates/dev.sh 2>/dev/null || { echo "  FAIL  templates/dev.sh does not parse"; fails=$((fails+1)); }
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

cmd_check() {
  local json=0 g code fails=0 results=""
  [ "${1:-}" = "--json" ] && json=1
  for g in "${GATES[@]}"; do
    if [ $json -eq 1 ]; then "cmd_$g" >/dev/null 2>&1; code=$?
    else echo "== $g"; "cmd_$g"; code=$?; fi
    [ $code -ne 0 ] && fails=$((fails+1))
    results="$results\"$g\": $([ $code -eq 0 ] && echo true || echo false), "
  done
  if [ $json -eq 1 ]; then
    printf '{"ok": %s, "gates": {%s}}\n' "$([ $fails -eq 0 ] && echo true || echo false)" "${results%, }"
  else
    [ $fails -eq 0 ] && echo "check: all ${#GATES[@]} gates green" || echo "check: $fails of ${#GATES[@]} gates FAILED"
  fi
  return $((fails > 0))
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
