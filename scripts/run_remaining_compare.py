#!/usr/bin/env python3
"""Finish sample10: remaining ChatRepair-loop bugs, then RepairAgent one-by-one.

Skips CR bugs that already finished and RA bugs that already have experiment logs.
Run under scripts/self_supervise.sh so a crashed window does not kill it.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA_AGENT = ROOT / "vendor" / "RepairAgent" / "repair_agent"
SAMPLE = ROOT / "demos" / "sample_all.txt"
if not SAMPLE.exists():
    SAMPLE = ROOT / "demos" / "sample10.txt"
HB = ROOT / "evidence" / "supervise" / "heartbeat.txt"
PROGRESS = ROOT / "evidence" / "compare_sample10" / "progress.txt"
HALT = ROOT / "evidence" / "supervise" / "halt.txt"
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")
MODEL = os.environ.get("COMPARE_MODEL") or os.environ.get("LLM_MODEL") or "deepseek-chat"
MAX_CYCLES = int(os.environ.get("COMPARE_RA_MAX_CYCLES") or "40")
# Wall-clock cap per bug. Normal RA extra bugs finished in 15–50 min; Jsoup 5
# hung one write_fix mutant test for 5+ hours. 90 min still clears a full 40-cycle run.
RA_TIMEOUT_SEC = int(os.environ.get("COMPARE_RA_TIMEOUT_SEC") or "5400")

sys.path.insert(0, str(ROOT / "scripts"))
import visualize_compare as viz  # noqa: E402
import chatrepair_loop as cr  # noqa: E402


def redact(text: str) -> str:
    return SECRET_RE.sub("sk-[REDACTED]", text or "")


def heartbeat(msg: str) -> None:
    HB.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    line = f"{stamp} {msg}\n"
    HB.write_text(line, encoding="utf-8")
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as fh:
        fh.write(line)
    print(line, end="", flush=True)


def parse_bugs() -> list[tuple[str, str]]:
    return cr.parse_bugs(SAMPLE)


def halt_requested() -> bool:
    flag = (os.environ.get("COMPARE_HALT") or "").strip().lower()
    if flag in {"1", "true", "yes"}:
        return True
    return HALT.exists()


def summarize() -> None:
    viz.ra_index.cache_clear()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "summarize_compare.py")],
        check=False,
    )


def run_cr() -> int:
    heartbeat("phase=CR start remaining sample_all")
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "chatrepair_loop.py"),
            "--bugfile",
            str(SAMPLE),
        ]
    )
    heartbeat(f"phase=CR done exit={proc.returncode}")
    summarize()
    return proc.returncode


SLIM_DIR = ROOT / "evidence" / "compare_sample10" / "repairagent"


def ra_already_recorded(proj: str, idx: str) -> bool:
    """Skip only after summarize wrote a slim JSON. In-progress prompt_history is not done."""
    return (SLIM_DIR / f"{proj}_{idx}.json").exists()


def ra_process_running() -> bool:
    proc = subprocess.run(["pgrep", "-af", "repairagent.py run"], capture_output=True, text=True)
    lines = [ln for ln in (proc.stdout or "").splitlines() if "repairagent.py run" in ln and "pgrep" not in ln]
    return bool(lines)


def kill_process_group(pid: int) -> None:
    """Stop a RepairAgent session and its Defects4J/java children. Do not use on the supervisor."""
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            os.killpg(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.4)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def record_ra_no(proj: str, idx: str, *, rounds: int | None, note: str, exp: str = "") -> None:
    SLIM_DIR.mkdir(parents=True, exist_ok=True)
    dest = SLIM_DIR / f"{proj}_{idx}.json"
    payload: dict = {
        "bug": f"{proj} {idx}",
        "exp": exp,
        "plausible": False,
        "rounds": rounds,
        "goals_accomplished": False,
        "note": note,
    }
    if dest.exists():
        try:
            old = json.loads(dest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            old = {}
        if old.get("note") and not note:
            payload["note"] = old["note"]
        if old.get("exp") and not exp:
            payload["exp"] = old["exp"]
        if payload["rounds"] is None:
            payload["rounds"] = old.get("rounds")
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_ra_one(proj: str, idx: str) -> int:
    if ra_already_recorded(proj, idx):
        heartbeat(f"phase=RA skip {proj} {idx} already recorded")
        return 0
    while ra_process_running():
        heartbeat(f"phase=RA wait existing repairagent before {proj} {idx}")
        time.sleep(30)
        if ra_already_recorded(proj, idx):
            heartbeat(f"phase=RA skip {proj} {idx} finished while waiting")
            return 0
    # An orphaned RA for this bug may have just exited. Record it; do not start a second run.
    viz.ra_index.cache_clear()
    hit = viz.ra_status(f"{proj} {idx}")
    if hit.get("status") in ("yes", "no"):
        heartbeat(f"phase=RA skip {proj} {idx} already finished by existing process")
        summarize()
        return 0
    heartbeat(f"phase=RA start {proj} {idx} max-cycles={MAX_CYCLES} model={MODEL}")
    proc = subprocess.Popen(
        [
            sys.executable,
            "repairagent.py",
            "run",
            "--bugs",
            f"{proj} {idx}",
            "--model",
            MODEL,
            "--temperature",
            "0",
            "--max-cycles",
            str(MAX_CYCLES),
        ],
        cwd=str(RA_AGENT),
        start_new_session=True,
    )
    try:
        code = proc.wait(timeout=RA_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        heartbeat(
            f"phase=RA timeout {proj} {idx} after {RA_TIMEOUT_SEC}s — record no and continue"
        )
        kill_process_group(proc.pid)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
        record_ra_no(
            proj,
            idx,
            rounds=None,
            note=f"wall-clock timeout after {RA_TIMEOUT_SEC}s; recorded as no so the queue can continue",
        )
        summarize()
        return 0
    heartbeat(f"phase=RA done {proj} {idx} exit={redact(str(code))}")
    summarize()
    return code or 0


def main() -> int:
    heartbeat("run_remaining_compare start")
    if halt_requested():
        heartbeat("halt requested — summarize and stop, no more RA bugs")
        summarize()
        return 0
    cr_code = run_cr()
    ra_codes = []
    for proj, idx in parse_bugs():
        if halt_requested():
            heartbeat(f"halt requested — stop before {proj} {idx}")
            break
        ra_codes.append(run_ra_one(proj, idx))
        if halt_requested():
            heartbeat(f"halt requested — stop after {proj} {idx}")
            break
    summarize()
    failed = (cr_code != 0) or any(c not in (0,) for c in ra_codes)
    heartbeat(f"run_remaining_compare finished cr={cr_code} ra={ra_codes} failed={int(failed)}")
    # Still exit 0 if bugs were attempted: a single RA miss should not restart CR.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
