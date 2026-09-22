#!/usr/bin/env python3
"""ChatRepair-style loop: generate patch -> run tests -> append failure -> repeat.

No codebase search. Uses Defects4J buggy-lines as the hardcoded context (perfect FL).
Reads API settings from RepairAgent repair_agent/.env — never prints the key.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

faulthandler.enable()
signal.signal(signal.SIGHUP, signal.SIG_IGN)

ROOT = Path(__file__).resolve().parent.parent
RA = ROOT / "vendor" / "RepairAgent"
RA_AGENT = RA / "repair_agent"
D4J_BIN = RA_AGENT / "defects4j" / "framework" / "bin"
BUGGY_LINES = RA / "data" / "buggy-lines"
WORK_ROOT = ROOT / "vendor" / "work" / "chatrepair_sample10"
OUT_ROOT = ROOT / "evidence" / "compare_sample10" / "chatrepair"
HB_PATH = ROOT / "evidence" / "supervise" / "heartbeat.txt"
MAX_ROUNDS = 12
MODEL = os.environ.get("COMPARE_MODEL", "deepseek-chat")
JAVA_HOME = os.environ.get("JAVA_HOME", "/usr/lib/jvm/java-11-openjdk-amd64")
SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}")


def heartbeat(msg: str) -> None:
    HB_PATH.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    HB_PATH.write_text(f"{stamp} {msg}\n", encoding="utf-8")


class HeartbeatThread(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.msg = "boot"
        self._stop = threading.Event()

    def run(self) -> None:
        while not self._stop.wait(15):
            try:
                heartbeat(self.msg)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()


def redact(text: str) -> str:
    if not text:
        return text
    text = SECRET_RE.sub("sk-[REDACTED]", text)
    text = re.sub(
        r'(OPENAI_API_KEY(?:["\s:=]|\\u003d)+)[^\s&"]+',
        r"\1[REDACTED]",
        text,
        flags=re.I,
    )
    return text


def load_dotenv(path: Path) -> dict[str, str]:
    vals: dict[str, str] = {}
    if not path.exists():
        return vals
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def d4j_env() -> dict:
    env = os.environ.copy()
    env["JAVA_HOME"] = JAVA_HOME
    env["TZ"] = "America/Los_Angeles"
    env["LC_COLLATE"] = "C"
    env.setdefault("LANG", "C.UTF-8")
    home_perl5 = str(Path.home() / "perl5" / "lib" / "perl5")
    perl5 = env.get("PERL5LIB", "")
    if home_perl5 not in perl5.split(os.pathsep):
        env["PERL5LIB"] = home_perl5 + (os.pathsep + perl5 if perl5 else "")
    env["PATH"] = os.pathsep.join(
        [str(Path(JAVA_HOME) / "bin"), str(D4J_BIN), env.get("PATH", "")]
    )
    return env


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=d4j_env(),
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def parse_bugs(path: Path) -> list[tuple[str, str]]:
    bugs = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        proj, idx = line.split()[:2]
        bugs.append((proj, idx))
    return bugs


def buggy_line_records(project: str, bid: str) -> list[tuple[str, int, str]]:
    p = BUGGY_LINES / f"{project}-{bid}.buggy.lines"
    if not p.exists():
        return []
    recs = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("#", 2)
        if len(parts) < 2:
            continue
        rel, ln = parts[0], parts[1]
        snippet = parts[2] if len(parts) > 2 else ""
        if not ln.isdigit():
            continue
        recs.append((rel, int(ln), snippet))
    return recs


def resolve_source(work: Path, rel: str) -> Path | None:
    rel = rel.lstrip("/")
    cands = [
        work / rel,
        work / "source" / rel,
        work / "src" / rel,
        work / "src/main/java" / rel,
        work / "src/java" / rel,
        work / "gson/src/main/java" / rel,
    ]
    for c in cands:
        if c.is_file():
            return c
    name = Path(rel).name
    hits = list(work.rglob(name))
    hits = [h for h in hits if h.is_file() and "test" not in str(h).lower()]
    return hits[0] if len(hits) == 1 else None


def excerpt(path: Path, center: int, radius: int = 40) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lo = max(1, center - radius)
    hi = min(len(lines), center + radius)
    out = []
    for i in range(lo, hi + 1):
        mark = ">>>" if i == center else "   "
        out.append(f"{mark} {i}: {lines[i - 1]}")
    return "\n".join(out)


def combined_output(proc: subprocess.CompletedProcess) -> str:
    return "\n".join(x for x in (proc.stdout or "", proc.stderr or "") if x)


def triggering_tests(work: Path) -> list[str]:
    proc = run(["defects4j", "export", "-p", "tests.trigger", "-w", str(work)], timeout=60)
    text = combined_output(proc)
    # stdout has no trailing newline; do not glue it onto the ant stderr line.
    return re.findall(r"(?:[A-Za-z_][\w.$]*)::[A-Za-z_]\w*", text)


def test_triggering(work: Path, tests: list[str]) -> tuple[bool, str]:
    logs = []
    all_ok = True
    if not tests:
        proc = run(["defects4j", "test", "-w", str(work)], timeout=1800)
        out = redact(combined_output(proc))
        fail_n = -1
        m = re.search(r"Failing tests:\s*(\d+)", out)
        if m:
            fail_n = int(m.group(1))
        fail_file = work / "failing_tests"
        extra = fail_file.read_text(encoding="utf-8", errors="replace") if fail_file.exists() else ""
        return fail_n == 0, out + "\n" + redact(extra)
    for t in tests:
        proc = run(["defects4j", "test", "-w", str(work), "-t", t], timeout=400)
        out = redact(combined_output(proc))
        logs.append(out)
        fail_file = work / "failing_tests"
        extra = fail_file.read_text(encoding="utf-8", errors="replace") if fail_file.exists() else ""
        logs.append(redact(extra))
        m = re.search(r"Failing tests:\s*(\d+)", out)
        if m:
            if int(m.group(1)) != 0:
                all_ok = False
        elif "Failing tests: 0" not in out:
            all_ok = False
    return all_ok, "\n".join(logs)


def full_tests(work: Path) -> tuple[bool, str]:
    proc = run(["defects4j", "test", "-w", str(work)], timeout=1800)
    out = redact(combined_output(proc))
    fail_file = work / "failing_tests"
    extra = fail_file.read_text(encoding="utf-8", errors="replace") if fail_file.exists() else ""
    m = re.search(r"Failing tests:\s*(\d+)", out)
    n = int(m.group(1)) if m else -1
    return n == 0, out + "\n" + redact(extra)


def llm_creds() -> tuple[str, str, str]:
    dotenv: dict[str, str] = {}
    src = "missing"
    for cand in (RA_AGENT / ".env", ROOT / ".env"):
        if cand.exists():
            dotenv.update(load_dotenv(cand))
            src = str(cand)
    if os.environ.get("OPENAI_API_KEY"):
        key = os.environ["OPENAI_API_KEY"]
        src = "process environment"
    else:
        key = dotenv.get("OPENAI_API_KEY", "")
    base = (
        os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENAI_API_BASE_URL")
        or dotenv.get("OPENAI_API_BASE")
        or dotenv.get("OPENAI_API_BASE_URL")
        or "https://api.deepseek.com"
    )
    return key, base, src


def call_llm(messages: list[dict]) -> str:
    key, base, src = llm_creds()
    if not key or "换成" in key or "PLACEHOLDER" in key:
        raise SystemExit(f"No usable OPENAI_API_KEY (looked at {src})")
    import openai

    openai.api_key = key
    openai.api_base = base.rstrip("/")
    if not openai.api_base.endswith("/v1"):
        openai.api_base = openai.api_base + "/v1"
    resp = openai.ChatCompletion.create(
        model=MODEL,
        temperature=0,
        messages=messages,
    )
    return resp["choices"][0]["message"]["content"]


def parse_edits(text: str) -> list[dict]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json

            data = json.loads(repair_json(text))
        except Exception:
            return []
    if isinstance(data, dict) and "edits" in data:
        data = data["edits"]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict)]


def apply_edits(work: Path, edits: list[dict]) -> str:
    notes = []
    for e in edits:
        rel = str(e.get("file") or e.get("path") or "")
        action = str(e.get("action") or "replace")
        try:
            line_no = int(e.get("line") or 0)
        except (TypeError, ValueError):
            line_no = 0
        new_text = str(e.get("text") or e.get("new_line") or "")
        path = resolve_source(work, rel) if rel else None
        if path is None and rel:
            notes.append(f"skip missing file {rel}")
            continue
        if path is None or line_no < 1:
            notes.append("skip bad edit")
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if line_no > len(lines):
            notes.append(f"skip line {line_no} > {len(lines)} in {path.name}")
            continue
        if not new_text.endswith("\n"):
            new_text += "\n"
        if action == "insert_after":
            lines.insert(line_no, new_text)
        else:
            lines[line_no - 1] = new_text
        path.write_text("".join(lines), encoding="utf-8")
        notes.append(f"{action} {path.relative_to(work)}#{line_no}")
    return "; ".join(notes) if notes else "no edits applied"


def restore_sources(work: Path) -> None:
    git_dir = work / ".git"
    if git_dir.exists():
        run(["git", "checkout", "--", "."], cwd=work, timeout=60)


def checkout(project: str, bid: str) -> Path:
    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    dest = WORK_ROOT / f"{project.lower()}_{bid}_buggy"
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    proc = run(
        ["defects4j", "checkout", "-p", project, "-v", f"{bid}b", "-w", str(dest)],
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(redact(combined_output(proc)))
    compile_proc = run(["defects4j", "compile", "-w", str(dest)], timeout=900)
    if compile_proc.returncode != 0:
        raise RuntimeError(
            "compile failed: "
            + redact(compile_proc.stderr or compile_proc.stdout or "")
        )
    return dest


def build_context(work: Path, recs: list[tuple[str, int, str]]) -> str:
    radius = 40
    if len(recs) > 3:
        radius = 25
    if len(recs) > 6:
        radius = 15
    chunks = []
    for rel, ln, snippet in recs:
        path = resolve_source(work, rel)
        if path is None:
            chunks.append(f"MISSING FILE {rel} line {ln} snippet={snippet}")
            continue
        chunks.append(
            f"FILE {rel} (resolved {path.relative_to(work)}) line {ln} labeled `{snippet}`\n"
            f"{excerpt(path, ln, radius=radius)}"
        )
    return "\n\n".join(chunks)


def dump_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def run_bug(project: str, bid: str, max_rounds: int) -> dict:
    t0 = time.time()
    recs = buggy_line_records(project, bid)
    work = checkout(project, bid)
    tests = triggering_tests(work)
    print(f"  triggering tests: {tests}", flush=True)
    if not tests:
        raise RuntimeError("could not parse Defects4J triggering tests")
    ok0, log0 = test_triggering(work, tests)
    messages = [
        {
            "role": "system",
            "content": (
                "You are ChatRepair-style APR. Given buggy Java and failing tests, "
                "propose a minimal patch. Reply with JSON only: "
                '{"edits":[{"file":"relative/java/path.java","action":"replace|insert_after","line":123,"text":"        new code;"}]}. '
                "Use 1-based line numbers from the excerpts. Do not search other files. "
                "For FAULT_OF_OMISSION use insert_after at the marked line."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Bug {project}-{bid}. Triggering tests: {tests}\n\n"
                f"Initial test output:\n{log0[-4000:]}\n\n"
                f"Buggy locations (perfect FL):\n{build_context(work, recs)}"
            ),
        },
    ]
    history: list[dict] = []
    plausible = False
    last_reply = ""
    out = OUT_ROOT / f"{project}_{bid}.json"
    for rnd in range(1, max_rounds + 1):
        restore_sources(work)
        print(f"  round {rnd}/{max_rounds} {project} {bid}", flush=True)
        try:
            last_reply = call_llm(messages)
        except Exception as e:
            history.append({"round": rnd, "error": redact(str(e))})
            break
        edits = parse_edits(last_reply)
        if not edits:
            feedback = "Could not parse JSON edits. Reply with the JSON object only."
            history.append(
                {
                    "round": rnd,
                    "edits": [],
                    "apply": "no edits applied",
                    "trigger_pass": False,
                    "reply_head": redact(last_reply[:1500]),
                }
            )
            messages.append({"role": "assistant", "content": last_reply})
            messages.append({"role": "user", "content": feedback})
            dump_json(out, _result(project, bid, plausible, tests, history, t0))
            continue
        note = apply_edits(work, edits)
        compile_proc = run(["defects4j", "compile", "-w", str(work)], timeout=900)
        if compile_proc.returncode != 0:
            feedback = "COMPILE FAILED\n" + redact(
                (compile_proc.stderr or compile_proc.stdout or "")[-2500:]
            )
            ok, log = False, feedback
        else:
            ok, log = test_triggering(work, tests)
            feedback = log[-2500:]
        history.append(
            {
                "round": rnd,
                "edits": edits,
                "apply": note,
                "trigger_pass": ok,
                "reply_head": redact(last_reply[:1500]),
            }
        )
        if ok:
            full_ok, full_log = full_tests(work)
            history[-1]["full_pass"] = full_ok
            history[-1]["full_log_tail"] = full_log[-1500:]
            if full_ok:
                plausible = True
                dump_json(out, _result(project, bid, plausible, tests, history, t0))
                break
            feedback = "Triggering tests passed but the full suite still fails:\n" + full_log[-2500:]
        messages.append({"role": "assistant", "content": last_reply})
        messages.append(
            {
                "role": "user",
                "content": "The patch is still wrong. Test/compile feedback:\n" + feedback,
            }
        )
        dump_json(out, _result(project, bid, plausible, tests, history, t0))
    return _result(project, bid, plausible, tests, history, t0)


def _result(project: str, bid: str, plausible: bool, tests: list[str], history: list, t0: float) -> dict:
    return {
        "bug": f"{project} {bid}",
        "plausible": plausible,
        "model": MODEL,
        "triggering_tests": tests,
        "rounds": len(history),
        "seconds": round(time.time() - t0, 1),
        "history": history,
    }


def slim(result: dict) -> dict:
    return {k: result.get(k) for k in ("bug", "plausible", "rounds", "seconds", "error")}


def already_done(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    tests = data.get("triggering_tests") or []
    if any("Running ant" in str(t) or " " in str(t) for t in tests):
        return False
    if data.get("error"):
        return False
    if data.get("plausible"):
        return True
    return int(data.get("rounds") or 0) >= MAX_ROUNDS


def main() -> int:
    parser = argparse.ArgumentParser(description="ChatRepair-style hardcoded repair loop")
    parser.add_argument("--bugfile", default=str(ROOT / "demos" / "sample10.txt"))
    parser.add_argument("bugs", nargs="*", help="Optional Project Index pairs, e.g. Closure 38")
    parser.add_argument("--force", action="store_true", help="Re-run bugs that already have JSON")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    key, base, src = llm_creds()
    print(
        f"LLM creds source={src} key_len={len(key)} base={base} model={MODEL}",
        flush=True,
    )
    if not key or "换成" in key or "PLACEHOLDER" in key:
        raise SystemExit("No usable OPENAI_API_KEY. Put it in report_reproduct/.env (not .env.example).")
    hb = HeartbeatThread()
    hb.start()
    heartbeat("chatrepair_loop start")
    bugs = parse_bugs(Path(args.bugfile))
    if args.bugs:
        if len(args.bugs) % 2 != 0:
            raise SystemExit("bugs must be Project Index pairs")
        want = {(args.bugs[i], args.bugs[i + 1]) for i in range(0, len(args.bugs), 2)}
        bugs = [b for b in bugs if b in want] or [
            (args.bugs[i], args.bugs[i + 1]) for i in range(0, len(args.bugs), 2)
        ]

    summary = []
    for proj, bid in bugs:
        out = OUT_ROOT / f"{proj}_{bid}.json"
        print(f"=== CR-loop {proj} {bid} ===", flush=True)
        hb.msg = f"chatrepair {proj} {bid}"
        heartbeat(hb.msg)
        if already_done(out) and not args.force:
            result = json.loads(out.read_text(encoding="utf-8"))
            print("skip existing", json.dumps(slim(result), ensure_ascii=False), flush=True)
            summary.append(result)
            continue
        try:
            result = run_bug(proj, bid, args.max_rounds)
        except Exception as e:
            result = {
                "bug": f"{proj} {bid}",
                "plausible": False,
                "error": redact(str(e))[-2000:],
                "rounds": 0,
            }
        dump_json(out, result)
        print(json.dumps(slim(result), ensure_ascii=False), flush=True)
        summary.append(result)
    (OUT_ROOT / "summary.json").write_text(
        json.dumps([slim(r) for r in summary], indent=2),
        encoding="utf-8",
    )
    n_ok = sum(1 for r in summary if r.get("plausible"))
    print(f"DONE {n_ok}/{len(summary)} plausible", flush=True)
    heartbeat(f"chatrepair_loop done {n_ok}/{len(summary)}")
    hb.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
