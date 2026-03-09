---
name: signalradar
description: >-
  SignalRadar (信号雷达) — Monitors Polymarket prediction markets for probability
  changes and sends alerts when thresholds are crossed.
  监控 Polymarket 预测市场概率变化，超过阈值时推送通知。
  Use when user asks to "add a Polymarket market", "monitor Polymarket",
  "check prediction markets", "list my monitors", "remove a monitor",
  "track market probabilities", "run market check", "check schedule status",
  "change threshold", "change check frequency", or "health check".
  Also use when user says "我的监控", "看看有啥变化", "帮我加一下", "阈值",
  "自动监控", "定时检查", or sends any polymarket.com URL — even if they
  don't explicitly say "SignalRadar".
  Accepts any Polymarket event URL. Do NOT use for stock/crypto trading signals,
  sports betting, price prediction models, or general financial analysis.
  不适用于股票/加密货币交易信号、体育博彩、价格预测模型或一般金融分析。
allowed-tools: "Bash(python3:*)"
license: MIT
compatibility: Python 3.9+, network access to gamma-api.polymarket.com. No pip dependencies (stdlib only).
metadata:
  openclaw:
    emoji: "📡"
    requires:
      bins: ["python3"]
      env: []
      pip: []
    primaryEnv: ""
    envHelp:
      SIGNALRADAR_WORKSPACE_ROOT:
        required: false
        description: "Override workspace root directory. Auto-detected from script location if not set."
        howToGet: "Set to the absolute path of your workspace root, e.g. export SIGNALRADAR_WORKSPACE_ROOT=/path/to/workspace"
      SIGNALRADAR_CONFIG:
        required: false
        description: "Override config file path. Defaults to config/signalradar_config.json under workspace root."
        howToGet: "Set to absolute path of your config JSON, e.g. export SIGNALRADAR_CONFIG=/path/to/signalradar_config.json"
  author: vahnxu
  version: 0.5.6
---

# SignalRadar

> 信号雷达 — 监控 Polymarket 预测市场概率变化，超过阈值时推送通知。

## 用户意图→命令映射 / Intent Mapping

Agent 收到用户消息后，按此表选择命令。**无匹配时不执行任何命令，正常对话即可。**

| 用户意图（中文常见表达） | English intent | 命令 |
|------------------------|----------------|------|
| "看看我监控了啥" / "我的列表" / "在追踪哪些" | "list my monitors" / "what am I tracking" | `list` |
| "有啥变化吗" / "检查一下" / "跑一下" | "any changes?" / "run a check" | `run` |
| "帮我加一下 [URL]" / "监控这个链接" | "add this market" / "monitor this" | `add <url>` |
| "帮我加几个市场" / "想监控但没链接" | "add markets" (no URL) | `add`（无参数，引导式） |
| "删掉第 N 个" / "不监控这个了" | "remove #N" / "stop monitoring" | `remove <N>` |
| "阈值改成 X" / "灵敏度调高" | "change threshold" / "more sensitive" | `config threshold.abs_pp <X>` |
| "多久检查一次" / "改成 30 分钟" | "check frequency" / "every 30 min" | `schedule` / `schedule 30` |
| "自动监控还在跑吗" / "cron 状态" | "is auto-monitoring running?" | `schedule`（查看状态） |
| "现在设置是什么" / "阈值多少" | "what are current settings?" | `config`（必须查实际值） |
| "健康检查" / "能用吗" | "health check" / "is it working?" | `doctor --output json` |
| **"好的" / "没事" / "OK" / "知道了"** | **casual chat** | **不执行任何命令** |
| **"那个 GPT 概率多少了"** | **"what's the probability of X?"** | `show <number|keyword>` |

## 关键规则 / Critical Rules

**CR-01 多市场必须先报告数量**
如果事件包含多个市场（>3 个），CLI 会先强制打印市场数量、类型摘要和市场列表，再等待用户确认；`--yes` 不能跳过这一步。Agent 仍然必须先向用户解释数量和类型，再执行 `add`。
If event has multiple markets (>3), the CLI now force-prints count, type summary, and market list before waiting for confirmation; `--yes` cannot skip this. Agent must still explain the count and types before running `add`.

