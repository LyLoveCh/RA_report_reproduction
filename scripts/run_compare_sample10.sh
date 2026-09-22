#!/usr/bin/env bash
# Mini comparison: ChatRepair-style loop vs official RepairAgent, same DeepSeek, same 10 bugs.
# Prefer the watchdog so a crashed IDE/agent window does not kill the job:
#   bash scripts/self_supervise.sh start -- bash scripts/run_compare_sample10.sh finish
#   bash scripts/watchdog_supervise.sh start
#   bash scripts/watchdog_supervise.sh status
# Direct:
#   bash scripts/run_compare_sample10.sh cr [Project Index ...]
#   bash scripts/run_compare_sample10.sh ra
#   bash scripts/run_compare_sample10.sh summarize
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RA="$ROOT/vendor/RepairAgent/repair_agent"

if [[ -f "$ROOT/scripts/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/env.sh" >/dev/null
fi

# Load keys from local env files without printing them.
# shellcheck disable=SC1091
source "$ROOT/scripts/load_llm_env.sh"

MODE="${1:-cr}"
if [[ $# -gt 0 ]]; then
  shift
fi
MODEL="${COMPARE_MODEL:-${LLM_MODEL:-deepseek-chat}}"
BUGFILE="${COMPARE_BUGFILE:-$ROOT/demos/sample_all.txt}"
if [[ ! -f "$BUGFILE" ]]; then
  BUGFILE="$ROOT/demos/sample10.txt"
fi

case "$MODE" in
  cr|chatrepair)
    exec python "$ROOT/scripts/chatrepair_loop.py" --bugfile "$BUGFILE" "$@"
    ;;
  ra|repairagent)
    cd "$RA"
    exec python repairagent.py run \
      --bugs-file "$BUGFILE" \
      --model "$MODEL" \
      --temperature 0 \
      --max-cycles 40 \
      "$@"
    ;;
  summarize)
    exec python "$ROOT/scripts/summarize_compare.py" "$@"
    ;;
  finish|remaining|all)
    exec python "$ROOT/scripts/run_remaining_compare.py" "$@"
    ;;
  *)
    echo "usage: $0 cr|ra|summarize|finish [args]"
    exit 1
    ;;
esac
