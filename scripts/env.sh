# Source before any RepairAgent / Defects4J command. No API keys here.
#   source /workspace/report_reproduct/scripts/env.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$ROOT/vendor/defects4j/framework/bin:$PATH"
export TZ="${TZ:-America/Los_Angeles}"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  export PATH="$ROOT/.venv/bin:$PATH"
fi
echo "JAVA_HOME=$JAVA_HOME"
java -version 2>&1 | head -1
command -v defects4j
python --version
