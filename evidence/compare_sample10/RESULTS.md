# 对比结果（DeepSeek，N=25）

不是论文 Table III（164 vs 162）。同一模型、同一题单、两种流水线。官方 RepairAgent 逻辑未改。
plausible = 触发测试绿，且 `defects4j test` 全套 0 failing。
CR 轮数 = 硬编码循环次数。RA 轮数 = 论文里的 cycle（一次 LLM 查询，来自 `model_responses_*`）。

合计 CR-loop plausible: **11/25**. RA plausible: **15/25**。

## 原 sample10（seed=42，N=10）

CR **7/10**，RA **7/10**。

| Bug | 论文 RA164 | 论文 ChatRepair162 | CR-loop-DeepSeek | RA-DeepSeek | CR 轮数 | RA 轮数 | CR 秒 |
|---|---|---|---|---|---|---|---|
| Closure 19 | no | yes | yes | yes (experiment_5) | 1 | 26 | 62.4 |
| Closure 38 | yes | yes | yes | yes (experiment_6) | 1 | 4 | 60.4 |
| Closure 97 | no | yes | yes | yes (experiment_7) | 1 | 4 | 32.6 |
| JacksonDatabind 69 | no | no | no | no (experiment_8) | 12 | 40 | 53.8 |
| JacksonDatabind 99 | yes | yes | yes | yes (experiment_9) | 1 | 4 | 46.2 |
| Lang 23 | no | no | no | yes (experiment_10) | 12 | 21 | 35.0 |
| Math 4 | no | no | yes | yes (experiment_11) | 1 | 5 | 54.3 |
| Math 83 | no | no | yes | yes (experiment_12) | 2 | 12 | 25.8 |
| Mockito 9 | no | no | no | no (experiment_13) | 12 | 40 | 1178.4 |
| Mockito 24 | no | yes | yes | no (experiment_14) | 2 | 40 | 91.7 |

## 加抽 extra（同一 RNG 继续 sample，N=15）

CR **4/15**，RA **8/15**。

| Bug | 论文 RA164 | 论文 ChatRepair162 | CR-loop-DeepSeek | RA-DeepSeek | CR 轮数 | RA 轮数 | CR 秒 |
|---|---|---|---|---|---|---|---|
| Cli 18 | no | no | yes | yes (experiment_15) | 2 | 40 | 12.9 |
| Closure 107 | no | no | no | no (experiment_16) | 12 | 40 | 76.7 |
| Closure 121 | no | no | no | no (experiment_17) | 12 | 40 | 492.3 |
| Collections 21 | no | no | no | yes (experiment_30) | 12 | 7 | 39.1 |
| JacksonDatabind 1 | no | yes | yes | yes (experiment_19) | 2 | 4 | 30.2 |
| JacksonDatabind 2 | no | no | no | no (experiment_20) | 12 | 40 | 283.9 |
| JacksonDatabind 5 | no | no | no | no (experiment_21) | 12 | 40 | 46.7 |
| JacksonDatabind 72 | no | no | yes | yes (experiment_22) | 1 | 10 | 42.8 |
| JacksonDatabind 94 | no | no | no | no (experiment_23) | 12 | 40 | 36.8 |
| Jsoup 5 | no | no | no | no (experiment_24) | 12 | 7 | 30.8 |
| Jsoup 41 | yes | no | yes | yes (experiment_25) | 1 | 40 | 10.1 |
| Jsoup 48 | no | no | no | yes (experiment_26) | 12 | 7 | 40.9 |
| Jsoup 81 | no | no | no | yes (experiment_27) | 12 | 17 | 28.9 |
| Lang 35 | no | no | no | no (experiment_28) | 12 | 40 | 44.0 |
| Math 8 | no | no | no | yes (experiment_29) | 12 | 40 | 61.8 |

## 备注

- **Collections 21**：第一次缺 Collections-21.buggy.lines 早停；补 FL 后 experiment_30 于 7 轮测绿，goals_accomplished=true。
- **JacksonDatabind 69**：hit last-cycle TTY prompt; exited without a plausible patch
- **Jsoup 5**：第一次 write_fix 变体把 defects4j test 跑进死循环（约 5.5h）记 no；experiment_31 重测又在 cycle 2 卡死（java 100% CPU 约 100 分钟），停掉后仍记 no。
- RA 轮数取 max(解析到的 JSON 条数, saved_context.cycle_count)。部分 model_responses_* 因 thoughts 未转义换行会提前解析失败。
- Collections 21：第一次缺 Collections-21.buggy.lines，write_fix 早停；补上 perfect FL 后 experiment_30 在 7 轮测绿并调用 goals_accomplished。
- Jsoup 5：第一次 write_fix 变体死循环后跳过记 no；experiment_31 重测又在 cycle 2 把 defects4j test 跑到 100% CPU（约 100 分钟），按同一规则停掉，仍记 no。

## Chart-1 冒烟（不在这张题单里）