**CR-02 禁止自动添加市场**
必须由用户明确提供 Polymarket 链接或从预置列表选择，Agent 禁止自行添加。
User must explicitly provide a Polymarket URL or choose from presets. Do NOT auto-add.

**CR-03 Agent 禁止手动编辑数据文件**
Agent 禁止使用 Write/Edit 工具编辑 `cache/`、`config/watchlist.json` 或基线文件。必须通过 CLI 命令操作。正常运行会自动写入这些文件，这是预期行为。（注意：用户本人可以手动编辑 watchlist.json，系统兼容手动编辑。此规则仅限制 Agent。）
Agent must NOT edit `cache/`, `config/watchlist.json`, or baseline files using Write/Edit tools. Use CLI commands only. Normal runs automatically write these — that is expected behavior. (Note: the human user may hand-edit watchlist.json — the system tolerates it. This rule only restricts the Agent.)

**CR-04 人机交互禁用 --yes**
与真人用户交互时，Agent 禁止使用 `--yes` 参数。`--yes` 仅用于自动化/CI 流水线（冒烟测试、cron 定时任务、预发布门禁）。让脚本内置的确认流程处理用户交互。
When interacting with a human user, Agent must NOT use `--yes` flag. The `--yes` flag is for automated/CI pipelines only.

**CR-05 查设置必须读实际值**
当用户询问当前设置时，必须先运行 `signalradar.py config` 或读取实际配置文件。禁止假设或猜测配置值。如果某项缺失，报告默认值并说明"这是默认值"。
When user asks about current settings, ALWAYS run `signalradar.py config` first. Do NOT guess.

**CR-06 首次 add 后自动启用 cron**
首次引导或首次 `add` 成功后，SignalRadar 会自动启用 10 分钟 cron 监控。CLI 会明确告知用户。Agent 应确认此操作已完成，并说明如何用 `schedule` 命令更改频率。
After first successful `add`, cron auto-enables. Agent should confirm and explain how to change frequency.

**CR-07 用 CLI 管理设置和频率**
使用 `signalradar.py config [key] [value]` 查看或修改设置（阈值、推送通道等）。使用 `signalradar.py schedule [N|disable]` 管理监控频率。禁止手动编辑 JSON 配置文件。
Use CLI commands for settings and schedule. Do NOT hand-edit JSON config files.

**CR-08 空列表引导浏览**
当用户的监控列表为空且想添加市场但没有链接时，建议执行不带参数的 `signalradar.py add` 来浏览预置事件。
When watchlist is empty and user has no URL, suggest `signalradar.py add` (no args) to browse presets.

## 已知 AI 错误（禁止重犯） / Known AI Mistakes

以下错误在 GCP 实测中已实际发生。Agent 必须避免。
These mistakes actually occurred in production. Agent must avoid them.

**错误 1：直接添加 28 个市场，未先报告数量**
- 错误做法：用户发比特币链接，Agent 直接执行 `add` 添加 28 个市场
- 正确做法：先说"这个 Bitcoin 事件有 28 个子市场（14 个看涨 + 14 个看跌）。全部添加还是选择特定价位？"等用户回复后再执行
- WRONG: User sends Bitcoin URL → Agent runs `add` and adds 28 markets silently
- CORRECT: Report "This event has 28 sub-markets (14 upside + 14 downside). Add all or pick?" → wait for reply

**错误 2：用户说"好的"，Agent 触发 run 并裸发 NO_REPLY**
- 错误做法：用户说"好的" → Agent 执行 `signalradar.py run` → 回复 "NO_REPLY"
- 正确做法："好的"是日常确认，不是检查请求。Agent 正常回复即可，不执行任何命令
- WRONG: User says "好的" → Agent runs `signalradar.py run` → replies "NO_REPLY"
- CORRECT: "好的" is casual acknowledgment. Reply normally without running any command.

**错误 3：人机对话中使用 --yes 参数**
- 错误做法：`python3 scripts/signalradar.py add <url> --yes`（跳过确认）
- 正确做法：`python3 scripts/signalradar.py add <url>`（让脚本内置确认流程处理；>3 市场时 CLI 会强制预览）
- WRONG: `signalradar.py add <url> --yes` (skips confirmation in human chat)
- CORRECT: `signalradar.py add <url>` (let built-in confirmation handle it; CLI force-previews large batches)

