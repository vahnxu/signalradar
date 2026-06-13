# SignalRadar

[English](README.md) | [简体中文](README.zh-CN.md)

> 监控 Polymarket 预测市场的概率变化，并在变化超过阈值时发送提醒。

你可以通过提供 Polymarket URL 精确选择要监控的市场。SignalRadar 零依赖，仅使用 Python 标准库。

## 快速开始

```bash
git clone https://github.com/vahnxu/signalradar.git
cd signalradar

# 1. 健康检查
python3 scripts/signalradar.py doctor --output json

# 2. 添加市场（引导式设置或直接提供 URL）
python3 scripts/signalradar.py add
python3 scripts/signalradar.py add https://polymarket.com/event/gpt5-release-june

# 3. 首次添加成功后会自动启动监控（默认每 10 分钟）

# 4. 查看调度状态
python3 scripts/signalradar.py schedule

# 5. 手动检查（dry-run，不写入状态）
python3 scripts/signalradar.py run --dry-run --output json
```

首次运行会记录基线。之后每次运行会检测变化，并在触发阈值时发送提醒。

## 工作原理

```text
用户添加 URL  --->  SignalRadar  --->  推送适配器
                    检测概率变化        发送提醒
                    检查阈值
```

1. 你通过 URL 添加要监控的市场（`add`）
2. SignalRadar 从 Polymarket API 获取实时概率
3. 与本地记录的基线进行比较
4. 当变化超过阈值时发送提醒（默认阈值：5 个百分点）
5. 触发提醒后，基线会更新为新的概率

## 命令

```bash
# 首次设置（Bot 模式，3 步）
python3 scripts/signalradar.py onboard --step preview --output json
python3 scripts/signalradar.py onboard --step confirm --keep 1,2,3 --output json
python3 scripts/signalradar.py onboard --step finalize --output json

# 添加市场（引导式设置或直接提供 URL）
python3 scripts/signalradar.py add                              # 终端引导式设置
python3 scripts/signalradar.py add <polymarket-url> [--category AI]

# 列出全部监控项
python3 scripts/signalradar.py list

# 查看单个监控市场
python3 scripts/signalradar.py show 2
python3 scripts/signalradar.py show gpt --output json

# 按编号移除监控项
python3 scripts/signalradar.py remove 3

# 执行一次检查
python3 scripts/signalradar.py run [--dry-run] [--output json]

# 查看或修改设置
python3 scripts/signalradar.py config [key] [value]
python3 scripts/signalradar.py config threshold.abs_pp 8.0

# 管理自动监控调度
python3 scripts/signalradar.py schedule [N|disable] [--driver auto|crontab]

# 预览或发送周期摘要
python3 scripts/signalradar.py digest [--dry-run] [--force] [--output text|json]

# 健康检查
python3 scripts/signalradar.py doctor --output json
```

对于会展开成 3 个以上子市场的事件 URL，`add` 会强制展示市场预览（数量、类型摘要和市场列表），并要求交互确认。在这种大批量路径下，`--yes` 会被拒绝。

## 推送方式

### Webhook（推荐）- Slack、Discord、Telegram Bot API 等

Webhook 可跨平台使用（OpenClaw、Claude Code、独立部署均可）。与 `crontab` 调度配合时，可以零 LLM 成本发送通知。

```json
{
  "delivery": {
    "primary": {
      "channel": "webhook",
      "target": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
    }
  }
}
```

保存到 `~/.signalradar/config/signalradar_config.json`，或使用 CLI 快捷命令：

```bash
python3 scripts/signalradar.py config delivery webhook https://your-webhook-url
```

### File（本地 JSONL 日志）

```json
{
  "delivery": {
    "primary": {
      "channel": "file",
      "target": "/path/to/alerts.jsonl"
    }
  }
}
```

### OpenClaw（平台消息，仅 OpenClaw）

