#!/usr/bin/env bash
# Linux / WSL only. Defects4J does not install cleanly on native Windows.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
D4J="$ROOT/vendor/defects4j"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk-amd64}"
if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "需要 Java 11。当前 JAVA_HOME=$JAVA_HOME"
  echo "Ubuntu: sudo apt-get install -y openjdk-11-jdk"
  exit 1
fi
"$JAVA_HOME/bin/java" -version
export PATH="$JAVA_HOME/bin:$PATH"
if [[ ! -d "$D4J/.git" ]]; then
  mkdir -p "$ROOT/vendor"
  git clone --depth 1 https://github.com/rjust/defects4j.git "$D4J"
fi
if [[ ! -d "$D4J/major" ]]; then
  echo "初始化 Defects4J（只需一次，会下载若干依赖）"
  (cd "$D4J" && ./init.sh)
fi
if ! perl -MString::Interpolate -e 1 2>/dev/null; then
  echo "缺少 Perl 模块 String::Interpolate。Ubuntu 可试："
  echo "  sudo cpanm String::Interpolate"
  exit 1
fi
echo "Defects4J 已就绪：$D4J"
echo "接着跑: bash scripts/run_all.sh --with-d4j"
