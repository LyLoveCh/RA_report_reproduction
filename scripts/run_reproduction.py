#!/usr/bin/env python3
"""RepairAgent course reproduction runner (ICSE 2025).

Default path is $0: official unit tests + Chart-1 mini + apply_changes demo.
Optional --with-d4j runs the real Defects4J Chart-1 red -> published patch -> green.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
REPAIR_AGENT = VENDOR / "RepairAgent"
D4J_HOME = VENDOR / "defects4j"
EVIDENCE = ROOT / "evidence"
WORK = VENDOR / "work"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def say(title: str, body: str = "") -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)
    if body:
        print(body)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, check=check)


def python_bin() -> Path:
    if os.name == "nt":
        p = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        p = ROOT / ".venv" / "bin" / "python"
    if p.exists():
        return p
    return Path(sys.executable)


def _import_ok(py: Path, expr: str) -> bool:
    return subprocess.run([str(py), "-c", expr], capture_output=True).returncode == 0


def ensure_venv() -> Path:
    if not (ROOT / ".venv").exists():
        say("创建虚拟环境", str(ROOT / ".venv"))
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
        py = python_bin()
        subprocess.run([str(py), "-m", "pip", "install", "-U", "pip"], check=True)
    py = python_bin()
    if not _import_ok(py, "import pytest"):
        run([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements-demo.txt")])
    return py


def ensure_repairagent() -> Path:
    if (REPAIR_AGENT / "repair_agent" / "tests").exists():
        return REPAIR_AGENT
    VENDOR.mkdir(parents=True, exist_ok=True)
    say("克隆官方仓库 sola-st/RepairAgent")
    run(["git", "clone", "--depth", "1", "https://github.com/sola-st/RepairAgent.git", str(REPAIR_AGENT)])
    return REPAIR_AGENT


def install_official_test_deps(py: Path) -> None:
    if _import_ok(py, "import pytest, auto_gpt_plugin_template, fuzzywuzzy, pydantic"):
        return
    req = REPAIR_AGENT / "repair_agent" / "requirements-dev.txt"
    raw = req.read_text(encoding="utf-8")
    tmp = ROOT / "evidence" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    stripped = tmp / "requirements-dev.local.txt"
    lines = [ln for ln in raw.splitlines() if "auto-gpt-plugin-template" not in ln]
    stripped.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run([str(py), "-m", "pip", "install", "-r", str(stripped)])
    run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "auto-gpt-plugin-template @ git+https://github.com/Significant-Gravitas/Auto-GPT-Plugin-Template@0.1.0",
        ]
    )


def stage_mini(py: Path) -> None:
    say("阶段 A · Chart-1 缩小版（$0，不需要 Java / Defects4J / API key）")
    print("同一条断言：dataset 非空时图例数量应为 1，出错代码返回 0。")
    log = EVIDENCE / "chart1_mini.log"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            [str(py), "-m", "pytest", str(ROOT / "demos" / "chart1_mini"), "-q"],
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    print(log.read_text(encoding="utf-8", errors="replace"))
    if proc.returncode != 0:
        raise SystemExit("Chart-1 缩小版失败")
    print("记录：", log)


def stage_apply_patch(py: Path) -> None:
    say("阶段 B · 用官方 apply_changes 打上论文公布的 Chart-1 补丁")
    src = ROOT / "demos" / "apply_patch" / "buggy_snippet.java"
    dst = EVIDENCE / "tmp" / "chart1_snippet.java"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    script = dst.parent / "apply_chart1.py"
    script.write_text(
        f"""
