#!/usr/bin/env python3
"""RQ4-style tool-use tables for our N=25 DeepSeek RepairAgent runs.

Paper Figure 10 splits correct vs unfixed. We only score plausible, so the
split is plausible vs not-plausible. Not a reproduction of Figure 10.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RA_SETUPS = ROOT / "vendor" / "RepairAgent" / "repair_agent" / "experimental_setups"
SLIM = ROOT / "evidence" / "compare_sample10" / "repairagent"
OUT = ROOT / "evidence" / "compare_sample10"

CMD_IN_ASSISTANT = re.compile(r'"command"\s*:\s*\{\s*"name"\s*:\s*"([A-Za-z0-9_]+)"')
GOALS_RE = re.compile(r'"name"\s*:\s*"goals_accomplished"')

CANON = {
    "read_range": "read_range",
    "get_classes_and_methods": "get_classes_and_methods",
    "extract_method_code": "extract_method",
    "extract_method": "extract_method",
    "extract_test_code": "extract_tests",
    "extract_tests": "extract_tests",
    "search_code_base": "search_code_base",
    "find_similar_api_calls": "find_similar_api_calls",
    "extract_similar_functions_calls": "find_similar_api_calls",
    "generate_method_body": "generate_method_body",
    "AI_generates_method_code": "generate_method_body",
    "run_tests": "run_tests",
    "run_fault_localization": "run_fault_localization",
    "write_fix": "write_fix",
    "express_hypothesis": "express_hypothesis",
    "collect_more_information": "collect_more_information",
    "go_back_to_collect_more_info": "collect_more_information",
    "discard_hypothesis": "discard_hypothesis",
    "goals_accomplished": "goal_accomplished",
    "goal_accomplished": "goal_accomplished",
    "missing_command": "missing_command",
}

PAPER_ORDER = [
    "write_fix",
    "read_range",
    "search_code_base",
    "extract_method",
    "express_hypothesis",
    "extract_tests",
    "get_classes_and_methods",
    "find_similar_api_calls",
    "generate_method_body",
    "collect_more_information",
    "discard_hypothesis",
    "run_fault_localization",
    "run_tests",
    "goal_accomplished",
]


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


def load_sample_bugs() -> list[str]:
    sample = ROOT / "demos" / "sample_all.txt"
    if not sample.exists():
        sample = ROOT / "demos" / "sample10.txt"
    bugs = []
    for line in sample.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            bugs.append(line)
    return bugs


def canon(name: str) -> str:
    return CANON.get(name, name)


def _history_names(exp: Path, proj: str, idx: str) -> list[str]:
    ctx = exp / "saved_contexts" / f"saved_context_{proj}_{idx}"
    if not ctx.exists():
        return []
    try:
        data = json.loads(ctx.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    names: list[str] = []
    for item in data.get("commands_history") or []:
        raw = str(item).split(" , ", 1)[0].strip()
        if raw:
            names.append(raw)
    return names


def _response_names(exp: Path, proj: str, idx: str) -> list[str]:
    resp = exp / "responses" / f"model_responses_{proj}_{idx}"
    if not resp.exists() or not resp.stat().st_size:
        return []
    text = resp.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    dec = json.JSONDecoder()
    i = 0
    s = text.strip()
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
        if isinstance(name, str):
            names.append(name)
    names.extend(CMD_IN_ASSISTANT.findall(s[i:]))
    return names


def _prompt_last_names(exp: Path, proj: str, idx: str) -> list[str]:
    hist = exp / "logs" / f"prompt_history_{proj}_{idx}"
    if not hist.exists():
        return []
    text = hist.read_text(encoding="utf-8", errors="replace")
    names: list[str] = []
    for seq in text.split("============== ChatSequence")[1:]:
        blocks = seq.split("--------------- ASSISTANT ----------------")
        if len(blocks) < 2:
            continue
        m = CMD_IN_ASSISTANT.search(blocks[-1])
        if m:
            names.append(m.group(1))
    return names


def _called_goals(exp: Path, proj: str, idx: str) -> bool:
    resp = exp / "responses" / f"model_responses_{proj}_{idx}"
    if not resp.exists() or not resp.stat().st_size:
        return False
    return bool(GOALS_RE.search(resp.read_text(encoding="utf-8", errors="replace")))


def commands_from_experiment(exp: Path, proj: str, idx: str) -> list[str]:
    """Actual tool calls. Prefer saved_context.commands_history (not prompt examples)."""
    hist = _history_names(exp, proj, idx)
    resp = _response_names(exp, proj, idx)
    prompt = _prompt_last_names(exp, proj, idx)
    names = hist
    if len(resp) > len(names):
        names = resp
    if len(prompt) > len(names):
        names = prompt
    if _called_goals(exp, proj, idx) and "goals_accomplished" not in names and "goal_accomplished" not in names:
        names = list(names) + ["goals_accomplished"]
    return [canon(n) for n in names if canon(n) != "missing_command"]


def _avg(group: list[dict], tool: str) -> float:
    if not group:
        return 0.0
    return sum(r["commands"].count(tool) for r in group) / len(group)


def _rate(group: list[dict], tool: str) -> float:
    if not group:
        return 0.0
    return sum(1 for r in group if tool in r["commands"]) / len(group)


def collect() -> dict:
    running = running_ra_bugs()
    rows = []
    skipped = []
    for bug in load_sample_bugs():
        if bug in running:
            skipped.append(f"{bug} (still running)")
            continue
        slim = SLIM / f"{bug.replace(' ', '_')}.json"
        if not slim.exists():
            skipped.append(f"{bug} (no slim JSON)")
            continue
        data = json.loads(slim.read_text(encoding="utf-8"))
        exp_name = data.get("exp") or ""
        exp = RA_SETUPS / exp_name
        if not exp_name or not exp.exists():
            skipped.append(f"{bug} (missing {exp_name})")
            continue
        proj, idx = bug.split()
        cmds = commands_from_experiment(exp, proj, idx)
        rows.append(
            {
                "bug": bug,
                "exp": exp_name,
                "plausible": bool(data.get("plausible")),
                "commands": cmds,
                "n": len(cmds),
                "top": Counter(cmds).most_common(3),
            }
        )
    yes = [r for r in rows if r["plausible"]]
    no = [r for r in rows if not r["plausible"]]
    tools = list(PAPER_ORDER)
    extra = sorted({c for r in rows for c in r["commands"] if c not in tools})
    tools.extend(extra)

    table = []
    for tool in tools:
        y = _avg(yes, tool)
        n = _avg(no, tool)
        tot = sum(r["commands"].count(tool) for r in rows)
        if y == 0 and n == 0 and tot == 0:
            continue
        table.append(
            {
                "tool": tool,
                "avg_yes": y,
                "avg_no": n,
                "rate_yes": _rate(yes, tool),
                "rate_no": _rate(no, tool),
                "total": tot,
            }
        )
    return {
        "n_yes": len(yes),
        "n_no": len(no),
        "n": len(rows),
        "skipped": skipped,
        "table": table,
        "rows": rows,
        "mean_calls_yes": (sum(r["n"] for r in yes) / len(yes)) if yes else 0.0,
        "mean_calls_no": (sum(r["n"] for r in no) / len(no)) if no else 0.0,
        "write_fix_yes": _avg(yes, "write_fix") if yes else 0.0,
        "write_fix_no": _avg(no, "write_fix") if no else 0.0,
        "goals_yes": _rate(yes, "goal_accomplished") if yes else 0.0,
        "goals_no": _rate(no, "goal_accomplished") if no else 0.0,
    }


def markdown(data: dict) -> str:
    lines = [
        "# RepairAgent 工具使用（我们的 N=25，DeepSeek）",
        "",
        "仿论文 RQ4 / Figure 10 的**拆法**，不是复现那张图。",
        "论文按 **correct vs unfixed**（unfixed = 只有 plausible 或完全没绿）。",
        "我们没做人工 correct，所以按 **plausible vs 没过**。",
        "",
        f"计入 **{data['n']}** 题（plausible {data['n_yes']}，没过 {data['n_no']}）。",
    ]
    if data["skipped"]:
        lines.append("未计入：" + "；".join(data["skipped"]) + "。")
    lines += [
        "",
        f"平均每次调用数：plausible **{data['mean_calls_yes']:.1f}**，没过 **{data['mean_calls_no']:.1f}**。",
        f"`write_fix` 平均次数：plausible **{data['write_fix_yes']:.1f}**，没过 **{data['write_fix_no']:.1f}**。",
        f"喊过 `goal_accomplished` 的比例：plausible **{100 * data['goals_yes']:.0f}%**，没过 **{100 * data['goals_no']:.0f}%**。",
        "",
        "## 平均次数 / 题（论文 Figure 10 同款）",
        "",
        "| 工具 | plausible 平均/题 | 没过 平均/题 | 全体次数 |",
        "|---|---:|---:|---:|",
    ]
    for row in data["table"]:
        lines.append(
            f"| `{row['tool']}` | {row['avg_yes']:.2f} | {row['avg_no']:.2f} | {row['total']} |"
        )
    lines += [
        "",
        "## 使用率（至少用过一次的题占比）",
        "",
        "| 工具 | plausible 使用率 | 没过 使用率 |",
        "|---|---:|---:|",
    ]
    for row in data["table"]:
        lines.append(
            f"| `{row['tool']}` | {100 * row['rate_yes']:.0f}% | {100 * row['rate_no']:.0f}% |"
        )
    lines += [
        "",
        "课上先指总次数（没过的题更长：读代码耗在 `read_range`），再指 `goal_accomplished`（只有自己喊下班才出现）。",
        "`write_fix` 两边平均数差不多，是因为 Cli 18 测绿后仍写到 36 次，把 plausible 组抬上去了；论文 Figure 10 会把它算进 unfixed。",
        "`run_tests` 为 0，是因为测试焊在 `write_fix` 里，和论文 RQ4 一致。",
        "论文的 unfixed 还包括「测绿但补丁不正确」；Cli 18 / Math 8 / Jsoup 41 测绿后仍写到预算附近，图里算 plausible，课上不要说成 Figure 10 的 fixed。",
        "",
        "## 每题调用次数（答问用）",
        "",
        "| Bug | plausible | 调用次数 | 最多的三个工具 |",
        "|---|---|---:|---|",
    ]
    for r in data["rows"]:
        top = ", ".join(f"{n}×{c}" for n, c in r["top"]) if r["top"] else "—"
        lines.append(
            f"| {r['bug']} | {'yes' if r['plausible'] else 'no'} | {r['n']} | {top} |"
        )
    lines.append("")
    return "\n".join(lines)


def _bar_svg(data: dict, title: str, as_pct: bool) -> str:
    rows = [r for r in data["table"] if r["tool"] != "missing_command"]
    if not rows:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="720" height="80"></svg>'
    left, row_h, bar_max = 220, 36, 280
    height = 88 + row_h * len(rows) + 20
    width = 760
    if as_pct:
        max_avg = 1.0
    else:
        max_avg = max(max(r["avg_yes"], r["avg_no"]) for r in rows) or 1.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<text x="24" y="26" font-size="16" font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">'
        f"{title}</text>",
        '<text x="24" y="46" font-size="12" font-family="ui-sans-serif,system-ui,sans-serif" fill="#475467">'
        f"plausible {data['n_yes']} vs 没过 {data['n_no']}，不是论文 Figure 10</text>",
        '<rect x="520" y="36" width="12" height="12" rx="2" fill="#1b7f4e"/>',
        '<text x="538" y="47" font-size="12" font-family="ui-sans-serif,system-ui,sans-serif" fill="#475467">plausible</text>',
        '<rect x="620" y="36" width="12" height="12" rx="2" fill="#b42318"/>',
        '<text x="638" y="47" font-size="12" font-family="ui-sans-serif,system-ui,sans-serif" fill="#475467">没过</text>',
    ]
    y0 = 66
    for i, row in enumerate(rows):
        y = y0 + i * row_h
        v_yes = row["rate_yes"] if as_pct else row["avg_yes"]
        v_no = row["rate_no"] if as_pct else row["avg_no"]
        parts.append(
            f'<text x="20" y="{y + 16}" font-size="13" font-family="ui-monospace,monospace" fill="#101828">{row["tool"]}</text>'
        )
        w_yes = max(2, int(bar_max * v_yes / max_avg)) if v_yes else 0
        w_no = max(2, int(bar_max * v_no / max_avg)) if v_no else 0
        lab_yes = f"{100 * v_yes:.0f}%" if as_pct else f"{v_yes:.1f}"
        lab_no = f"{100 * v_no:.0f}%" if as_pct else f"{v_no:.1f}"
        if w_yes:
            parts.append(
                f'<rect x="{left}" y="{y}" width="{w_yes}" height="12" rx="3" fill="#1b7f4e"/>'
                f'<text x="{left + w_yes + 6}" y="{y + 11}" font-size="11" '
                f'font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">{lab_yes}</text>'
            )
        else:
            parts.append(
                f'<text x="{left}" y="{y + 11}" font-size="11" '
                f'font-family="ui-sans-serif,system-ui,sans-serif" fill="#98a2b3">{lab_yes}</text>'
            )
        if w_no:
            parts.append(
                f'<rect x="{left}" y="{y + 16}" width="{w_no}" height="12" rx="3" fill="#b42318"/>'
                f'<text x="{left + w_no + 6}" y="{y + 27}" font-size="11" '
                f'font-family="ui-sans-serif,system-ui,sans-serif" fill="#101828">{lab_no}</text>'
            )
        else:
            parts.append(
                f'<text x="{left}" y="{y + 27}" font-size="11" '
                f'font-family="ui-sans-serif,system-ui,sans-serif" fill="#98a2b3">{lab_no}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)


def svg(data: dict) -> str:
    return _bar_svg(data, "工具平均次数/题", as_pct=False)


def rate_svg(data: dict) -> str:
    return _bar_svg(data, "工具使用率（至少一次）", as_pct=True)


def html_tables(data: dict) -> str:
    avg_rows = []
    rate_rows = []
    for row in data["table"]:
        avg_rows.append(
            "<tr>"
            f"<td><code>{row['tool']}</code></td>"
            f"<td class='num'>{row['avg_yes']:.2f}</td>"
            f"<td class='num'>{row['avg_no']:.2f}</td>"
            f"<td class='num'>{row['total']}</td>"
            "</tr>"
        )
        rate_rows.append(
            "<tr>"
            f"<td><code>{row['tool']}</code></td>"
            f"<td class='num'>{100 * row['rate_yes']:.0f}%</td>"
            f"<td class='num'>{100 * row['rate_no']:.0f}%</td>"
            "</tr>"
        )
    skip = ("未计入：" + "；".join(data["skipped"]) + "。") if data["skipped"] else ""
    return f"""
  <h2>工具使用（仿 RQ4，不是 Figure 10）</h2>
  <p>论文按 correct vs unfixed。我们按 <b>plausible {data['n_yes']}</b> vs <b>没过 {data['n_no']}</b>，共 {data['n']} 题。
  平均调用：plausible <b>{data['mean_calls_yes']:.1f}</b>，没过 <b>{data['mean_calls_no']:.1f}</b>。
  <code>write_fix</code>：{data['write_fix_yes']:.1f} vs {data['write_fix_no']:.1f}。
  {skip}</p>
  <div class="cols">
    <div>
      <h3>平均次数 / 题</h3>
      <table class="tools">
        <thead><tr><th>工具</th><th>plausible</th><th>没过</th><th>全体次数</th></tr></thead>
        <tbody>{''.join(avg_rows)}</tbody>
      </table>
    </div>
    <div>
      <h3>使用率（至少一次）</h3>
      <table class="tools">
        <thead><tr><th>工具</th><th>plausible</th><th>没过</th></tr></thead>
        <tbody>{''.join(rate_rows)}</tbody>
      </table>
    </div>
  </div>
