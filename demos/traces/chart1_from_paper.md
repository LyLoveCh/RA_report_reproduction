# Chart-1：论文仓库里的公开结果（不花钱即可展示）

来源：https://github.com/sola-st/RepairAgent

## `data/summary_example.txt`

RepairAgent 在 Chart_1 上：

- Correctly Fixed: **Yes**
- Suggested Fixes: **1**
- Number of Queries: **10**

写出的补丁（与开发者补丁 identical）：

```
Lines: ['1797'] from file
org/jfree/chart/renderer/category/AbstractCategoryItemRenderer.java
{'1797': 'if (dataset == null) {'}
```

## `data/fixes_implementation`（# Chart 1）

```
modified_line: if (dataset == null) {
Why: Identical.
```

## Defects4J 官方开发者补丁方向

固定版（正确）是 `if (dataset == null)`；
出错版是 `if (dataset != null)`，导致 `test2947660`：`expected:<1> but was:<0>`。

## 本目录现场对应

- `demos/chart1_mini/test_chart1.py`：同一条断言的 Python 缩小版（任意机器可跑）
- `scripts/run_reproduction.py --with-d4j`：真 JFreeChart + Defects4J（需 Java 11）
