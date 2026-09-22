#!/usr/bin/env python3
"""Write comparison figures (SVG + a single HTML page). No matplotlib required."""

from __future__ import annotations

import functools
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evidence" / "compare_sample10"
CR_DIR = OUT / "chatrepair"
RA_SETUPS = ROOT / "vendor" / "RepairAgent" / "repair_agent" / "experimental_setups"
SAMPLE10 = ROOT / "demos" / "sample10.txt"
SAMPLE = ROOT / "demos" / "sample_all.txt"
if not SAMPLE.exists():
    SAMPLE = SAMPLE10
RA_FIXED = ROOT / "vendor" / "RepairAgent" / "data" / "final_list_of_fixed_bugs"
CR_FIXED = ROOT / "vendor" / "RepairAgent" / "repair_agent" / "experimental_setups" / "chatrepair_all"

FILL = {
    "yes": "#1b7f4e",
    "no": "#b42318",
    "pending": "#98a2b3",
    "error": "#dc6803",
    "?": "#667085",
}
LABEL = {"yes": "修到", "no": "未修", "pending": "待跑", "error": "出错", "?": "?"}


def _bug_lines(path: Path) -> list[str]:
    bugs = []
    if not path.exists():
        return bugs
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            bugs.append(line)
    return bugs


def load_bugs() -> list[str]:
    return _bug_lines(SAMPLE)


def load_sample10() -> list[str]:
    return _bug_lines(SAMPLE10)


def _names_from_list(path: Path) -> set[str]:
    names: set[str] = set()
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().replace("-", " ")
        if line:
            names.add(line)
    return names


@functools.lru_cache(maxsize=1)
def paper_sets() -> tuple[set[str], set[str]]:
    return _names_from_list(RA_FIXED), _names_from_list(CR_FIXED)


def paper_flags(bug: str) -> tuple[str, str]:
    ra_set, cr_set = paper_sets()
    return ("yes" if bug in ra_set else "no", "yes" if bug in cr_set else "no")


def cr_status(bug: str) -> dict:
    proj, idx = bug.split()
    p = CR_DIR / f"{proj}_{idx}.json"
    if not p.exists():
        return {"status": "pending"}
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("plausible"):
        st = "yes"
    elif data.get("error"):
        st = "error"
    elif int(data.get("rounds") or 0) >= 12:
        st = "no"
    else:
        st = "pending"
    return {
        "status": st,
        "rounds": data.get("rounds"),
        "seconds": data.get("seconds"),
        "model": data.get("model"),
    }


def count_concat_json(text: str) -> int:
    dec = json.JSONDecoder()
    i = n = 0
    s = text.strip()
    while i < len(s):
        while i < len(s) and s[i].isspace():
            i += 1
        if i >= len(s):
            break
        try:
            _, end = dec.raw_decode(s, i)
        except json.JSONDecodeError:
            break
        n += 1
        i = end
    return n