"""


def slim_payload(data: dict) -> dict:
    return {
        "n": data["n"],
        "n_yes": data["n_yes"],
        "n_no": data["n_no"],
        "skipped": data["skipped"],
        "mean_calls_yes": data["mean_calls_yes"],
        "mean_calls_no": data["mean_calls_no"],
        "write_fix_yes": data["write_fix_yes"],
        "write_fix_no": data["write_fix_no"],
        "goals_yes": data["goals_yes"],
        "goals_no": data["goals_no"],
        "table": data["table"],
        "per_bug": [
            {
                "bug": r["bug"],
                "exp": r["exp"],
                "plausible": r["plausible"],
                "n": r["n"],
                "counts": dict(Counter(r["commands"])),
            }
            for r in data["rows"]
        ],
    }


def main() -> dict:
    data = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "TOOLS.md").write_text(markdown(data), encoding="utf-8")
    (OUT / "tools.svg").write_text(svg(data), encoding="utf-8")
    (OUT / "tools_rate.svg").write_text(rate_svg(data), encoding="utf-8")
    (OUT / "tools.json").write_text(
        json.dumps(slim_payload(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT / 'TOOLS.md'} n={data['n']} yes={data['n_yes']} no={data['n_no']}")
    return data


if __name__ == "__main__":
    main()