**错误 4：用 Write/Edit 工具直接编辑 watchlist.json**
- 错误做法：用 Write 工具修改 `config/watchlist.json` 的内容
- 正确做法：使用 `signalradar.py add/remove/config` CLI 命令操作
- WRONG: Edit `config/watchlist.json` with Write/Edit tools
- CORRECT: Use `signalradar.py add`, `remove`, `config` CLI commands

**错误 5：凭记忆回答配置值，不查实际文件**
- 错误做法：用户问"阈值多少？" → Agent 回答"默认是 5pp"（没有执行 config 命令）
- 正确做法：先运行 `signalradar.py config threshold.abs_pp`，再用实际返回值回答
- WRONG: "The default threshold is 5pp" (without checking)
- CORRECT: Run `signalradar.py config threshold.abs_pp` first, then answer with the actual value

## Quick Start / 快速开始

```bash
# Install (OpenClaw users) / 安装（OpenClaw 用户）
clawhub install signalradar

# Or clone directly / 或直接克隆
git clone https://github.com/vahnxu/signalradar.git && cd signalradar

# 1. Health check / 健康检查
python3 scripts/signalradar.py doctor --output json

# 2. Add markets (guided setup or by URL) / 添加市场（引导式或通过链接）
python3 scripts/signalradar.py add
python3 scripts/signalradar.py add https://polymarket.com/event/your-market-here

# 3. Monitoring auto-starts after first add (every 10 min)
# 首次添加后自动启动监控（每 10 分钟）

# 4. Check schedule status / 查看调度状态
python3 scripts/signalradar.py schedule

# 5. Manual check (dry-run) / 手动检查（试运行）
python3 scripts/signalradar.py run --dry-run --output json
```

## Common Tasks / 常用操作

### Add a market / 添加市场

```bash
python3 scripts/signalradar.py add                              # Guided setup / 引导式添加
python3 scripts/signalradar.py add <polymarket-event-url> [--category <name>]
```

Flow: parse URL → query Polymarket API → show market question + current probability → user confirms → record baseline.

流程：解析链接 → 查询 Polymarket API → 显示市场问题 + 当前概率 → 用户确认 → 记录基线。

- If the event has multiple markets (e.g., different date brackets), the CLI shows all markets with their current probabilities before adding. For large events (>3 markets), it also shows a type summary and forces interactive confirmation even if `--yes` was passed.
  如果事件包含多个市场（如不同日期区间），CLI 会先展示所有市场及当前概率。大事件（>3 个市场）还会显示类型摘要，并且即使传了 `--yes` 也会强制要求交互确认。
- If some markets from the event are already monitored, only new ones are added.
  如果事件中部分市场已在监控，只添加新的。
- If the market is settled/expired, a warning is shown but the user can still add it.
  如果市场已结算/过期，会显示警告，但用户仍可添加。
- Category defaults to `default` if not specified. User is not prompted for category.
  分类默认为 `default`。不会提示用户选择分类。
- On first-ever add (empty watchlist), a brief explanation of the baseline concept is shown.
  首次添加（空监控列表）时，会简要解释基线概念。

### List monitors / 查看监控列表

```bash
python3 scripts/signalradar.py list [--category <name>] [--archived]
```

Shows all entries grouped by category with global sequential numbering. Each entry shows: number, question, current probability, baseline.

按分类分组显示所有条目，使用全局顺序编号。每条显示：编号、市场问题、当前概率、基线值。

`--archived` shows previously removed entries (preserved for export).
`--archived` 显示之前移除的条目（保留用于导出）。

### Show one monitored market / 查看单个监控市场

```bash
python3 scripts/signalradar.py show <number-or-keyword> [--output json]
```

Looks up one or more monitored markets by list number or keyword, fetches current probability, and returns a read-only snapshot without updating baselines.

按列表编号或关键词查找一个或多个已监控市场，获取当前概率，并返回只读快照，不更新基线。

### Remove a monitor / 移除监控

```bash
python3 scripts/signalradar.py remove <number>
```