def ra_cycles(exp: Path, proj: str, idx: str) -> int | None:
    """LLM queries for one bug in one experiment. Paper: one cycle = one query.

    Prefer the largest of: parsed response objects, saved_context.cycle_count,
    and prompt_history chat blocks. Response JSON often stops parsing early
    when thoughts contain raw newlines, so JSON-only counts under-report.
    """
    stem = f"{proj}_{idx}"
    found: list[int] = []
    resp = exp / "responses" / f"model_responses_{stem}"
    if resp.exists() and resp.stat().st_size:
        n = count_concat_json(resp.read_text(encoding="utf-8", errors="replace"))
        if n:
            found.append(n)
    ctx = exp / "saved_contexts" / f"saved_context_{stem}"
    if ctx.exists():
        try:
            data = json.loads(ctx.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        c = data.get("cycle_count")
        if isinstance(c, int) and c > 0:
            found.append(c)
    hist = exp / "logs" / f"prompt_history_{stem}"
    if hist.exists():
        n = hist.read_text(encoding="utf-8", errors="replace").count("============== ChatSequence")
        if n:
            found.append(n)
    return max(found) if found else None


def status_label(status: str, rounds=None) -> str:
    base = LABEL.get(status, status)
    if rounds is None or rounds == "":
        return base
    return f"{base}·{rounds}"


@functools.lru_cache(maxsize=1)
def ra_index() -> dict:
    hits: dict[str, dict] = {}
    if not RA_SETUPS.exists():
        return hits
    for exp in sorted(RA_SETUPS.glob("experiment_*"), key=lambda p: int(p.name.split("_")[1])):
        names: set[str] = set()
        patch_dir = exp / "plausible_patches"
        if patch_dir.exists():
            for f in patch_dir.glob("plausible_patches_*.json"):
                stem = f.stem.replace("plausible_patches_", "")
                if "_" not in stem:
                    continue
                proj, idx = stem.rsplit("_", 1)
                name = f"{proj} {idx}"
                names.add(name)
                try:
                    payload = json.loads(f.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    payload = []
                hits[name] = {
                    "status": "yes" if payload else "no",
                    "exp": exp.name,
                    "rounds": ra_cycles(exp, proj, idx),
                }
        log_dir = exp / "logs"
        if log_dir.exists():
            for f in log_dir.glob("prompt_history_*"):
                stem = f.name.replace("prompt_history_", "")
                if "_" not in stem:
                    continue
                proj, idx = stem.rsplit("_", 1)
                name = f"{proj} {idx}"
                names.add(name)
                hits.setdefault(
                    name,
                    {
                        "status": "no",
                        "exp": exp.name,
                        "rounds": ra_cycles(exp, proj, idx),
                    },
                )
        for name in names:
            if hits[name].get("rounds") is None:
                proj, idx = name.split()
                hits[name]["rounds"] = ra_cycles(exp, proj, idx)
    return hits


def ra_status(bug: str) -> dict:
    return ra_index().get(bug, {"status": "pending", "rounds": None})


def chart1_cr() -> dict:
    p = CR_DIR / "Chart_1.json"
    if not p.exists():
        return {"status": "pending"}
    data = json.loads(p.read_text(encoding="utf-8"))
    patch = ""
    hist = data.get("history") or []
    if hist:
        edits = hist[-1].get("edits") or []
        if edits:
            patch = str(edits[-1].get("text") or "").strip()
    return {
        "status": "yes" if data.get("plausible") else "no",
        "rounds": data.get("rounds"),
        "seconds": data.get("seconds"),
        "patch": patch,
        "model": data.get("model") or "deepseek-chat",
    }


def chart1_ra() -> dict:
    best = {"status": "pending", "patch": "", "exp": ""}
    if not RA_SETUPS.exists():
        return best
    for exp in sorted(RA_SETUPS.glob("experiment_*"), key=lambda p: int(p.name.split("_")[1])):
        f = exp / "plausible_patches" / "plausible_patches_Chart_1.json"
        if not f.exists():
            continue
        try:
            payload = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = []
        patch = ""
        for item in payload:
            mods = []
            body = item.get("patch")
            if isinstance(body, dict):
                mods = body.get("modifications") or []
            elif isinstance(body, list) and body:
                mods = body[0].get("modifications") or []
            for m in mods:
                line = str(m.get("modified_line") or "")
                if "dataset == null" in line:
                    patch = line.strip()
                    break
            if patch:
                break
        if not patch and payload:
            patch = "(plausible patches saved)"
        best = {
            "status": "yes" if payload else "no",
            "patch": patch,
            "exp": exp.name,
            "rounds": ra_cycles(exp, "Chart", "1"),
        }
    return best


def svg_cell(x: float, y: float, w: float, h: float, status: str, text: str | None = None) -> str:
    fill = FILL.get(status, FILL["?"])
    label = text if text is not None else LABEL.get(status, status)
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="6" fill="{fill}"/>'
        f'<text x="{x + w / 2:.1f}" y="{y + h / 2 + 5:.1f}" text-anchor="middle" '
        f'fill="#fff" font-size="13" font-family="ui-sans-serif,system-ui,sans-serif">{html.escape(label)}</text>'
    )


def grid_svg(rows: list[dict]) -> str:
    cols = ["Bug", "论文 RA164", "论文 CR162", "本次 CR", "本次 RA"]
    col_w = [170, 110, 110, 140, 140]
    x0, y0 = 20, 50
    row_h = 32
    width = 20 + sum(col_w) + 20
    height = y0 + row_h * (len(rows) + 1) + 36
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="20" y="28" font-size="18" font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">'
        f"同一 DeepSeek，两种流水线（N={len(rows)}，不是 Table III）</text>",
    ]
    x = x0
    for i, title in enumerate(cols):
        parts.append(
            f'<text x="{x + 8}" y="{y0 + 20}" font-size="12" font-family="ui-sans-serif,system-ui,sans-serif" '
            f'fill="#475467">{html.escape(title)}</text>'
        )
        x += col_w[i]
    for r, row in enumerate(rows):
        y = y0 + row_h * (r + 1)
        parts.append(
            f'<text x="{x0 + 8}" y="{y + 21}" font-size="13" font-family="ui-sans-serif,system-ui,sans-serif" '
            f'fill="#101828">{html.escape(row["bug"])}</text>'
        )
        x = x0 + col_w[0]
        for key, w, rkey in (
            ("paper_ra", col_w[1], None),
            ("paper_cr", col_w[2], None),
            ("ours_cr", col_w[3], "cr_rounds"),
            ("ours_ra", col_w[4], "ra_rounds"),
        ):
            label = status_label(row[key], row.get(rkey) if rkey else None)
            parts.append(svg_cell(x + 6, y + 4, w - 12, row_h - 8, row[key], text=label))
            x += w
    parts.append("</svg>")
    return "\n".join(parts)


