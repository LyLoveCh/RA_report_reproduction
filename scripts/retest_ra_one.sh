#!/usr/bin/env bash
# Retest one RepairAgent bug. Does not skip an existing slim JSON.
# Installs kit perfect-FL files into the vendor tree when present.
#   bash scripts/retest_ra_one.sh Collections 21
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/env.sh" >/dev/null
# shellcheck disable=SC1091
source "$ROOT/scripts/load_llm_env.sh"

if [[ $# -lt 2 ]]; then
  echo "usage: $0 Project Index" >&2
  exit 1
fi
PROJ="$1"
IDX="$2"
RA="$ROOT/vendor/RepairAgent/repair_agent"
MODEL="${COMPARE_MODEL:-${LLM_MODEL:-deepseek-chat}}"
MAX_CYCLES="${COMPARE_RA_MAX_CYCLES:-40}"

if pgrep -af 'repairagent.py run' | grep -v pgrep >/dev/null; then
  echo "a repairagent.py run is already alive; not starting a second Defects4J" >&2
  exit 1
fi

KIT="$ROOT/data/buggy-lines/${PROJ}-${IDX}.buggy.lines"
if [[ -f "$KIT" ]]; then
  for dest in "$RA/defects4j/buggy-lines" "$ROOT/vendor/RepairAgent/data/buggy-lines"; do
    mkdir -p "$dest"
    cp "$KIT" "$dest/"
  done
  echo "installed perfect FL: $KIT"
fi

SLIM_DIR="$ROOT/evidence/compare_sample10/repairagent"
SLIM="$SLIM_DIR/${PROJ}_${IDX}.json"
if [[ -f "$SLIM" ]]; then
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$SLIM" "$SLIM_DIR/${PROJ}_${IDX}.before_retest_${stamp}.json"
  echo "archived previous slim JSON"
fi

cd "$RA"
python repairagent.py run \
  --bugs "$PROJ $IDX" \
  --model "$MODEL" \
  --temperature 0 \
  --max-cycles "$MAX_CYCLES"
code=$?
python "$ROOT/scripts/summarize_compare.py" || true
exit "$code"
