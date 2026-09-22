#!/usr/bin/env bash
# Detached watchdog: if the tmux job dies while state is still "running",
# start it again. Lives outside Cursor so a crashed IDE window does not
# take the comparison with it. Never starts a second Defects4J while
# workers from the previous session are still alive.
#
#   bash scripts/watchdog_supervise.sh start
#   bash scripts/watchdog_supervise.sh status
#   bash scripts/watchdog_supervise.sh stop
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/evidence/supervise"
SESSION="repro-supervise"
LOG="$DIR/watchdog.log"
PIDFILE="$DIR/watchdog.pid"
STATE="$DIR/state.txt"
JOB=(bash "$ROOT/scripts/run_compare_sample10.sh" finish)

mkdir -p "$DIR"

tmux_bin() {
  if [[ -f /exec-daemon/tmux.portal.conf ]]; then
    tmux -f /exec-daemon/tmux.portal.conf "$@"
  else
    tmux "$@"
  fi
}

stamp() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

log() { echo "$(stamp) $*" >>"$LOG"; }

session_alive() {
  tmux_bin has-session -t "=$SESSION" 2>/dev/null
}

worker_lines() {
  pgrep -af 'run_remaining_compare.py|chatrepair_loop.py|repairagent.py run|self_supervise.sh inner' 2>/dev/null \
    | grep -v -E 'pgrep|watchdog_supervise' || true
}

workers_alive() {
  [[ -n "$(worker_lines)" ]]
}

read_state() {
  if [[ -f "$STATE" ]]; then
    cat "$STATE"
  else
    echo "unknown"
  fi
}

cmd_loop() {
  trap '' HUP
  trap '' PIPE
  trap '' INT
  cd "$ROOT"
  echo $$ > "$PIDFILE"
  tmux_bin set-option -g destroy-unattached off >/dev/null 2>&1 || true
  tmux_bin set-option -g detach-on-destroy off >/dev/null 2>&1 || true
  log "watchdog pid=$$ ppid=$PPID sid=$$ start"
  while true; do
    local st
    st="$(read_state)"
    if [[ "$st" == "done" ]]; then
      log "job done — watchdog stopping"
      rm -f "$PIDFILE"
      exit 0
    fi
    if [[ "$st" == "failed" ]] || [[ "$st" == "stopped" ]]; then
      log "job $st — watchdog stopping"
      rm -f "$PIDFILE"
      if [[ "$st" == "failed" ]]; then
        exit 1
      fi
      exit 0
    fi
    if ! session_alive; then
      if workers_alive; then
        log "tmux $SESSION missing but workers still live — not starting a second Defects4J"
      elif [[ "$st" == "running" || "$st" == "starting" || "$st" == "unknown" ]]; then
        log "tmux $SESSION missing while state=$st — restarting finish"
        bash "$ROOT/scripts/self_supervise.sh" start -- "${JOB[@]}" >>"$LOG" 2>&1 || true
      fi
    fi
    {
      echo "$(stamp) state=$st tmux=$(session_alive && echo alive || echo dead) workers=$(workers_alive && echo alive || echo none)"
      worker_lines | head -n 5
    } >"$DIR/liveness.txt"
    sleep 30
  done
}

cmd_start() {
  trap '' HUP
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "watchdog already running pid=$(cat "$PIDFILE")"
    cmd_status
    exit 0
  fi
  : >>"$LOG"
  # New session, ignore hangup, stdin from /dev/null. Cursor window death
  # must not take this process with it.
  setsid nohup bash "$ROOT/scripts/watchdog_supervise.sh" loop </dev/null >>"$LOG" 2>&1 &
  disown || true
  sleep 0.8
  cmd_status
}

cmd_status() {
  echo "job_state=$(read_state)"
  if session_alive; then
    echo "tmux=alive"
  else
    echo "tmux=dead"
  fi
  if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    local wpid wppid
    wpid="$(cat "$PIDFILE")"
    wppid="$(ps -o ppid= -p "$wpid" 2>/dev/null | tr -d ' ')"
    echo "watchdog=alive pid=$wpid ppid=${wppid:-?} (ppid=1 means detached from Cursor)"
    if workers_alive; then
      echo "workers=alive"
    else
      echo "workers=none"
    fi
  else
    echo "watchdog=dead"
  fi
  if [[ -f "$LOG" ]]; then
    echo "---- last watchdog lines ----"
    tail -n 8 "$LOG"
  fi
}

cmd_stop() {
  if [[ -f "$PIDFILE" ]]; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    rm -f "$PIDFILE"
  fi
  echo "watchdog stopped (tmux job left running)"
}

sub="${1:-status}"
case "$sub" in
  start) cmd_start ;;
  loop) cmd_loop ;;
  status) cmd_status ;;
  stop) cmd_stop ;;
  *)
    echo "usage: $0 start|status|stop"
    exit 1
    ;;
esac
