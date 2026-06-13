# SignalRadar（信号雷达）

> 监控 Polymarket 预测市场概率变化，超过阈值时推送通知。

[English](README.md) | 简体中文

你通过提供 Polymarket 链接来精确选择要监控的市场。零依赖（仅使用 Python 标准库）。

SignalRadar 有两种使用方式：

1. **MCP 服务器** —— 把只读的 Polymarket 查询工具接入任意 AI agent（Claude Code/Desktop、Cursor、Windsurf 等）。如果你在搭 agent，从这里开始。
2. **CLI skill** —— 带状态的监控产品：watchlist、定时检查、阈值报警、周报。如果你想要全天候盯盘推送，从这里开始。

## 在 AI Agent 中使用（MCP 服务器）

可选的只读 [MCP](https://modelcontextprotocol.io) 服务器位于 [`mcp/`](mcp/)，把 SignalRadar 久经实战的 Polymarket 数据核心暴露给任意 MCP 客户端：

| 工具 | 功能 |
|------|------|
| `search_markets` | 按 URL、slug 或关键词解析 Polymarket 事件 |
| `get_market` | 当前快照：概率、24h 成交量、流动性、状态 |
| `get_price_trend` | 7 天价格趋势统计 + 采样历史点 |
| `check_threshold` | 当前概率 vs 给定基线的无状态阈值预览 |

```bash
pip install -r mcp/requirements.txt
claude mcp add signalradar -- python3 /path/to/signalradar/mcp/server.py
```

主体 skill 保持零依赖；`mcp` 依赖隔离在该目录内。工具永不抛裸异常——失败时返回结构化的 `{"error", "message"}`。完整参考见 [`mcp/README.md`](mcp/README.md)。

## 快速开始（CLI）

```bash
git clone https://github.com/vahnxu/signalradar.git
cd signalradar

# 1. 健康检查
python3 scripts/signalradar.py doctor --output json

# 2. 添加市场（引导式或通过链接）
python3 scripts/signalradar.py add
python3 scripts/signalradar.py add https://polymarket.com/event/gpt5-release-june

# 3. 首次添加后自动启动监控（每 10 分钟）

# 4. 查看调度状态
python3 scripts/signalradar.py schedule

# 5. 手动检查（试运行）
python3 scripts/signalradar.py run --dry-run --output json
```

首次运行记录基线。后续运行检测变化并发送警报。

## 工作原理

```
用户添加链接  --->  SignalRadar  --->  推送适配器
                    （检测变化）        （通知你）
                    阈值检查
```

1. 通过链接添加市场（`add`）
2. SignalRadar 从 Polymarket API 获取实时概率
3. 与记录的基线对比
4. 变化超过阈值时发送警报（默认：5 个百分点）
5. 每次警报后基线更新

## 命令

```bash
# 首次设置（bot 模式，3 步）
python3 scripts/signalradar.py onboard --step preview --output json
python3 scripts/signalradar.py onboard --step confirm --keep 1,2,3 --output json
python3 scripts/signalradar.py onboard --step finalize --output json

# 添加市场（引导式或通过链接）
python3 scripts/signalradar.py add                              # 引导式（终端）
python3 scripts/signalradar.py add <polymarket-url> [--category AI]

# 列出所有监控条目
python3 scripts/signalradar.py list

# 查看单个监控市场
python3 scripts/signalradar.py show 2
python3 scripts/signalradar.py show gpt --output json

# 按编号移除条目
python3 scripts/signalradar.py remove 3

# 执行检查
python3 scripts/signalradar.py run [--dry-run] [--output json|openclaw]

# 查看或修改设置
python3 scripts/signalradar.py config [key] [value]
python3 scripts/signalradar.py config threshold.abs_pp 8.0

# 管理自动监控调度
python3 scripts/signalradar.py schedule [N|disable] [--driver auto|crontab|openclaw]

# 预览或发送定期报告
python3 scripts/signalradar.py digest [--dry-run] [--force] [--output text|json|openclaw]

# 健康检查
python3 scripts/signalradar.py doctor --output json
```

对于展开后超过 3 个市场的事件链接，`add` 会强制先展示市场预览（数量、类型摘要、市场列表），并要求交互确认；该大批量路径下 `--yes` 会被拒绝。

## 推送方式

### Webhook（推荐）—— Slack、Discord、Telegram Bot API 等

可跨所有平台使用（OpenClaw、Claude Code、独立部署）。配合 `crontab` 调度，零 LLM 成本。

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

保存为 `~/.signalradar/config/signalradar_config.json`。

### 文件（本地 JSONL 日志）

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

### OpenClaw（平台消息 —— 仅 OpenClaw）

通过 ClawHub 安装时为默认选项。不可移植到其他平台。见下方 [OpenClaw 安装](#openclaw-安装)。

## 自动监控

SignalRadar 在首次 `add` 或 `onboard finalize` 成功后尝试自动启用 10 分钟后台监控（v0.9.0）。默认优先使用系统 `crontab` + `--push`（零 LLM 成本）；仅在 crontab 不可用时回退到 `openclaw cron`。

**Route gate（OpenClaw 用户）**：当推送通道为 `openclaw` + `crontab` 驱动 + 尚无已捕获的 reply route（`~/.signalradar/cache/openclaw_reply_route.json`）时，CLI 拒绝启用 cron 任务并返回 `route_missing`，不会静默启用一个无法推送的调度。Route 在任意前台 bot 交互时自动捕获。用 `schedule --output json` 检查 `route_ready` 状态。

如果首次 `add` 成功时 `profile.language` 仍为空，SignalRadar 会把检测到的系统文案语言写入用户配置，避免后台通知再依赖瞬时环境猜测。

```bash
signalradar.py schedule              # 显示当前状态
signalradar.py schedule 30           # 自动选择驱动（优先 crontab）
signalradar.py schedule 10 --driver openclaw  # 强制使用 OpenClaw cron
signalradar.py schedule 10 --driver crontab   # 强制使用系统 crontab
signalradar.py schedule disable      # 禁用自动监控
```

## 运行数据目录

SignalRadar 将用户数据存放在 skill 目录外，避免 `clawhub update` 覆盖监控列表和基线。

- 默认数据目录：`~/.signalradar/`
- 配置：`~/.signalradar/config/signalradar_config.json`
- 监控列表：`~/.signalradar/config/watchlist.json`
- 基线：`~/.signalradar/cache/baselines/`
- 审计日志：`~/.signalradar/cache/events/signal_events.jsonl`
- 最近运行状态：`~/.signalradar/cache/last_run.json`
- 周报快照状态：`~/.signalradar/cache/digest_state.json`

本地测试可使用 `SIGNALRADAR_DATA_DIR=/tmp/signalradar` 覆盖默认目录。

### 阈值 vs 频率

- **阈值** —— 概率需要变化多少才触发警报。用 `config` 调整。
- **频率** —— SignalRadar 多久检查一次市场。用 `schedule` 调整。

## 理解运行结果

| 状态 | 含义 |
|------|------|
| `BASELINE` | 首次观测，记录基线，不发警报。 |
| `SILENT` | 变化低于阈值，不发警报。 |
| `HIT` | 超过阈值，发送警报，基线更新。 |
| `NO_REPLY` | 无市场超过阈值。 |

HIT 示例：
```
GPT-5 release by June 2026: 32% -> 41% (+9pp), crossing 5pp threshold. Baseline updated to 41%.
📈 7d: 28% -> 41% (low 26% · high 43%)
💰 24h vol $12.7k · liq $690k
```

自 v1.1.0 起，HIT 告警可附带纯展示性的上下文行（7 天概率趋势、24 小时成交量/流动性）。数据不可用时整行省略；设置 `source.trend_context` 为 `false` 可关闭。上下文不参与阈值判断和基线更新。

## 配置

全部可选。开箱即用，默认配置即可运行。

| 设置 | 默认值 | 说明 |
|------|--------|------|
| `threshold.abs_pp` | 5.0 | 警报阈值（百分点） |
| `threshold.per_category_abs_pp` | `{}` | 按分类覆盖阈值 |
| `delivery.primary.channel` | `webhook` | 支持：`webhook`（推荐）、`openclaw`、`file` |
| `digest.frequency` | `weekly` | `off` / `daily` / `weekly` / `biweekly` |
| `digest.day_of_week` | `monday` | 周报发送星期 |
| `digest.time_local` | `09:00` | 周报本地发送时间 |
| `digest.top_n` | `10` | 周报文本中展示的最大变化条目数 |
| `baseline.cleanup_after_expiry_days` | 90 | 市场到期后清理基线天数 |
| `source.trend_context` | `true` | HIT 告警中的 7 天趋势与量/流动性上下文行开关 |
| `profile.language` | `""` | 系统文案语言（`zh` / `en`），空值自动检测（环境优先，时区兜底） |

完整参考请查看 [`references/config.md`](references/config.md)。

`run --output json` 保持冻结字段（`status`、`request_id`、`ts`、`hits`、`errors`），并可能包含供 agent 侧过滤的 `observations` 数组。

`run --output openclaw` 保留给平台调度：安静运行输出 `HEARTBEAT_OK`，HIT 时输出用户可读告警文本，周报到期且推送通道为 `openclaw` 时附周报文本。

`add --output json` 返回结构化的 `added` / `skipped` 结果；首次成功 `add` 尝试自动监控时附 `schedule` 对象（route gate 阻止启用时该对象仍存在，`auto_enabled: false`）。`onboard --step finalize --output json` 返回独立的 `ONBOARD_COMPLETE` 载荷和单独的 `schedule` 字段。

`digest --output json` 返回结构化周报预览/快照。人类可读周报对多子市场事件按事件分组展示头部变动，不会倾倒全部市场。

## 定期报告

SignalRadar v0.8.3 已包含定期报告功能。它比较的是"当前监控状态"和"上一份周报快照"，而不是单次运行的告警基线。

- 同时包含"已触发实时 HIT 的市场"和"虽然没触发实时阈值、但周期净变化依然明显的市场"。
- 对大量子市场的事件使用按事件分组的摘要展示。
- 完整明细通过 `digest --output json` 提供。
- 首次自动周报只做静默建快照：SignalRadar 会先记录初始周报快照，从下一个周期开始才自动向用户发送周报。如需立即预览，请使用 `digest --force`。

## OpenClaw 安装

如果你使用 [OpenClaw](https://clawhub.com)，可以直接从市场安装：

```bash
clawhub install signalradar
```

## 运行要求

- Python 3.9+
- 需要网络访问 `gamma-api.polymarket.com`（趋势上下文另需 `clob.polymarket.com`）
- 无 pip 依赖（仅标准库）；可选的 MCP 服务器有自己隔离的依赖

## 许可

MIT