Shows the entry name and asks for confirmation before removing. Removed entries are archived (moved to `archived` array in `config/watchlist.json`) with full history preserved.

显示条目名称并在移除前要求确认。移除的条目会被归档（移至 `config/watchlist.json` 的 `archived` 数组），完整历史保留。

### Run a check / 执行检查

```bash
python3 scripts/signalradar.py run [--dry-run] [--output json]
```

Checks all active entries against Polymarket API. If probability change exceeds threshold, sends alert via configured delivery channel.

检查所有活跃条目的 Polymarket 概率。如果变化超过阈值，通过配置的推送通道发送警报。

- Settled/expired entries are skipped during run, with a summary at the end: "N entries settled, consider removing."
  已结算/过期的条目在运行时跳过，结尾汇总提示："N 个条目已结算，建议移除。"
- When multiple markets from the same event trigger simultaneously, they are grouped in the alert.
  同一事件的多个市场同时触发时，在警报中合并展示。
- After a HIT is pushed, the baseline updates to the new probability value. The notification text includes "baseline updated to XX%."
  HIT 推送后，基线更新为新的概率值。通知文本包含"基线已更新至 XX%"。
- `--dry-run` fetches and evaluates but writes no state.
  `--dry-run` 只获取和评估，不写入任何状态。

### Manage schedule / 管理调度

```bash
python3 scripts/signalradar.py schedule                        # Show current status / 显示当前状态
python3 scripts/signalradar.py schedule 10                     # Set 10-minute interval / 设置 10 分钟间隔
python3 scripts/signalradar.py schedule 10 --driver openclaw   # Use openclaw cron / 使用 openclaw cron
python3 scripts/signalradar.py schedule disable                # Disable auto-monitoring / 禁用自动监控
```

### View or change config / 查看或修改配置

```bash
python3 scripts/signalradar.py config                          # Show all settings / 显示所有设置
python3 scripts/signalradar.py config check_interval_minutes   # Show one setting / 显示单项设置
python3 scripts/signalradar.py config threshold.abs_pp 8.0     # Change threshold / 修改阈值
```

### Health check / 健康检查

```bash
python3 scripts/signalradar.py doctor --output json
```

Returns `{"status": "HEALTHY"}` if Python version and network connectivity are OK.
如果 Python 版本和网络连接正常，返回 `{"status": "HEALTHY"}`。

## Understanding Results / 理解运行结果

| Status | Meaning / 含义 | Action / 操作 |
|--------|----------------|---------------|
| `BASELINE` | First observation for an entry / 条目的首次观测 | Baseline recorded; no alert sent / 记录基线，不发送警报 |
| `HIT` | Change exceeds threshold / 变化超过阈值 | Alert sent via delivery channel; baseline updated / 通过推送通道发送警报，基线更新 |
| `NO_REPLY` | No entries crossed threshold / 无条目超过阈值 | Nothing to report / 无需报告 |
| `SILENT` | Change below threshold / 变化低于阈值 | No alert sent / 不发送警报 |

### HIT output example / HIT 输出示例

```json
{
  "status": "HIT",
  "request_id": "9f98e47e-6e0e-4563-b7c8-87a3b19e97af",
  "hits": [
    {
      "entry_id": "polymarket:12345:gpt5-release-june:evt_67890",
      "slug": "gpt5-release-june",
      "question": "GPT-5 released by June 30, 2026?",
      "current": 0.41,
      "baseline": 0.32,
      "abs_pp": 9.0,
      "confidence": "high",
      "reason": "abs_pp 9.0 >= threshold 5.0"
    }
  ],
  "ts": "2026-03-02T08:00:00Z"
}
```

When presenting a HIT to the user / 向用户展示 HIT 时：
> **GPT-5 released by June 30, 2026?**: 32% → 41% (+9pp), threshold 5pp crossed. Baseline updated to 41%.
> **GPT-5 在 2026 年 6 月 30 日前发布？**：32% → 41%（+9pp），超过 5pp 阈值。基线已更新至 41%。

### Same-event grouped HIT / 同事件合并 HIT

