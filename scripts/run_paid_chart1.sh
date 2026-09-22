#!/usr/bin/env bash
# Spend a small OpenAI budget on ONE Defects4J bug: Chart 1.
# Extra args are forwarded, e.g. --docker
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RA="$ROOT/vendor/RepairAgent/repair_agent"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "未设置 OPENAI_API_KEY。"
  echo "  export OPENAI_API_KEY='sk-...'"
  echo "不要把 key 写进 Git，也不要发给别人。"
  exit 1
fi

if [[ ! -f "$RA/repairagent.py" ]]; then
  mkdir -p "$ROOT/vendor"
  git clone --depth 1 https://github.com/sola-st/RepairAgent.git "$ROOT/vendor/RepairAgent"
fi

cd "$RA"
echo "只跑 Chart 1 / gpt-4o-mini / max-cycles 40 / temperature 0"
echo "官方命令见 PAID_RUN.md"
exec python3 repairagent.py run \
  --bugs "Chart 1" \
  --model gpt-4o-mini \
  --temperature 0 \
  --max-cycles 40 \
  "$@"