def bars_svg(cr_yes: int, ra_yes: int, n: int) -> str:
    width, height = 640, 280
    max_h = 160
    base = 220
    bar_w = 90
    xs = (160, 390)

    def bar(x: int, val: int, color: str, name: str) -> str:
        h = 8 if n == 0 else max(8, int(max_h * val / n))
        y = base - h
        return (
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" rx="8" fill="{color}"/>'
            f'<text x="{x + bar_w / 2}" y="{y - 10}" text-anchor="middle" font-size="20" '
            f'font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">{val}/{n}</text>'
            f'<text x="{x + bar_w / 2}" y="{base + 28}" text-anchor="middle" font-size="14" '
            f'font-family="ui-sans-serif,system-ui,sans-serif" fill="#475467">{html.escape(name)}</text>'
        )

    return "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#fff"/>',
            '<text x="24" y="32" font-size="18" font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">'
            "plausible 题数（触发测试绿且全套 0 failing）</text>",
            bar(xs[0], cr_yes, "#1570ef", "CR-loop-DeepSeek"),
            bar(xs[1], ra_yes, "#7a5af8", "RA-DeepSeek"),
            "</svg>",
        ]
    )


def chart1_svg(cr: dict, ra: dict) -> str:
    def card(x: int, title: str, st: dict) -> str:
        color = FILL.get(st.get("status", "pending"), FILL["pending"])
        patch = html.escape((st.get("patch") or "")[:64] or "（尚无补丁文本）")
        extra = []
        if st.get("rounds") is not None:
            extra.append(f'{st["rounds"]} 轮')
        if st.get("seconds") is not None:
            extra.append(f'{st["seconds"]} 秒')
        if st.get("exp"):
            extra.append(str(st["exp"]))
        meta = html.escape(" · ".join(extra) if extra else LABEL.get(st.get("status", "pending"), ""))
        return (
            f'<rect x="{x}" y="56" width="360" height="150" rx="16" fill="#f8fafc" stroke="#e4e7ec"/>'
            f'<text x="{x + 24}" y="88" font-size="16" font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">{html.escape(title)}</text>'
            f'<rect x="{x + 24}" y="104" width="72" height="28" rx="14" fill="{color}"/>'
            f'<text x="{x + 60}" y="123" text-anchor="middle" fill="#fff" font-size="13" '
            f'font-family="ui-sans-serif,system-ui,sans-serif">{html.escape(LABEL.get(st.get("status","pending"),""))}</text>'
            f'<text x="{x + 24}" y="156" font-size="13" font-family="ui-sans-serif,system-ui,sans-serif" fill="#475467">{meta}</text>'
            f'<text x="{x + 24}" y="182" font-size="13" font-family="ui-monospace,monospace" fill="#101828">{patch}</text>'
        )

    return "\n".join(
        [
            '<svg xmlns="http://www.w3.org/2000/svg" width="780" height="230" viewBox="0 0 780 230">',
            '<rect width="100%" height="100%" fill="#fff"/>',
            '<text x="24" y="32" font-size="18" font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">'
            "Chart-1 冒烟（同一 DeepSeek，两种模式都要先走通）</text>",
            card(24, "ChatRepair 循环", cr),
            card(400, "官方 RepairAgent", ra),
            "</svg>",
        ]
    )