When multiple markets from the same event trigger / 同一事件多个市场同时触发时：
> **Bitcoin price (March 31)** — 3 markets crossed threshold:
> - BTC > $100k: 45% → 58% (+13pp), baseline updated to 58%
> - BTC > $110k: 23% → 35% (+12pp), baseline updated to 35%
> - BTC > $120k:  8% → 19% (+11pp), baseline updated to 19%

### Empty watchlist / 空监控列表

If there are no entries, run returns / 如果没有条目，run 返回：
```json
{"status": "NO_REPLY", "message": "Watchlist is empty. Use 'signalradar.py add <url>' to add entries."}
```

## Configuration (Optional) / 配置（可选）

All settings have sensible defaults. Configuration file: `config/signalradar_config.json`.
所有设置都有合理的默认值。配置文件：`config/signalradar_config.json`。

| Setting / 设置 | Default / 默认值 | Description / 说明 |
|----------------|-------------------|---------------------|
| `threshold.abs_pp` | 5.0 | Global threshold in percentage points / 全局阈值（百分点） |
| `threshold.per_category_abs_pp` | `{}` | Per-category override / 按分类覆盖阈值，如 `{"AI": 4.0}` |
| `threshold.per_entry_abs_pp` | `{}` | Per-entry override, key = entry_id / 按条目覆盖阈值 |
| `delivery.primary.channel` | `openclaw` | `openclaw`, `file`, or `webhook` / 推送通道 |
| `delivery.primary.target` | `direct` | Path (file) or URL (webhook) / 文件路径或 webhook 地址 |
| `digest.frequency` | `weekly` | `off` / `daily` / `weekly` / `biweekly` / 定期报告频率 |
| `baseline.cleanup_after_expiry_days` | 90 | Days after market end date to clean up baseline / 市场到期后清理基线的天数 |
| `profile.timezone` | `Asia/Shanghai` | Display timezone / 显示时区 |
| `profile.language` | `""` | Empty = follow platform; set value to override / 空=跟随平台语言 |

### Delivery adapters / 推送适配器

- **`openclaw`** (default / 默认) — delivers to OpenClaw platform messaging layer. No setup needed when installed via ClawHub.
  通过 OpenClaw 平台消息层推送。通过 ClawHub 安装时无需额外配置。
- **`file`** — appends alerts to a local JSONL file. Set `target` to file path.
  将警报追加写入本地 JSONL 文件。将 `target` 设为文件路径。
- **`webhook`** — HTTP POST to external endpoint. Set `target` to webhook URL (works with Slack, Discord, etc.).
  HTTP POST 到外部端点。将 `target` 设为 webhook 地址（支持 Slack、Discord 等）。

For standalone use (not via OpenClaw), set delivery to `file` or `webhook`.
独立使用（非 OpenClaw 环境）时，请将推送通道设为 `file` 或 `webhook`。

For full configuration reference, see `references/config.md`.
完整配置参考请查看 `references/config.md`。

## Periodic Report / 定期报告

SignalRadar sends a periodic summary of all monitored entries (default: weekly). The report uses the same delivery channel as HIT alerts.

SignalRadar 会定期发送所有监控条目的摘要（默认：每周）。报告使用与 HIT 警报相同的推送通道。

Contents / 内容：
- All entries with current probability and change since last report / 所有条目的当前概率及自上次报告以来的变化
- Settled/expired entries marked with a recommendation to remove / 已结算/过期的条目标记为建议移除
- Next report date / 下次报告日期

Frequency is controlled by `digest.frequency` in config.
频率通过配置中的 `digest.frequency` 控制。

## Local State (What This Skill Writes) / 本地状态（此 Skill 写入的文件）

| Path / 路径 | Purpose / 用途 | When written / 写入时机 |
|--------------|----------------|-------------------------|
| `config/watchlist.json` | Monitored entries + archived entries / 监控条目 + 归档条目 | By `add` and `remove` commands / `add` 和 `remove` 命令执行时 |
| `cache/baselines/*.json` | Last-seen probability per market / 每个市场最后一次概率 | Every non-dry-run check / 每次非试运行的检查 |
| `cache/events/*.jsonl` | Audit log of all decisions / 所有决策的审计日志 | Every non-dry-run check / 每次非试运行的检查 |
| `cache/last_run.json` | Last run timestamp and status / 最后一次运行的时间戳和状态 | Every non-dry-run check / 每次非试运行的检查 |

