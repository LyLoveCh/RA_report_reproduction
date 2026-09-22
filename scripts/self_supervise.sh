#!/usr/bin/env bash
# Self-supervise a long job so a crashed Cursor/agent window does not kill it.
#
#   bash scripts/self_supervise.sh start -- bash scripts/run_compare_sample10.sh cr
#   bash scripts/self_supervise.sh start -- bash scripts/run_full_chart1.sh
#   bash scripts/self_supervise.sh status
#   bash scripts/self_supervise.sh attach
#   bash scripts/self_supervise.sh stop
#
# The job runs in tmux, writes a heartbeat, and restarts on crash (non-zero exit)
# up to MAX_RESTART times. Exit 0 means success — no restart.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/evidence/supervise"
SESSION="repro-supervise"
MAX_RESTART="${SUPERVISE_MAX_RESTART:-15}"
HB="$DIR/heartbeat.txt"
LOG="$DIR/supervisor.log"
STATE="$DIR/state.txt"
PIDFILE="$DIR/inner.pid"

mkdir -p "$DIR"

tmux_bin() {
  if [[ -f /exec-daemon/tmux.portal.conf ]]; then
    tmux -f /exec-daemon/tmux.portal.conf "$@"
  else
    tmux "$@"
  fi
}

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log() {
  echo "$(stamp) $*" | tee -a "$LOG" >/dev/null
  echo "$(stamp) $*" > "$HB"
}

cmd_inner() {
  trap '' HUP
  trap '' PIPE
  local n=0
  local delay=4
  echo "running" > "$STATE"
  echo $$ > "$PIDFILE"
  if [[ $# -lt 1 ]]; then
    echo "inner: missing command" >&2
    echo "failed" > "$STATE"
    exit 1
  fi
  while true; do
    log "attempt=$((n + 1)) start: $*"
    set +e
    "$@"
    local code=$?
    set -e
    log "attempt=$((n + 1)) exit=$code"
    if [[ "$code" -eq 0 ]]; then
      echo "done" > "$STATE"
      log "success — supervisor stopping"
      exit 0
    fi
    n=$((n + 1))
    if [[ "$n" -ge "$MAX_RESTART" ]]; then
      echo "failed" > "$STATE"
      log "gave up after $n crashes"
      exit "$code"
    fi
    log "crash — restart in ${delay}s ($n/$MAX_RESTART)"
    sleep "$delay"
    if [[ "$delay" -lt 60 ]]; then
      delay=$((delay * 2))
    fi
  done
}

cmd_start() {
  trap '' HUP
  if tmux_bin has-session -t "=$SESSION" 2>/dev/null; then
    echo "already running (tmux $SESSION). Use: $0 status | $0 attach"
    cmd_status
    exit 0
  fi
  if [[ $# -lt 1 ]]; then
    echo "usage: $0 start -- <command> [args...]"
    exit 1
  fi
  : > "$LOG"
  echo "starting" > "$STATE"
  tmux_bin set-option -g destroy-unattached off >/dev/null 2>&1 || true
  tmux_bin set-option -g detach-on-destroy off >/dev/null 2>&1 || true
  # Remain in tmux even if this shell exits. The inner loop is the watchdog.
  tmux_bin new-session -d -s "$SESSION" -c "$ROOT" -- \
    bash "$ROOT/scripts/self_supervise.sh" inner "$@"
  sleep 0.4
  cmd_status
}

cmd_status() {
  local st="unknown"
  [[ -f "$STATE" ]] && st="$(cat "$STATE")"
  echo "state=$st"
  echo "session=$SESSION"
  if tmux_bin has-session -t "=$SESSION" 2>/dev/null; then
    echo "tmux=alive"
  else
    echo "tmux=dead"
  fi
  if [[ -f "$HB" ]]; then
    echo -n "heartbeat="
    cat "$HB"
  else
    echo "heartbeat=(none yet)"
  fi
  if [[ -f "$LOG" ]]; then
    echo "---- last log lines ----"
    tail -n 12 "$LOG"
  fi
}

cmd_attach() {
  tmux_bin attach-session -t "=$SESSION"
}

cmd_stop() {
  tmux_bin kill-session -t "=$SESSION" 2>/dev/null || true
  echo "stopped" > "$STATE"
  log "stopped by user"
  echo "stopped"
}

cmd_keepalive() {
  echo "keepalive" > "$STATE"
  echo $$ > "$PIDFILE"
  while true; do
    log "keepalive pid=$$"
    sleep 20
  done
}

usage() {
  echo "usage: $0 start -- <command> [args...]"
  echo "       $0 status | attach | stop | keepalive | inner <command>"
}

sub="${1:-status}"
if [[ $# -gt 0 ]]; then
  shift
fi
case "$sub" in
  start)
    if [[ "${1:-}" == "--" ]]; then
      shift
    fi
    cmd_start "$@"
    ;;
  inner)
    if [[ "${1:-}" == "--" ]]; then
      shift
    fi
    cmd_inner "$@"
    ;;
  status) cmd_status ;;
  attach) cmd_attach ;;
  stop) cmd_stop ;;
  keepalive)
    cmd_keepalive
    ;;
  -h|--help|help) usage ;;
  *)
    usage
    exit 1
    ;;
esac
