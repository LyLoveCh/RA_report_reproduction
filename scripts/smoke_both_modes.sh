#!/usr/bin/env bash
# Prove BOTH pipelines on Chart-1 before touching the 10-bug comparison.
#   bash scripts/smoke_both_modes.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RA="$ROOT/vendor/RepairAgent/repair_agent"
LOG="$ROOT/evidence/smoke_chart1.log"
mkdir -p "$ROOT/evidence"

if [[ -f "$ROOT/scripts/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/env.sh" >/dev/null
fi
# shellcheck disable=SC1091
source "$ROOT/scripts/load_llm_env.sh"

MODEL="${COMPARE_MODEL:-${LLM_MODEL:-deepseek-chat}}"
{
  echo "==== probe LLM ===="
  python "$ROOT/scripts/probe_llm.py"
  echo "==== ChatRepair-style loop × Chart 1 ===="
  python "$ROOT/scripts/chatrepair_loop.py" --force --max-rounds 8 Chart 1
  echo "==== RepairAgent × Chart 1 (max-cycles 20) ===="
  cd "$RA"
  python repairagent.py run \
    --bugs "Chart 1" \
    --model "$MODEL" \
    --temperature 0 \
    --max-cycles 20
  echo "==== smoke finished ===="
} 2>&1 | tee "$LOG"