- `--dry-run` fetches and evaluates without writing any state.
  `--dry-run` 只获取和评估，不写入任何状态。
- The human user (not Agent) may hand-edit `config/watchlist.json` (e.g., to change categories). The system tolerates manual edits. Agent must use CLI commands only — see CR-03.
  用户本人（非 Agent）可以手动编辑 `config/watchlist.json`（如更改分类）。系统兼容手动编辑。Agent 必须使用 CLI 命令——见 CR-03。
- No files outside the skill directory are modified.
  不会修改 skill 目录外的任何文件。

## Scheduling / 调度

SignalRadar automatically enables 10-minute cron monitoring after the first successful `add` (v0.5.3+). The default driver is system crontab (zero model cost, deterministic shell execution).

SignalRadar 在首次 `add` 成功后自动启用 10 分钟 cron 监控（v0.5.3+）。默认使用系统 crontab（零模型成本，确定性 shell 执行）。

Manage via the `schedule` command / 通过 `schedule` 命令管理：

```bash
signalradar.py schedule              # Show current status / 显示当前状态
signalradar.py schedule 30           # Change to 30-minute interval / 改为 30 分钟间隔
signalradar.py schedule disable      # Disable auto-monitoring completely / 完全禁用自动监控
signalradar.py schedule 10 --driver openclaw  # Use openclaw cron instead / 改用 openclaw cron
```

Minimum interval: 5 minutes (prevents overlapping runs).
最小间隔：5 分钟（防止运行重叠）。

### Threshold vs Frequency / 阈值 vs 频率

- **Threshold / 阈值** controls *sensitivity* — how much a probability must change before an alert fires. Managed per-category or per-entry via `signalradar.py config`.
  控制*灵敏度*——概率需要变化多少才会触发警报。通过 `signalradar.py config` 按分类或按条目管理。
- **Frequency / 频率** controls *how often* SignalRadar checks markets. Managed globally via `signalradar.py schedule`.
  控制 SignalRadar *多久检查一次*市场。通过 `signalradar.py schedule` 全局管理。

These are independent: a 5pp threshold with 10-minute frequency checks every 10 minutes and alerts on 5pp+ changes. A 3pp threshold with 30-minute frequency checks less often but is more sensitive when it does.

二者独立：5pp 阈值 + 10 分钟频率 = 每 10 分钟检查一次，5pp 以上变化时警报。3pp 阈值 + 30 分钟频率 = 检查频率低但灵敏度更高。

## Troubleshooting / 故障排除

| Error Code / 错误码 | Cause / 原因 | Fix / 修复 |
|---------------------|-------------|------------|
| `SR_TIMEOUT` | Polymarket API timeout / API 超时 | Check network; retry after 30s / 检查网络，30 秒后重试 |
| `SR_SOURCE_UNAVAILABLE` | Cannot reach gamma-api.polymarket.com / 无法连接 API | Verify DNS and internet access / 检查 DNS 和网络 |
| `SR_VALIDATION_ERROR` | Malformed entry data / 条目数据格式错误 | Run `python3 scripts/validate_schema.py` / 运行验证脚本 |
| `SR_ROUTE_FAILURE` | Delivery adapter failed / 推送适配器失败 | Check delivery config / 检查推送配置 |
| `SR_CONFIG_CONFLICT` | Contradictory config values / 配置值冲突 | Review config for duplicate keys / 检查配置是否有重复键 |
| `SR_PERMISSION_DENIED` | Insufficient permissions / 权限不足 | Check file permissions on config/ and cache/ / 检查文件权限 |

## AI Agent 指令（完整版） / AI Agent Instructions

### 默认行为 / Agent Default Behavior

Agent 在执行 SignalRadar 命令时，应遵循以下默认行为：

**命令输出处理**：Agent 应使用 `--output json` 获取结构化数据，然后自己翻译为用户友好的自然语言消息发送给用户。禁止将原始 JSON 或状态码直接发给用户。
Use `--output json` to get structured data, then translate it to user-friendly natural language. Never send raw JSON or status codes to the user.

