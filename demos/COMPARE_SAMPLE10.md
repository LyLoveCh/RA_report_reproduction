# Mini comparison（seed=42，先 10 题，再加抽 15 题）

同一 DeepSeek、同一题单、两条流水线。**不是**重跑论文 Table III（164 vs 162）。官方 RepairAgent 逻辑不改。

## 抽样

`demos/sample10.txt`：从 RepairAgent `experimental_setups/batches` 的 864 条（≈论文 835）里
`random.seed(42); random.sample(unique, 10)`。文件里按项目名排过序，集合不变。

`demos/sample_extra.txt`：同一 RNG **接着**对剩下 854 条 `sample(15)`，再按项目名排序。生成脚本：`python scripts/make_sample_extra.py`。

`demos/sample_all.txt` = 原 10 + extra 15（N=25）。跑 `finish` 时用这一份。

原 10 题：

| Bug | 论文 RA 164 | 论文 ChatRepair 162 |
|---|---|---|
| Closure 19 | 否 | 是 |
| Closure 38 | 是 | 是 |
| Closure 97 | 否 | 是 |
| JacksonDatabind 69 | 否 | 否 |
| JacksonDatabind 99 | 是 | 是 |
| Lang 23 | 否 | 否 |
| Math 4 | 否 | 否 |
| Math 83 | 否 | 否 |
| Mockito 9 | 否 | 否 |
| Mockito 24 | 否 | 是 |

Chart-1 不在题单里。原 10 题里只有 Closure 38、JacksonDatabind 99 在论文 RA 的 164 里。extra 15 题里论文 RA164 只有 Jsoup 41，ChatRepair162 只有 JacksonDatabind 1。

## 两条流水线

1. **CR-loop-DeepSeek**：`scripts/chatrepair_loop.py`  
   写死「生成补丁 → 跑测试 → 把报错贴回去 → 再生成」。不能搜仓库。最多 12 轮。位置来自 `data/buggy-lines`（perfect FL）。
2. **RA-DeepSeek**：官方 `repairagent.py run --bugs-file demos/sample_all.txt --model deepseek-chat --temperature 0 --max-cycles 40`

成功标准：触发测试先绿，再 `defects4j test` 全套 **Failing tests: 0**（plausible，不做人工 correct 判定）。

RA 轮数按论文定义：一个 cycle = 一次 LLM 查询，从 `model_responses_Project_Index` 里的 JSON 条数读取。CR 轮数是硬编码循环的 generate→test 次数。

## 先冒烟，再跑 10 题

10 题对比之前，先确认 key 能调模型，并且 **ChatRepair 循环** 和 **官方 RepairAgent** 都能在 Chart-1 上走通：

```bash
python scripts/probe_llm.py
bash scripts/smoke_both_modes.sh
```

`.env.example` 是占位符。真 key 在 `report_reproduct/.env`（gitignore）。

## 怎么跑 10 题（这台 Linux，冒烟通过之后）

```bash
source scripts/env.sh
bash scripts/run_compare_sample10.sh cr          # 先 10 题硬编码循环
bash scripts/run_compare_sample10.sh cr --force Closure 38
bash scripts/run_compare_sample10.sh ra          # 再官方 agent，顺序跑，不要并行
bash scripts/run_compare_sample10.sh summarize   # 写 RESULTS.md 并重画 compare.html
bash scripts/run_compare_sample10.sh finish      # 把剩下的 CR + RA 跑完（可续跑）
```

过夜 / 关掉 Cursor 窗口也不停（先 tmux，再脱离窗口的看门狗；**不要**并行第二份 Defects4J）：

```bash
bash scripts/self_supervise.sh start -- bash scripts/run_compare_sample10.sh finish
bash scripts/watchdog_supervise.sh start
bash scripts/watchdog_supervise.sh status
```

`self_supervise` 忽略 SIGHUP，父进程是 tmux。`watchdog_supervise` 用 `setsid nohup`，tmux 没了且 state 仍是 running 才重启；工人进程还在时不会再开一份。

不要并行：Defects4J 会抢 CPU/磁盘。Closure 单次编译经常要几分钟。

## 输出

- CR：`evidence/compare_sample10/chatrepair/`
- RA：`vendor/RepairAgent/repair_agent/experimental_setups/experiment_N/`（vendor 不进 git）
- 表：`evidence/compare_sample10/RESULTS.md`
- 可视化（课上打开）：`evidence/compare_sample10/compare.html`
- 幻灯片可插入：`chart1_smoke.svg`、`bars.svg`、`grid.svg`、`tools.svg`、`tools_rate.svg`
- 工具表（仿 RQ4，按 plausible vs 没过，不是 Figure 10）：`TOOLS.md` / `tools.json`

重画图：

```bash
python scripts/visualize_compare.py
```

## 本次结果

表：`evidence/compare_sample10/RESULTS.md`。课上打开：`evidence/compare_sample10/compare.html`。

原 10 题：CR-loop **7/10**，RA **7/10**。另加抽 15 题（N=25）连夜续跑，合计以表为准。**不是** Table III。

## 课上怎么说

这 10 题的数字**不能**写成「我们复现了 Table III」。只能说：同一 DeepSeek 下，agent 和硬编码循环在这个随机子集上各修了几题 plausible。