通过 ClawHub 安装时默认使用 OpenClaw 平台消息。这个通道不适用于其他平台。参见下方 [OpenClaw 安装](#openclaw-安装)。

## 自动监控

首次成功执行 `add` 或 `onboard finalize` 后，SignalRadar 会尝试自动启用 10 分钟一次的后台监控。默认优先使用系统 `crontab` 和 `--push`，这样不需要 LLM 参与推送。

如果首次成功 `add` 时 `profile.language` 仍为空，SignalRadar 会把检测到的系统消息语言写入用户配置，确保后台通知语言保持一致。

```bash
signalradar.py schedule              # 显示当前状态
signalradar.py schedule 30           # 自动选择驱动（优先 crontab）
signalradar.py schedule 10 --driver crontab   # 强制使用系统 crontab
signalradar.py schedule disable      # 禁用自动监控
```

## 运行数据目录

SignalRadar 会把用户数据存放在 skill 目录外，因此更新不会覆盖你的监控列表或基线。

- 默认数据根目录：`~/.signalradar/`
- 配置：`~/.signalradar/config/signalradar_config.json`
- 监控列表：`~/.signalradar/config/watchlist.json`
- 基线：`~/.signalradar/cache/baselines/`
- 审计日志：`~/.signalradar/cache/events/signal_events.jsonl`
- 最近运行元数据：`~/.signalradar/cache/last_run.json`
- 摘要快照状态：`~/.signalradar/cache/digest_state.json`

本地测试时，可使用 `SIGNALRADAR_DATA_DIR=/tmp/signalradar` 覆盖默认目录。

### 阈值与频率

- **阈值**：概率变化达到多少才触发提醒。使用 `config` 调整。
- **频率**：SignalRadar 多久检查一次市场。使用 `schedule` 调整。

## 理解结果

| 状态 | 含义 |
|------|------|
| `BASELINE` | 首次观测。记录基线，不发送提醒。 |
| `SILENT` | 变化低于阈值，不发送提醒。 |
| `HIT` | 变化超过阈值。已发送提醒，并更新基线。 |
| `NO_REPLY` | 没有市场超过阈值。 |

HIT 示例：

```text
GPT-5 release by June 2026: 32% -> 41% (+9pp), crossing 5pp threshold. Baseline updated to 41%.
```

## 配置

所有配置项都是可选的。默认配置即可开箱使用。

| 设置 | 默认值 | 说明 |
|------|--------|------|
| `threshold.abs_pp` | 5.0 | 提醒阈值（百分点） |
| `threshold.per_category_abs_pp` | `{}` | 按分类覆盖阈值 |
| `delivery.primary.channel` | `webhook` | `webhook`（推荐）、`file`、`openclaw` |
| `digest.frequency` | `weekly` | `off`、`daily`、`weekly`、`biweekly` |
| `digest.day_of_week` | `monday` | 周期摘要发送星期 |
| `digest.time_local` | `09:00` | 周期摘要本地发送时间 |
| `digest.top_n` | `10` | 人类可读摘要中展示的最大变化条目数 |
| `baseline.cleanup_after_expiry_days` | 90 | 市场结束后保留基线的天数 |
| `profile.language` | `""` | 系统消息语言（`zh` / `en`），空值表示自动检测 |

完整配置参考见 [`references/config.md`](references/config.md)。

## 周期摘要

SignalRadar 包含周期摘要功能。它比较的是当前监控状态与上一份摘要快照，而不是单次运行的提醒基线。

- 包含已经触发过实时 HIT 提醒的市场，也包含周期内净变化明显但未触发实时阈值的市场。
- 对大型多市场事件使用分组摘要。
- 完整明细可通过 `digest --output json` 查看。
- 第一次自动摘要只用于静默建立初始快照；从下一个摘要周期开始才会发送给用户。想立即预览可使用 `digest --force`。

## OpenClaw 安装

如果你使用 [OpenClaw](https://clawhub.com)，可以直接从 marketplace 安装：

```bash
clawhub install signalradar
```

## MCP 服务器（面向 AI Agent）

可选的只读 [MCP](https://modelcontextprotocol.io) 服务器位于 [`mcp/`](mcp/)，向任何 MCP 客户端（Claude Code/Desktop、Cursor、Windsurf 等）暴露市场搜索、快照、7 天趋势和阈值预览四个工具。主体 skill 保持零依赖，`mcp` 依赖隔离在该目录内。详见 [`mcp/README.md`](mcp/README.md)。

## 运行要求

- Python 3.9+
- 能访问 `gamma-api.polymarket.com`
- 无 pip 依赖（仅 Python 标准库）

## 许可证

MIT