**run vs run --dry-run 选择**：
- 用户明确要求检查（"检查一下"/"跑一下"）→ 使用 `run`（会更新基线）
- Agent 想展示当前状态但不确定用户是否想更新基线 → 使用 `run --dry-run`（只读不写）
- User explicitly asks to check → `run` (updates baselines)
- Agent wants to show status but unsure about updating → `run --dry-run` (read-only)

**网络错误处理**：收到 `SR_TIMEOUT` 或 `SR_SOURCE_UNAVAILABLE` 时，Agent 应告知用户"Polymarket API 暂时无法访问，请稍后再试"，不要自动重试。
On `SR_TIMEOUT` or `SR_SOURCE_UNAVAILABLE`, tell user "Polymarket API temporarily unavailable, please try later." Do not auto-retry.

**已结算市场处理**：添加已结算/过期的市场时，Agent 应主动告知用户"这个市场已结算，添加后不会产生新的警报。确定要添加吗？"让用户决定。
When adding settled/expired markets, proactively tell user: "This market is settled. Adding it won't produce new alerts. Still add?" Let user decide.

**单市场查询优先用 `show`**：如果用户问"那个 GPT 概率多少了"，优先运行 `show <关键词或编号>`。只有在用户明确要"顺便检查全部市场"时才用 `run`。
For single-market lookups, prefer `show <keyword-or-number>`. Use `run` only when the user wants a full check of all monitored markets.

### 结果展示 / Presenting Results

禁止将原始状态码（NO_REPLY、HIT、BASELINE、SILENT、ERROR）直接发送给用户。必须翻译为自然语言。
NEVER output raw status codes directly to user. Always translate to natural language.

- **HIT**：始终显示市场问题、概率变化（旧% → 新%）、变化幅度（pp），以及"基线已更新至 X%"。同一事件多个市场触发时合并展示。
  Always show market question, probability change (old% → new%), magnitude in pp, and "baseline updated to X%". Group by event when multiple markets trigger.
- **BASELINE**：告诉用户"首次运行——已为 N 个市场记录基线。稍后再次运行以检测变化。"不要将 BASELINE 呈现为问题。
  Tell user: "First run — baselines recorded for N markets. Run again later to detect changes."
- **NO_REPLY**：简要确认"已检查所有市场，没有超过阈值的变化。"
  Briefly confirm: "All markets checked. No changes exceeded the threshold."
- **空监控列表**：引导用户添加市场："当前没有监控市场。发一个 Polymarket 链接给我，或者说'帮我加几个'浏览预置事件。"
  Guide user: "No markets monitored. Send me a Polymarket URL, or say 'add some' to browse presets."

### 禁止操作 / Prohibited Actions

- 禁止自动发现或建议添加市场。等待用户提供链接。
  Do not auto-discover or suggest markets to add. Wait for user.
- 禁止在 `schedule` 命令流程外创建 cron 任务。
  Do not create cron jobs outside of `schedule` command.
- Agent 禁止手动编辑 `cache/`、`config/watchlist.json` 或基线文件（见 CR-03）。
  Agent must not manually edit data files (see CR-03).
- 不要假设有模式——没有模式概念。直接运行 `signalradar.py run`。
  No modes exist. Just run `signalradar.py run`.
- 禁止提及或尝试使用 Notion 集成（已在 v0.5.0 中移除）。
  Do not mention Notion integration (removed in v0.5.0).
- 用户日常对话（"好的"/"没事"/"OK"/"知道了"）不是命令，禁止触发任何 signalradar 操作。
  Casual chat ("好的"/"OK"/"没事") is NOT a command. Do NOT trigger any signalradar operation.

### 语言处理 / Language Handling

- 系统消息（提示、确认、状态文本）跟随平台语言或 `profile.language` 设置。
  System messages follow platform language or `profile.language` setting.
- 市场问题始终以 Polymarket API 返回的原始英文显示。不要翻译市场问题。
  Market questions always displayed in original English from API. Do not translate.

## References / 参考

- `references/config.md` — Full configuration reference / 完整配置参考
- `references/protocol.md` — Data contract (EntrySpec, SignalEvent, DeliveryEnvelope) / 数据契约
- `references/operations.md` — SLO targets, retry policy / SLO 目标、重试策略
