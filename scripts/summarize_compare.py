#!/usr/bin/env python3
"""Fill evidence/compare_sample10/RESULTS.md from CR-loop JSON + RepairAgent experiment dirs."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA_SETUPS = ROOT / "vendor" / "RepairAgent" / "repair_agent" / "experimental_setups"
CR_DIR = ROOT / "evidence" / "compare_sample10" / "chatrepair"
OUT = ROOT / "evidence" / "compare_sample10" / "RESULTS.md"


def cr_row(bug: str) -> dict:
    proj, idx = bug.split()
    p = CR_DIR / f"{proj}_{idx}.json"
    if not p.exists():
        return {"status": "pending"}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {
        "status": "yes" if data.get("plausible") else ("error" if data.get("error") else ("no" if int(data.get("rounds") or 0) >= 12 else "pending")),
        "rounds": data.get("rounds"),
        "seconds": data.get("seconds"),
        "error": (data.get("error") or "")[:180],
    }


def table_rows(viz, bugs: list[str], running: set[str]) -> tuple[list[str], int, int]:
    lines = [
        "| Bug | 论文 RA164 | 论文 ChatRepair162 | CR-loop-DeepSeek | RA-DeepSeek | CR 轮数 | RA 轮数 | CR 秒 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    cr_yes = ra_yes = 0
    for bug in bugs:
        in_ra, in_cr = viz.paper_flags(bug)
        crow = viz.cr_status(bug)
        rhit = viz.ra_status(bug)
        if bug in running:
            rhit = {"status": "pending", "rounds": None, "exp": None}
        cr_cell = crow["status"]
        if crow["status"] == "yes":
            cr_yes += 1
        if rhit.get("status") == "pending" or rhit.get("status") is None:
            ra_cell = "pending"
        elif rhit.get("status") == "yes":
            ra_cell = f"yes ({rhit.get('exp')})"
            ra_yes += 1
        else:
            ra_cell = f"no ({rhit.get('exp')})"
        cr_rounds = crow.get("rounds") if crow.get("rounds") is not None else ""
        ra_rounds = rhit.get("rounds") if rhit.get("rounds") is not None else ""
        seconds = crow.get("seconds") if crow.get("seconds") is not None else ""
        lines.append(
            f"| {bug} | {in_ra} | {in_cr} | {cr_cell} | {ra_cell} | {cr_rounds} | {ra_rounds} | {seconds} |"
        )
    return lines, cr_yes, ra_yes


def _load_mod(name: str):
    import importlib.util

    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_viz():
    return _load_mod("visualize_compare.py")


def _load_tools():
    return _load_mod("tool_usage.py")


def called_goals_accomplished(exp: Path, proj: str, idx: str) -> bool:
    resp = exp / "responses" / f"model_responses_{proj}_{idx}"
    if not resp.exists() or not resp.stat().st_size:
        return False
    dec = json.JSONDecoder()
    i = 0
    s = resp.read_text(encoding="utf-8", errors="replace").strip()
    while i < len(s):
        while i < len(s) and s[i].isspace():
            i += 1
        if i >= len(s):
            break
        try:
            obj, end = dec.raw_decode(s, i)
        except json.JSONDecodeError:
            break
        i = end
        if not isinstance(obj, dict):
            continue
        cmd = obj.get("command")
        name = cmd.get("name") if isinstance(cmd, dict) else cmd
        if name == "goals_accomplished":
            return True
    return False


def running_ra_bugs() -> set[str]:
    import subprocess

    running: set[str] = set()
    proc = subprocess.run(["pgrep", "-af", "repairagent.py run"], capture_output=True, text=True)
    for ln in (proc.stdout or "").splitlines():
        if "repairagent.py run" not in ln or "pgrep" in ln:
            continue
        if "--bugs " in ln and "--bugs-file" not in ln:
            rest = ln.split("--bugs", 1)[1]
            parts = rest.strip().split()
            if len(parts) >= 2 and not parts[0].startswith("-"):
                running.add(f"{parts[0]} {parts[1]}")
    return running


def export_ra_slim(viz) -> None:
    """Vendor experiment dirs are gitignored; keep a one-row JSON per sample10 bug."""
    running = running_ra_bugs()
    out = ROOT / "evidence" / "compare_sample10" / "repairagent"
    out.mkdir(parents=True, exist_ok=True)
    for bug in viz.load_bugs():
        if bug in running:
            continue
        hit = viz.ra_status(bug)
        if hit.get("status") in (None, "pending"):
            continue
        proj, idx = bug.split()
        exp_name = hit.get("exp") or ""
        exp = RA_SETUPS / exp_name if exp_name else None
        payload = {
            "bug": bug,
            "exp": exp_name,
            "plausible": hit.get("status") == "yes",
            "rounds": hit.get("rounds"),
            "goals_accomplished": bool(exp and called_goals_accomplished(exp, proj, idx)),
        }
        dest = out / f"{proj}_{idx}.json"
        if dest.exists():
            try:
                old = json.loads(dest.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                old = {}
            if old.get("note"):
                payload["note"] = old["note"]
        dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    viz = load_viz()
    bugs = viz.load_bugs()
    original = viz.load_sample10()
    extra = [b for b in bugs if b not in set(original)]
    running = running_ra_bugs()
    orig_lines, orig_cr, orig_ra = table_rows(viz, original, running)
    extra_lines, extra_cr, extra_ra = table_rows(viz, extra, running) if extra else ([], 0, 0)
    cr_yes = orig_cr + extra_cr
    ra_yes = orig_ra + extra_ra
    cr1 = viz.chart1_cr()
    ra1 = viz.chart1_ra()
    lines = [
        f"# 对比结果（DeepSeek，N={len(bugs)}）",
        "",
        "不是论文 Table III（164 vs 162）。同一模型、同一题单、两种流水线。官方 RepairAgent 逻辑未改。",
        "plausible = 触发测试绿，且 `defects4j test` 全套 0 failing。",
        "CR 轮数 = 硬编码循环次数。RA 轮数 = 论文里的 cycle（一次 LLM 查询，来自 `model_responses_*`）。",
        "",
        f"合计 CR-loop plausible: **{cr_yes}/{len(bugs)}**. RA plausible: **{ra_yes}/{len(bugs)}**。",
        "",
        f"## 原 sample10（seed=42，N={len(original)}）",
        "",
        f"CR **{orig_cr}/{len(original)}**，RA **{orig_ra}/{len(original)}**。",
        "",
    ]
    lines += orig_lines
    if extra:
        lines += [
            "",
            f"## 加抽 extra（同一 RNG 继续 sample，N={len(extra)}）",
            "",
            f"CR **{extra_cr}/{len(extra)}**，RA **{extra_ra}/{len(extra)}**。",
            "",
        ]
        lines += extra_lines
    notes: list[str] = []
    slim = ROOT / "evidence" / "compare_sample10" / "repairagent"
    if slim.exists():
        for p in sorted(slim.glob("*.json")):
            if ".before_retest_" in p.name:
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            note = (data.get("note") or "").strip()
            if note:
                notes.append(f"- **{data.get('bug') or p.stem}**：{note}")
    extra_notes = ROOT / "evidence" / "compare_sample10" / "notes.txt"
    if extra_notes.exists():
        for raw in extra_notes.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line:
                notes.append(f"- {line}")
    halt_note = ROOT / "evidence" / "compare_sample10" / "halt.txt"
    if halt_note.exists():
        extra_note = halt_note.read_text(encoding="utf-8").strip()
        if extra_note:
            notes.append(f"- {extra_note.replace(chr(10), ' ')}")
    if notes:
        lines += ["", "## 备注", ""] + notes
    lines += [
        "",
        "## Chart-1 冒烟（不在这张题单里）",
        "",
        "| 流水线 | plausible | 轮数 | 备注 |",
        "|---|---|---|---|",
        f"| CR-loop-DeepSeek | {cr1.get('status')} | {cr1.get('rounds') if cr1.get('rounds') is not None else ''} | {cr1.get('patch') or ''} |",
        f"| RA-DeepSeek | {ra1.get('status')} | {ra1.get('rounds') if ra1.get('rounds') is not None else ''} | {ra1.get('exp') or ''} {ra1.get('patch') or ''} |",
        "",
        "结论只覆盖已列出的题。ChatRepair 侧是本仓库的硬编码循环，不是 Xia 原实现 + GPT-3.5。",
        "",
    ]
    tools_mod = _load_tools()
    tools_body = tools_mod.markdown(tools_mod.collect())
    if tools_body.startswith("# "):
        tools_body = "## " + tools_body[2:]
    lines += [tools_body]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    orig_ra_status = viz.ra_status

    def ra_status_safe(bug: str) -> dict:
        if bug in running:
            return {"status": "pending", "rounds": None, "exp": None}
        return orig_ra_status(bug)

    viz.ra_status = ra_status_safe
    viz.ra_index.cache_clear()
    export_ra_slim(viz)
    viz.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