def load_tools():
    import importlib.util

    path = Path(__file__).with_name("tool_usage.py")
    spec = importlib.util.spec_from_file_location("tool_usage", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load tool_usage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def html_page(
    rows: list[dict],
    cr_yes: int,
    ra_yes: int,
    n: int,
    cr1: dict,
    ra1: dict,
    tools: dict | None = None,
    tools_mod=None,
) -> str:
    grid = grid_svg(rows)
    bars = bars_svg(cr_yes, ra_yes, n)
    c1 = chart1_svg(cr1, ra1)
    tools_svg = tools_rate = tools_tables = ""
    if tools and tools_mod:
        tools_svg = tools_mod.svg(tools)
        tools_rate = tools_mod.rate_svg(tools)
        tools_tables = tools_mod.html_tables(tools)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>RepairAgent vs ChatRepair-loop</title>
  <style>
    body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 24px; color: #101828; background: #fff; }}
    h1 {{ font-size: 22px; margin: 0 0 8px; }}
    h2 {{ font-size: 18px; margin: 28px 0 8px; }}
    h3 {{ font-size: 15px; margin: 0 0 8px; }}
    p, li {{ color: #475467; line-height: 1.5; }}
    .note {{ background: #fef3c7; border: 1px solid #fcd34d; padding: 12px 16px; border-radius: 10px; }}
    .panel {{ margin: 24px 0; overflow-x: auto; }}
    code {{ background: #f2f4f7; padding: 1px 6px; border-radius: 4px; }}
    .cols {{ display: flex; gap: 32px; flex-wrap: wrap; }}
    table.tools {{ border-collapse: collapse; font-size: 14px; min-width: 280px; }}
    table.tools th, table.tools td {{ border-bottom: 1px solid #e4e7ec; padding: 6px 10px; text-align: left; }}
    table.tools td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    table.tools th {{ color: #475467; font-weight: 600; }}
  </style>
</head>
<body>
  <h1>同一 DeepSeek：硬编码循环 vs 官方 RepairAgent</h1>
  <p>课上打开这一页即可。数字只覆盖本页画出的题目，<b>不是</b>论文 Table III（164 vs 162）。</p>
  <p class="note">真 key 在 gitignore 的 <code>.env</code> 里。图由 <code>python scripts/visualize_compare.py</code> 从 JSON 重画。</p>
  <div class="panel">{c1}</div>
  <div class="panel">{bars}</div>
  <div class="panel">{grid}</div>
  <p>绿色=plausible（触发测试绿且全套 0 failing）。灰=还没跑完。格子里「修到·N」的 N：CR 是硬编码循环轮数，RA 是论文里的 cycle（一次 LLM 查询）。CR-loop 当前 {cr_yes}/{n}，RA 当前 {ra_yes}/{n}。</p>
  <div class="panel">{tools_svg}</div>
  <div class="panel">{tools_rate}</div>
  {tools_tables}
</body>
</html>
"""


def build_rows() -> tuple[list[dict], int, int]:
    rows = []
    cr_yes = ra_yes = 0
    for bug in load_bugs():
        paper_ra, paper_cr = paper_flags(bug)
        cr = cr_status(bug)
        ra = ra_status(bug)
        if cr["status"] == "yes":
            cr_yes += 1
        if ra["status"] == "yes":
            ra_yes += 1
        rows.append(
            {
                "bug": bug,
                "paper_ra": paper_ra,
                "paper_cr": paper_cr,
                "ours_cr": cr["status"],
                "ours_ra": ra["status"],
                "cr_rounds": cr.get("rounds"),
                "ra_rounds": ra.get("rounds"),
            }
        )
    return rows, cr_yes, ra_yes


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, cr_yes, ra_yes = build_rows()
    n = len(rows)
    cr1 = chart1_cr()
    ra1 = chart1_ra()
    tools_mod = load_tools()
    tools = tools_mod.main()
    (OUT / "grid.svg").write_text(grid_svg(rows), encoding="utf-8")
    (OUT / "bars.svg").write_text(bars_svg(cr_yes, ra_yes, n), encoding="utf-8")
    (OUT / "chart1_smoke.svg").write_text(chart1_svg(cr1, ra1), encoding="utf-8")
    (OUT / "compare.html").write_text(
        html_page(rows, cr_yes, ra_yes, n, cr1, ra1, tools=tools, tools_mod=tools_mod),
        encoding="utf-8",
    )
    snapshot = {
        "n": n,
        "cr_yes": cr_yes,
        "ra_yes": ra_yes,
        "rows": rows,
        "chart1": {"cr": cr1, "ra": ra1},
        "tools": tools_mod.slim_payload(tools),
        "disclaimer": "Not Table III. Same DeepSeek, this sample only. Tool split is plausible vs not, not Figure 10.",
    }
    (OUT / "snapshot.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT / 'compare.html'}")
    print(f"Chart-1 CR={cr1.get('status')} rounds={cr1.get('rounds')} RA={ra1.get('status')} rounds={ra1.get('rounds')} exp={ra1.get('exp')}")
    print(f"sample CR={cr_yes}/{n} RA={ra_yes}/{n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
