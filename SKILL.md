---
name: signalradar
description: >-
  SignalRadar (信号雷达) — Monitors Polymarket prediction markets for probability
  changes and sends alerts when thresholds are crossed.
  监控 Polymarket 预测市场概率变化，超过阈值时推送通知。
  Use when user asks to "add a Polymarket market", "monitor Polymarket",
  "check prediction markets", "list my monitors", "remove a monitor",
  "track market probabilities", or "run market check".
  Accepts any Polymarket event URL. Do NOT use for stock market analysis,
  sports betting, or real-time trading signals.
  接受任意 Polymarket 事件链接。不适用于股市分析、体育博彩或实时交易信号。
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

## Critical Rules / 关键规则

- **Do NOT auto-add monitoring entries.** User must explicitly provide a Polymarket URL.
  **禁止自动添加监控条目。** 必须由用户明确提供 Polymarket 链接。
- **Do NOT manually edit** `cache/`, `config/watchlist.json`, or baseline files. Normal runs automatically write these — that is expected behavior.
  **禁止手动编辑** `cache/`、`config/watchlist.json` 或基线文件。正常运行会自动写入这些文件，这是预期行为。
- After first successful onboarding or first `add`, SignalRadar automatically enables 10-minute cron monitoring. This is NOT silent — the CLI explicitly tells the user. Agent should confirm this happened and explain how to change frequency.
  首次引导或首次 `add` 成功后，SignalRadar 会自动启用 10 分钟 cron 监控。这不是静默操作——CLI 会明确告知用户。Agent 应确认此操作已完成，并说明如何更改频率。
- When interacting with a human user, Agent must NOT use `--yes` flag. The `--yes` flag is for automated/CI pipelines only (smoke tests, prepublish gates). Let the script's built-in confirmation handle user interaction.
  与真人用户交互时，Agent 禁止使用 `--yes` 参数。`--yes` 仅用于自动化/CI 流水线（冒烟测试、预发布门禁）。让脚本内置的确认流程处理用户交互。
- When user asks about current settings, ALWAYS run `signalradar.py config` or read the actual config file first. Do NOT assume or guess config values. If a key is missing, report the DEFAULT value and state it is the default.
  当用户询问当前设置时，必须先运行 `signalradar.py config` 或读取实际配置文件。禁止假设或猜测配置值。如果某项缺失，报告默认值并说明是默认值。
- If event has multiple markets (>3), Agent MUST first report the count and explain what they are BEFORE running `add`. Example: "This Bitcoin event has 28 sub-markets (14 upside + 14 downside). Add all 28 or pick specific levels?" Wait for user choice.
  如果事件包含多个市场（>3 个），Agent 必须先报告数量并解释类型，然后再执行 `add`。示例："这个 Bitcoin 事件有 28 个子市场（14 个看涨 + 14 个看跌）。全部添加还是选择特定价位？"等待用户选择。
- Use `signalradar.py config [key] [value]` to view or change settings. Use `signalradar.py schedule [N|disable]` for monitoring frequency. Do NOT hand-edit JSON config files.
  使用 `signalradar.py config [key] [value]` 查看或修改设置。使用 `signalradar.py schedule [N|disable]` 管理监控频率。禁止手动编辑 JSON 配置文件。
- When user's watchlist is empty and they want to add markets but don't have a URL, suggest `signalradar.py add` without arguments to browse preset events.
  当用户的监控列表为空且想添加市场但没有链接时，建议执行不带参数的 `signalradar.py add` 来浏览预置事件。

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

- If the event has multiple markets (e.g., different date brackets), all are added by default. User can refine afterward.
  如果事件包含多个市场（如不同日期区间），默认全部添加。用户可以之后调整。
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
- Users may hand-edit `config/watchlist.json` (e.g., to change categories). The system tolerates manual edits.
  用户可以手动编辑 `config/watchlist.json`（如更改分类）。系统兼容手动编辑。
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

## AI Agent Instructions (Complete) / AI Agent 指令（完整版）

### Presenting results / 结果展示

- **HIT**: Always show market question, probability change (old% → new%), magnitude in pp, and "baseline updated to X%". Group by event when multiple markets from the same event trigger.
  **HIT**：始终显示市场问题、概率变化（旧% → 新%）、变化幅度（pp），以及"基线已更新至 X%"。同一事件多个市场触发时合并展示。
- **BASELINE**: Tell the user "First run — baselines recorded for N markets. Run again later to detect changes." Do not present BASELINE as a problem.
  **BASELINE**：告诉用户"首次运行——已为 N 个市场记录基线。稍后再次运行以检测变化。"不要将 BASELINE 呈现为问题。
- **NO_REPLY**: Briefly confirm "No markets crossed the threshold." Do not dump raw JSON.
  **NO_REPLY**：简要确认"没有市场超过阈值。"不要输出原始 JSON。
- **Empty watchlist**: Guide the user to add entries: "No entries being monitored. Add a market with: `signalradar.py add <polymarket-url>`"
  **空监控列表**：引导用户添加条目："当前没有监控条目。使用 `signalradar.py add <polymarket-url>` 添加市场。"

### Prohibited actions / 禁止操作

- Do not auto-discover or suggest markets to add. Wait for user to provide URLs.
  禁止自动发现或建议添加市场。等待用户提供链接。
- Do not create cron jobs outside of the `schedule` command flow.
  禁止在 `schedule` 命令流程外创建 cron 任务。
- Do not manually edit `cache/`, `config/watchlist.json`, or baseline files.
  禁止手动编辑 `cache/`、`config/watchlist.json` 或基线文件。
- Do not assume a mode — there are no modes. Just run `signalradar.py run`.
  不要假设有模式——没有模式概念。直接运行 `signalradar.py run`。
- Do not mention or attempt to use Notion integration (removed in v0.5.0).
  禁止提及或尝试使用 Notion 集成（已在 v0.5.0 中移除）。

### Language handling / 语言处理

- System messages (prompts, confirmations, status text) follow platform language or `profile.language` setting.
  系统消息（提示、确认、状态文本）跟随平台语言或 `profile.language` 设置。
- Market questions are always displayed in their original English text from Polymarket API. Do not translate market questions.
  市场问题始终以 Polymarket API 返回的原始英文显示。不要翻译市场问题。

## References / 参考

- `references/config.md` — Full configuration reference / 完整配置参考
- `references/protocol.md` — Data contract (EntrySpec, SignalEvent, DeliveryEnvelope) / 数据契约
- `references/operations.md` — SLO targets, retry policy / SLO 目标、重试策略
