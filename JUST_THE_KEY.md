# 现在到哪一步 / 你只要填 key

## 已经完成（不用你再做）

- 论文方法：agent 外壳读到 III.C
- **$0 验收**：官方 pytest 429 通过；Defects4J Chart-1 红→公布补丁→绿
- **这台 Linux 环境已齐**：Java 11、Defects4J、官方 RepairAgent

## key 放哪

真 key 只写这两个 **gitignore** 文件之一（任意一个即可，课程目录优先）：

- `report_reproduct/.env`
- `vendor/RepairAgent/repair_agent/.env`

**不要**写进 `report_reproduct/.env.example`。那个文件进 Git，只能留占位符 `sk-把这里换成你的新key`。

从模板复制：

```text
report_reproduct/.env.example  →  report_reproduct/.env
```

只改 `OPENAI_API_KEY=`。不要把 key 发到聊天。

探测 key 是否真能调到模型（不会打印 key）：

```bash
python report_reproduct/scripts/probe_llm.py
```

两条流水线先在 **Chart-1** 上冒烟，确认都行再跑 10 题对比：

```bash
bash report_reproduct/scripts/smoke_both_modes.sh
```
