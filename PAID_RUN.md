# 花小钱跑 RepairAgent（只跑 Chart-1）

钱买的是 **LLM 调用**。Java 11 + Defects4J（或 Docker）仍然要有，否则 key 也跑不起来。

**只跑 Chart-1。不要跑 835 题。** 论文均价约 $0.14/bug（GPT-3.5）；835 题会到一百美元量级。

## 预算（先做这个再充值）

| 项目 | 建议 |
|---|---|
| 模型 | **gpt-4o-mini**（官方 CLI 默认，便宜） |
| 题目 | **只 Chart 1**（论文 10 次查询就修对） |
| 轮数上限 | `--max-cycles 40`（默认；Chart-1 用不到这么多） |
| 账户充值 | **$5 够很久** |
| 必做 | OpenAI 控制台把 **月度上限设成 $2**，防止脚本失控 |
| 不要用 | gpt-4o、Claude Opus、一次写 `Chart 1, Math 5, Lang 22` |

Chart-1 按论文 27 万 token、再用现在 mini 的价，大约 **几分到两三毛美元**；第一次失败重跑也多半不到 **$1**。

## 第 0 步：环境（花钱之前）

Agent 每一轮都要 checkout Java 项目、编译、跑测试。缺这个，钱会浪费在报错上。

**优先（Windows 笔记本）：** 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)，用官方 `--docker`。

**其次：** WSL Ubuntu，先跑通免费的 Defects4J Chart-1：

```bash
bash scripts/setup_defects4j.sh
bash scripts/run_all.sh --with-d4j
```

看到红 `expected:<1> but was:<0>` 再绿 `Failing tests: 0` 之后，再花钱。

## 第 1 步：OpenAI key（不要发给任何人、不要贴到聊天里）

1. 打开 https://platform.openai.com/api-keys 注册并充值少量。
2. Create secret key，复制一次。
3. Usage limits 里把月限额打到 **$2**。
4. 当前终端：

```bash
export OPENAI_API_KEY='sk-...'     # Linux / WSL / macOS
# Windows PowerShell:
# $env:OPENAI_API_KEY = 'sk-...'
```

不要把 key 写进 Git。可放在 `vendor/RepairAgent/repair_agent/.env`（该目录已被 gitignore 的 vendor 罩住）。

## 第 2 步：只跑 Chart-1

在 `report_reproduct` 目录。

**有 Docker：**

```bash
bash scripts/run_paid_chart1.sh --docker
```

**已装好 Java 11 + Defects4J（Linux / WSL）：**

```bash
export JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
bash scripts/run_paid_chart1.sh
```

等价的官方命令：

```bash
cd vendor/RepairAgent/repair_agent
python3 repairagent.py run --bugs "Chart 1" --model gpt-4o-mini --temperature 0 --max-cycles 40
```

第一次会装 Python 依赖、拉 Defects4J 镜像或项目，**等 10–20 分钟很正常**（论文中位耗时约 15 分钟，时间几乎都在跑测试，不在问模型）。

## 第 3 步：跑完看什么（课上要展示的）

日志在：

`vendor/RepairAgent/repair_agent/experimental_setups/experiment_N/`

| 文件 | 课上指着说 |
|---|---|
| `logs/` | agent 每一轮 thoughts + 调了哪个工具 |
| `plausible_patches/` | 测试变绿的补丁 |
| `responses/` | 原始 LLM 回复 |

对照论文：Chart-1 应改第 1797 行成 `if (dataset == null)`。你们这次不一定 10 轮（模型换了、有随机性），但补丁应语义相同，触发测试应变绿。

## 失败了怎么办（先别加钱加题）

- `Defects4J is not available` → 先 `--docker` 或 `setup_defects4j.sh`
- `Incorrect API key` / 401 → key 或网络访问不到 `api.openai.com`
- 跑满 40 轮仍没修对 → 停。课上仍用 $0 的红绿日志 + 这篇失败日志当 Discussion
- **不要**立刻改成 gpt-4o 重跑

## 和论文的对应关系

这次才算用上 **III. Approach 的 agent 循环**：动态 prompt → 选工具 → 跑测试 → 再问模型。  
前面 $0 路径只验收了公布补丁；花钱路径让模型自己走 Chart-1。
