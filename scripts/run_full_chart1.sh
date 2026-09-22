#!/usr/bin/env bash
# Full agent on ONE bug (Chart 1). Put the key in ../.env first — never in git or chat.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RA="$ROOT/vendor/RepairAgent/repair_agent"

if [[ -f "$ROOT/scripts/env.sh" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/scripts/env.sh" >/dev/null
fi
# shellcheck disable=SC1091
source "$ROOT/scripts/load_llm_env.sh"

if [[ ! -f "$RA/repairagent.py" ]]; then
  mkdir -p "$ROOT/vendor"
  git clone --depth 1 https://github.com/sola-st/RepairAgent.git "$ROOT/vendor/RepairAgent"
fi

if ! command -v defects4j >/dev/null 2>&1 && [[ "${1:-}" != "--docker" ]]; then
  echo "本机没有 defects4j。请先: bash scripts/setup_defects4j.sh"
  echo "或加参数 --docker（需要 Docker）"
  exit 1
fi

MODEL="${LLM_MODEL:-deepseek-chat}"
echo "完整 agent × 1 题: Chart 1 / model=$MODEL / max-cycles=40"
cd "$RA"
exec python3 repairagent.py run \
  --bugs "Chart 1" \
  --model "$MODEL" \
  --temperature 0 \
  --max-cycles 40 \
  "$@"