| 流水线 | plausible | 轮数 | 备注 |
|---|---|---|---|
| CR-loop-DeepSeek | yes | 1 | if (dataset == null) { |
| RA-DeepSeek | yes | 4 | experiment_4 if (dataset == null) { |

结论只覆盖已列出的题。ChatRepair 侧是本仓库的硬编码循环，不是 Xia 原实现 + GPT-3.5。

## RepairAgent 工具使用（我们的 N=25，DeepSeek）

仿论文 RQ4 / Figure 10 的**拆法**，不是复现那张图。
论文按 **correct vs unfixed**（unfixed = 只有 plausible 或完全没绿）。
我们没做人工 correct，所以按 **plausible vs 没过**。

计入 **25** 题（plausible 15，没过 10）。

平均每次调用数：plausible **14.9**，没过 **25.2**。
`write_fix` 平均次数：plausible **4.6**，没过 **4.5**。
喊过 `goal_accomplished` 的比例：plausible **80%**，没过 **0%**。

## 平均次数 / 题（论文 Figure 10 同款）

| 工具 | plausible 平均/题 | 没过 平均/题 | 全体次数 |
|---|---:|---:|---:|
| `write_fix` | 4.60 | 4.50 | 114 |
| `read_range` | 7.33 | 16.10 | 271 |
| `search_code_base` | 0.33 | 1.30 | 18 |
| `extract_method` | 0.40 | 1.60 | 22 |
| `express_hypothesis` | 1.00 | 0.80 | 23 |
| `extract_tests` | 0.20 | 0.60 | 9 |
| `get_classes_and_methods` | 0.07 | 0.30 | 4 |
| `generate_method_body` | 0.07 | 0.00 | 1 |
| `collect_more_information` | 0.07 | 0.00 | 1 |
| `goal_accomplished` | 0.80 | 0.00 | 12 |

## 使用率（至少用过一次的题占比）

| 工具 | plausible 使用率 | 没过 使用率 |
|---|---:|---:|
| `write_fix` | 100% | 80% |
| `read_range` | 100% | 100% |
| `search_code_base` | 20% | 60% |
| `extract_method` | 13% | 40% |
| `express_hypothesis` | 100% | 80% |
| `extract_tests` | 20% | 60% |
| `get_classes_and_methods` | 7% | 30% |
| `generate_method_body` | 7% | 0% |
| `collect_more_information` | 7% | 0% |
| `goal_accomplished` | 80% | 0% |

课上先指总次数（没过的题更长：读代码耗在 `read_range`），再指 `goal_accomplished`（只有自己喊下班才出现）。
`write_fix` 两边平均数差不多，是因为 Cli 18 测绿后仍写到 36 次，把 plausible 组抬上去了；论文 Figure 10 会把它算进 unfixed。
`run_tests` 为 0，是因为测试焊在 `write_fix` 里，和论文 RQ4 一致。
论文的 unfixed 还包括「测绿但补丁不正确」；Cli 18 / Math 8 / Jsoup 41 测绿后仍写到预算附近，图里算 plausible，课上不要说成 Figure 10 的 fixed。

## 每题调用次数（答问用）

| Bug | plausible | 调用次数 | 最多的三个工具 |
|---|---|---:|---|
| Closure 19 | yes | 26 | read_range×20, write_fix×4, express_hypothesis×1 |
| Closure 38 | yes | 4 | read_range×1, express_hypothesis×1, write_fix×1 |
| Closure 97 | yes | 4 | read_range×1, express_hypothesis×1, write_fix×1 |
| JacksonDatabind 69 | no | 39 | read_range×35, extract_tests×1, express_hypothesis×1 |
| JacksonDatabind 99 | yes | 4 | read_range×1, express_hypothesis×1, write_fix×1 |
| Lang 23 | yes | 20 | read_range×10, write_fix×7, extract_tests×1 |
| Math 4 | yes | 5 | read_range×2, express_hypothesis×1, write_fix×1 |
| Math 83 | yes | 12 | read_range×4, write_fix×4, search_code_base×2 |
| Mockito 9 | no | 40 | write_fix×20, read_range×11, extract_method×4 |
| Mockito 24 | no | 16 | read_range×14, express_hypothesis×1, write_fix×1 |
| Cli 18 | yes | 40 | write_fix×36, read_range×3, express_hypothesis×1 |
| Closure 107 | no | 40 | read_range×39, extract_tests×1 |
| Closure 121 | no | 22 | read_range×9, extract_method×6, search_code_base×3 |
| Collections 21 | yes | 7 | read_range×4, express_hypothesis×1, write_fix×1 |
| JacksonDatabind 1 | yes | 4 | read_range×1, express_hypothesis×1, write_fix×1 |
| JacksonDatabind 2 | no | 20 | read_range×14, write_fix×3, extract_tests×1 |
| JacksonDatabind 5 | no | 9 | read_range×9 |
| JacksonDatabind 72 | yes | 10 | read_range×6, write_fix×2, express_hypothesis×1 |
| JacksonDatabind 94 | no | 23 | read_range×10, search_code_base×5, extract_method×5 |
| Jsoup 5 | no | 7 | read_range×2, extract_tests×1, express_hypothesis×1 |
| Jsoup 41 | yes | 24 | read_range×16, extract_method×3, express_hypothesis×1 |
| Jsoup 48 | yes | 7 | write_fix×3, read_range×2, express_hypothesis×1 |
| Jsoup 81 | yes | 17 | read_range×6, extract_method×3, search_code_base×2 |
| Lang 35 | no | 36 | read_range×18, write_fix×16, extract_tests×1 |
| Math 8 | yes | 39 | read_range×33, write_fix×4, extract_tests×1 |

