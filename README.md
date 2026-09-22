# RepairAgent 课程复现

面向 ICSE 2025 论文
**RepairAgent: An Autonomous, LLM-Based Agent for Program Repair**
（DOI `10.1109/ICSE55347.2025.00157`，仓库 [https://github.com/sola-st/RepairAgent](https://github.com/sola-st/RepairAgent）)

这是**课程报告用的本地可跑材料**，
## 课上演示什么（$0）

APR = 自动写补丁，用测试证明从红变绿。本目录演示 **Defects4J Chart-1**：


| 步骤     | 你看到什么                                                   |
| ------ | ------------------------------------------------------- |
| 出错代码   | `if (dataset != null) return empty;`                    |
| 触发测试   | `test2947660` → `expected:<1> but was:<0>`              |
| 论文公布补丁 | 改成 `if (dataset == null)`（与开发者补丁 identical，10 次 LLM 查询） |
| 修好     | `Failing tests: 0`                                      |


**不要**花 835 个 bug 的 API 钱，也**不要**跑 GitBug-Java（约 140GB）。

环境：

需要：Python 3.10+（勾选 Add to PATH）、Git。

打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_all.ps1
```

或双击 `scripts\run_all.bat`。

默认会跑三件事（都不需要 OpenAI key、都不需要 Java）：

1. **Chart-1 缩小版**（Python，同一条断言）
2. **官方** `apply_changes` 把论文补丁写进源码片段（RepairAgent 真正改文件的那一步）
3. **官方 400+ 条单元测试**（会自动浅克隆 `sola-st/RepairAgent`，第一次较慢）

只要缩小版：

```powershell
.\scripts\run_all.ps1 -OnlyMini
```



## 真 JFreeChart / Defects4J Chart-1（仍 $0，但要 Java 11）

原生 Windows 装 Defects4J 很痛。推荐 **WSL Ubuntu** 或任意 Linux：

```bash
sudo apt-get install -y openjdk-11-jdk python3 python3-venv git perl unzip cpanminus
sudo cpanm String::Interpolate
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
bash scripts/setup_defects4j.sh
bash scripts/run_all.sh --with-d4j
```

本云环境已经跑通并留下日志：`evidence/chart1_defects4j.log`。

## 目录

```
report_reproduct/
  scripts/run_reproduction.py   # 复现入口
  scripts/chatrepair_loop.py    # 10 题对比：硬编码循环
  scripts/run_compare_sample10.sh
  scripts/run_all.ps1           # Windows
  scripts/run_all.sh            # Linux / WSL
  scripts/setup_defects4j.sh    # 只在 Linux 初始化 Defects4J
  demos/chart1_mini/            # Chart-1 断言缩小版
  demos/apply_patch/            # 供 apply_changes 使用的出错片段
  demos/traces/                 # 论文仓库里 Chart_1 的公开数字
  evidence/                     # 已跑通的日志，答辩可直接打开
  PAID_RUN.md                   # 花小钱只跑 Chart-1
  TALK_SCRIPT.md                # 3 分钟口播稿
  vendor/                       # git 忽略：自动克隆的 RepairAgent / Defects4J
```



## 和论文数字对齐（报告可念）

- Defects4J 全集 835；RepairAgent **correct 164**（plausible 186），其中 39 个基线没修过
- Chart-1：10 次查询、1 个建议补丁、判定正确
- 平均约 27 万 token / bug，论文当时 GPT-3.5 约 **14 美分**；本复现路径 **0 美分**

长任务请用自我监督，避免 Cursor 窗口崩了还要点 Reopen 重跑：

```bash
bash scripts/self_supervise.sh start -- bash scripts/run_full_chart1.sh
bash scripts/self_supervise.sh status
# overnight compare: tmux + detached watchdog (do not start a second Defects4J)
bash scripts/self_supervise.sh start -- bash scripts/run_compare_sample10.sh finish
bash scripts/watchdog_supervise.sh start
```

花小钱让 agent 自己修 Chart-1：见 **[PAID_RUN.md](PAID_RUN.md)**。只跑这一题。不要跑 835 题。

## 10 题对比（同一 DeepSeek，不是 Table III）

先确认 key 能调模型，并且两种流水线都能在 **Chart-1** 上走通，再跑 10 题：

```bash
python scripts/probe_llm.py
bash scripts/smoke_both_modes.sh
```

真 key 放 `report_reproduct/.env`（gitignore）。不要写进 `.env.example`。

`demos/sample10.txt`：seed=42 先抽 10 题；`sample_extra.txt` 是同一 RNG 再抽 15 题（合计 `sample_all.txt`，N=25）。两条流水线：

- 硬编码 ChatRepair 风格循环：`bash scripts/run_compare_sample10.sh cr`
- 官方 RepairAgent：`bash scripts/run_compare_sample10.sh ra`（不改仓库逻辑）

协议见 [demos/COMPARE_SAMPLE10.md](demos/COMPARE_SAMPLE10.md)。结果表在 `evidence/compare_sample10/RESULTS.md`。课上打开 `evidence/compare_sample10/compare.html`（含工具平均次数/使用率，按 plausible vs 没过）。结论只覆盖表里的题，**不是** Table III，也**不是** Figure 10。

## 本机已验证（云端 Linux）

- 官方 pytest：**429 passed**
- Defects4J Chart-1b 触发测试：**红 expected:<1> but was:<0>**
- 打上 `if (dataset == null)` 后：**Failing tests: 0**

