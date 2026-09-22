# Load LLM settings without printing secrets.
# Source from RepairAgent/.env first, then report_reproduct/.env (kit path wins).
# Usage: source scripts/load_llm_env.sh
if [[ -z "${ROOT:-}" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
RA="${RA:-$ROOT/vendor/RepairAgent/repair_agent}"
_LLM_KEY_SRC=""
for envf in "$RA/.env" "$ROOT/.env"; do
  if [[ -f "$envf" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$envf"
    set +a
    _LLM_KEY_SRC="$envf"
  fi
done
if [[ -z "${OPENAI_API_KEY:-}" || "$OPENAI_API_KEY" == *"换成你的"* || "$OPENAI_API_KEY" == *PLACEHOLDER* ]]; then
  echo "还没有可用的 key。"
  echo "写在 $ROOT/.env 或 $RA/.env（gitignore，不要提交、不要贴到聊天）。"
  echo ".env.example 必须保持占位符，不能写真 key。"
  return 1 2>/dev/null || exit 1
fi
echo "OPENAI_API_KEY loaded from ${_LLM_KEY_SRC} (len=${#OPENAI_API_KEY})"
echo "OPENAI_API_BASE=${OPENAI_API_BASE:-${OPENAI_API_BASE_URL:-unset}}"
echo "LLM_MODEL=${LLM_MODEL:-${COMPARE_MODEL:-deepseek-chat}}"
