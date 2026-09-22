# 课上 3 分钟口播（对着本目录现场跑）

开场 20 秒：这篇不是聊天修 bug。APR = 机器改源码，测试从红变绿。RepairAgent 把 LLM 当成 agent，自己选工具；我们今天不烧 835 题的钱，只复现 Chart-1 这一道。

## 现场顺序

1. 打开 `demos/traces/chart1_from_paper.md`  
   念：官方日志里 Chart_1 修对了，10 次查询，补丁是第 1797 行改成 `if (dataset == null)`，和开发者 identical。

2. 跑缩小版（任何电脑都能绿）：

   ```text
   powershell -ExecutionPolicy Bypass -File .\scripts\run_all.ps1 -OnlyMini
   ```

   指着输出说：同一条断言 `expected 1 but was 0`，出错代码在 dataset 非空时直接返回空图例。

3. 再跑（或已经跑过）`apply_changes` 阶段：  
   这是 agent 的 `write_fix`，不经过 LLM，把论文那一行写进文件。

4. 若老师追问「这不是真 JFreeChart」：打开 `evidence/chart1_defects4j.log`  
   红：`Failing tests: 1` + `expected:<1> but was:<0>`  
   绿：`Failing tests: 0`  
   云端 Linux + Java 11 + 官方 Defects4J 已跑通。有 WSL 可再现场 `run_all.sh --with-d4j`。

5. 若老师追问「代码对不对」：打开官方 pytest 日志 `evidence/official_pytest.log`，**429 passed**，无 API key。

6. 若老师要对比：打开 `evidence/compare_sample10/compare.html`（同一 DeepSeek，循环 vs agent）。**不要**把这页数字说成论文 Table III。往下翻工具表：仿 RQ4 拆 plausible vs 没过，**不要**说成 Figure 10（论文那张是 correct vs unfixed）。

## 可能被问

- **SOTA**：当时该基准上最好的一档。ChatRepair 162，这篇 correct 164。
- **为什么不跑完整 agent**：要 OpenAI/Anthropic key，论文均价 14 美分/bug；课设允许 $0 路径。
- **和 ChatRepair 差别**：ChatRepair 写死「吐补丁→跑测试→贴报错」；RepairAgent 每轮自己选工具（读、搜、改、测）。
- **repair ingredients**：Chart-1 这题材料就是那一行条件；更难的题（Closure-14）要去别的文件抄 `Branch.ON_EX`。

收尾 10 秒：我们复现的是「测试验收补丁」这条 APR 主链，以及官方仓库公布的 Chart-1 补丁；不是复现 164/835 的训练账单。