import sys
sys.path.insert(0, r"{REPAIR_AGENT / 'repair_agent'}")
from apply_changes import apply_changes
apply_changes({{
    "file_name": r"{dst}",
    "insertions": [],
    "deletions": [],
    "modifications": [{{"line_number": 8, "modified_line": "        if (dataset == null) {{"}}],
}})
print(open(r"{dst}", encoding="utf-8").read())
""",
        encoding="utf-8",
    )
    out = subprocess.check_output([str(py), str(script)], text=True, encoding="utf-8")
    print(out)
    if "if (dataset == null)" not in out:
        raise SystemExit("apply_changes 没有写出论文补丁")
    (EVIDENCE / "apply_changes_chart1.txt").write_text(out, encoding="utf-8")
    print("这就是 RepairAgent write_fix 真正改磁盘的那一步（不调用 LLM）。")


def stage_official_pytest(py: Path) -> None:
    say("阶段 C · 官方单元测试（不需要 Java / Defects4J / API key）")
    ensure_repairagent()
    install_official_test_deps(py)
    tests = REPAIR_AGENT / "repair_agent" / "tests"
    log = EVIDENCE / "official_pytest.log"
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.run(
            [str(py), "-m", "pytest", str(tests), "-q", "-p", "no:cacheprovider"],
            cwd=str(REPAIR_AGENT / "repair_agent"),
            stdout=fh,
            stderr=subprocess.STDOUT,
        )
    tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-8:]
    print("\n".join(tail))
    if proc.returncode != 0:
        print("完整日志：", log)
        raise SystemExit("官方 pytest 失败")
    print("完整日志：", log)


def find_java11() -> Path | None:
    env = os.environ.get("JAVA_HOME")
    candidates = []
    if env:
        candidates.append(Path(env))
    candidates.extend(
        [
            Path("/usr/lib/jvm/java-11-openjdk-amd64"),
            Path("/usr/lib/jvm/java-1.11.0-openjdk-amd64"),
        ]
    )
    win_root = Path(r"C:\Program Files\Java")
    if win_root.exists():
        candidates.extend(sorted(win_root.glob("jdk-11*")))
        candidates.extend(sorted(win_root.glob("*11*")))
    for home in candidates:
        java = home / "bin" / ("java.exe" if os.name == "nt" else "java")
        if not java.exists():
            continue
        try:
            out = subprocess.check_output([str(java), "-version"], stderr=subprocess.STDOUT, text=True)
        except Exception:
            continue
        if 'version "11' in out or "version \"11" in out:
            return home
    return None


def d4j_env(java_home: Path) -> dict:
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    bin_dir = java_home / "bin"
    d4j_bin = D4J_HOME / "framework" / "bin"
    env["PATH"] = os.pathsep.join([str(bin_dir), str(d4j_bin), env.get("PATH", "")])
    env["TZ"] = "America/Los_Angeles"  # JFreeChart tests are timezone-sensitive
    return env


def defects4j_ready() -> bool:
    return (D4J_HOME / "framework" / "bin" / "defects4j").exists() and (
        D4J_HOME / "major"
    ).exists()


def stage_defects4j(java_home: Path) -> None:
    say("阶段 D · 真 Defects4J Chart-1（Java 11 + Perl，0 API 费用）")
    if not defects4j_ready():
        print("未检测到已 init 的 Defects4J。")
        print("Linux / WSL 先跑：bash scripts/setup_defects4j.sh")
        print("Windows 原生环境很难装 Defects4J，课上用阶段 A/B/C + evidence/chart1_defects4j.log。")
        return
    env = d4j_env(java_home)
    work = WORK / "chart_1b"
    if work.exists():
        shutil.rmtree(work)
    WORK.mkdir(parents=True, exist_ok=True)
    d4j = "defects4j"
    run([d4j, "checkout", "-p", "Chart", "-v", "1b", "-w", str(work)], env=env)
    run([d4j, "compile"], cwd=work, env=env)
    test_name = "org.jfree.chart.renderer.category.junit.AbstractCategoryItemRendererTests::test2947660"
    log = EVIDENCE / "chart1_defects4j.log"
    chunks: list[str] = []

    def capture(title: str, cmd: list[str]) -> str:
        print(title)
        proc = subprocess.run(cmd, cwd=str(work), env=env, text=True, capture_output=True)
        text = (proc.stdout or "") + (proc.stderr or "")
        chunks.append(title + "\n" + text)
        print(text[-1500:] if len(text) > 1500 else text)
        return text

    red = capture("## RED buggy Chart-1", [d4j, "test", "-t", test_name])
    fail_file = work / "failing_tests"
    if fail_file.exists():
        fail_txt = fail_file.read_text(encoding="utf-8", errors="replace")
        chunks.append("## failing_tests (buggy)\n" + fail_txt)
        print(fail_txt)
        red += fail_txt
    if "Failing tests: 1" not in red and "expected:<1> but was:<0>" not in red:
        print("警告：没有看到预期的红测试，继续打补丁。")

    src = work / "source/org/jfree/chart/renderer/category/AbstractCategoryItemRenderer.java"
    text = src.read_text(encoding="utf-8", errors="replace")
    needle = "public LegendItemCollection getLegendItems()"
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit("找不到 getLegendItems")
    old = "        if (dataset != null) {\n            return result;"
    new = "        if (dataset == null) {\n            return result;"
    chunk = text[idx:]
    if old not in chunk:
        raise SystemExit("找不到 Chart-1 出错条件")
    src.write_text(text[:idx] + chunk.replace(old, new, 1), encoding="utf-8")
    chunks.append("## PATCH RepairAgent/developer: if (dataset == null)\n")
    run([d4j, "compile"], cwd=work, env=env)
    green = capture("## GREEN after published Chart-1 patch", [d4j, "test", "-t", test_name])
    if "Failing tests: 0" not in green:
        raise SystemExit("打补丁后测试仍未变绿")
    log.write_text("\n".join(chunks), encoding="utf-8")
    print("记录：", log)
    print("课上口播：红 expected:<1> but was:<0> → 论文补丁 if (dataset == null) → 绿 Failing tests: 0")


def main() -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(description="RepairAgent course reproduction")
    parser.add_argument("--skip-official", action="store_true", help="skip sola-st/RepairAgent pytest")
    parser.add_argument("--with-d4j", action="store_true", help="run real Defects4J Chart-1")
    parser.add_argument("--only-mini", action="store_true", help="only Chart-1 mini tests")
    args = parser.parse_args()

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    say(
        "RepairAgent 课程复现",
        "论文: ICSE 2025  DOI 10.1109/ICSE55347.2025.00157\n"
        "官方仓库: https://github.com/sola-st/RepairAgent\n"
        "本目录可以整份拷到 E:\\report_reproduct",
    )
    py = ensure_venv()
    stage_mini(py)
    if args.only_mini:
        return 0
    ensure_repairagent()
    stage_apply_patch(py)
    if not args.skip_official:
        stage_official_pytest(py)
    if args.with_d4j:
        java_home = find_java11()
        if java_home is None:
            print("没有找到 Java 11。阶段 D 跳过。请设置 JAVA_HOME 后再跑 --with-d4j。")
        else:
            stage_defects4j(java_home)
    else:
        print()
        print("未加 --with-d4j：真实 Chart-1 红绿演示可看 evidence/chart1_defects4j.log")
        print("Linux / WSL 若已装 Java 11 和 Defects4J：")
        print("  python scripts/run_reproduction.py --with-d4j")
    say("完成", "课上最少跑阶段 A+B；有 Java 11 再跑阶段 D。不要花 835 个 bug 的钱。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
