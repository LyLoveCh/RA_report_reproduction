# 论文结果和复现的类比

同一 DeepSeek、同一 25 题上，RepairAgent 测绿 **15/25**，写死的循环测绿 **11/25**。两边都绿的有 10 题，只 agent 绿的有 5 题，只循环绿的有 1 题。这个形状和论文一样：总体接近，两个集合互相交叉。数字本身对不上论文的 Table III。

论文是 GPT-3.5、Defects4J 835 题、correct。这次是 DeepSeek `deepseek-chat`、temperature 0、seed 42 抽的 25 题、plausible。对照循环是本仓库写的 12 轮反馈环，不是 Xia 的 ChatRepair。

## 论文那边

第 V 节 RQ1、Table III：GPT-3.5-0125，Defects4J **835** 题。RepairAgent **plausible 186**、**correct 164**（116 个和开发者补丁字面相同，48 个人工判成语义相同）。ChatRepair 的 correct 是 **162**。摘要里的那句是：164 里有 **39** 题是先前技术没修好的。Figure 6 画的是两个修复集合的交集，谁也不包含谁。

Table IV 把这个差距拆开了：单行 bug 上 ChatRepair 更多（133 对 115），多行上 RepairAgent 更多（46 对 29）。第 VI.A 节的解释是，agent 会自己去读、去搜，所以多修了一批；同时它也会把简单 bug 修得很重。

## 这次对得上的形状

| | 论文 | 这次 |
|---|---|---|
| 模型 | GPT-3.5-0125 | DeepSeek `deepseek-chat`，temperature 0 |
| 题 | 835 | seed 42 抽的 25，外加 Chart-1 冒烟 |
| 对照 | 作者给的 ChatRepair 补丁 | 本仓库的 12 轮循环，每一轮都要交补丁 |
| 成功 | correct | 只记 plausible：触发测试绿，再 `defects4j test` 全套 0 failing |
| 结果 | correct 164 对 162 | plausible 15 对 11 |

先抽的 10 题两边都是 **7/10**。后抽的 15 题才拉开：**agent 8/15，循环 4/15**。所以 15 对 11 是这一刀切出来的。这和 Figure 6 的意思一致：总体接近，领先取决于看哪一批。

只 agent 绿的五题，循环都把 12 轮用完了：

| 题 | 循环 | RepairAgent | cycle | agent 主要在做什么 |
|---|---|---|---:|---|
| Lang 23 | 12 轮用尽 | 绿 | 21 | `read_range` ×10，`write_fix` ×7 |
| Collections 21 | 12 轮用尽 | 绿 | 7 | 读 4 次，写 1 次，然后 `goal_accomplished` |
| Jsoup 48 | 12 轮用尽 | 绿 | 7 | `write_fix` ×3，很快结束 |
| Jsoup 81 | 12 轮用尽 | 绿 | 17 | 读、`extract_method`、`search_code_base` |
| Math 8 | 12 轮用尽 | 绿 | 40 | `read_range` ×33，测绿后没喊下班 |
| Mockito 24 | 2 轮就绿 | 没绿 | 40 | `read_range` ×14，预算用尽 |

Mockito 24 在论文里属于 ChatRepair 的 162，不属于 RepairAgent 的 164。这次方向一样：循环绿了，agent 没绿。

论文 correct 集合里、又落在这 25 题中的只有 Closure 38、JacksonDatabind 99、Jsoup 41。这三题 agent 都测绿了。测绿只说明测试过了，还不是论文的 correct。

## 呼应原文的哪几段

**第 I 节那句限制，和第 II 节对 agent 的定义。** 循环把 buggy 行放进 prompt，失败了再贴回去，每一轮都必须交一份补丁。Collections 21 和 Jsoup 81 上，agent 先读、先搜，再决定写。这就是论文说的：写死的反馈环不能自己去搜集 bug 和代码里的修复材料；agent 自己安排下一步，并且去调用工具。Table IV 是这件事在 835 题上的总账。这 25 题没有标单行还是多行，所以只能说到机制。

**Figure 2 和 RQ2。** 进 Done 的唯一箭头是 `goal_accomplished`。15 题绿里有 12 题喊了（80%），10 题没绿的是 0。Cli 18、Jsoup 41、Math 8 测试已经绿了，仍跑到 40 cycle。Cli 18 的 `write_fix` 写了 36 次。论文 RQ2 写的就是这件事：修好了时间也不会短，因为过程要等到模型自己收工，或者预算用尽。

**RQ4 和 Figure 10，只对得上分工。** 25 题一共 475 次工具调用，平均约 **19** 次。论文平均约 **35** 次，一次调用就是一个 cycle。没过的题更长（25.2 对 14.9），多出来的是 `read_range`（16.1 对 7.3）。`run_tests` 是 0，因为测试焊在 `write_fix` 里，和 RQ4 一样。`write_fix` 的平均数两边几乎一样（4.6 对 4.5），是 Cli 18 那 36 次抬上去的。论文 Figure 10 是 correct 上约 6 次、unfixed 上约 17 次；unfixed 里包含测绿但不算 correct 的补丁。我们的图按 plausible / 没过拆，所以那两根柱不能叫 Figure 10。

**VI.A。** 能自己去读 bug，就会多修一批循环够不着的题；同时 agent 也会在已经测绿之后继续写。Cli 18 就是后一种。

**Chart-1** 不在 25 题里。两边都写成论文 Figure 5 的 `if (dataset == null)`。循环 1 轮，agent 4 个 cycle。论文公开日志是 10 次查询。同一种补丁，另一次运行。

## 可以停在这句

同一模型、同一 25 题，自己选工具的 agent 比「贴代码、拿补丁、再贴失败」多测绿 4 题，其中 5 题只有它绿。多出来的那些，是它先读、先搜，再决定写不写。测试变绿不会让它停，这和论文的状态机一致。

这句话对应摘要、第 I 节、第 II 节、RQ1 的交叉集合、RQ2 的停止规则、RQ4 的工具分工，以及 VI.A。它对应不了 Table III 的 164/835，也对应不了 Figure 10 的柱高。correct 的人工判定、RQ3 的消融、GitBug-Java，这次都没有做。

数字来自 [`RESULTS.md`](RESULTS.md) 和 [`TOOLS.md`](TOOLS.md)。
