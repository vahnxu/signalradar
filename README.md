# SignalRadar

> 信号雷达 — Monitor Polymarket prediction markets for probability changes. Get alerts when thresholds are crossed.
>
> 监控 Polymarket 预测市场概率变化，超过阈值时推送通知。

You choose exactly which markets to monitor by providing Polymarket URLs. Zero dependencies (Python stdlib only).

你通过提供 Polymarket 链接来精确选择要监控的市场。零依赖（仅使用 Python 标准库）。

## Quick Start / 快速开始

```bash
git clone https://github.com/vahnxu/signalradar.git
cd signalradar

# 1. Health check / 健康检查
python3 scripts/signalradar.py doctor --output json

# 2. Add markets (guided setup or by URL) / 添加市场（引导式或通过链接）
python3 scripts/signalradar.py add
python3 scripts/signalradar.py add https://polymarket.com/event/gpt5-release-june

# 3. Monitoring auto-starts after first add (every 10 min)
# 首次添加后自动启动监控（每 10 分钟）

# 4. Check schedule status / 查看调度状态
python3 scripts/signalradar.py schedule

# 5. Manual check (dry-run) / 手动检查（试运行）
python3 scripts/signalradar.py run --dry-run --output json
```

First run records baselines. Subsequent runs detect changes and send alerts.
首次运行记录基线。后续运行检测变化并发送警报。

## How It Works / 工作原理

```
User adds URL  --->  SignalRadar  --->  Delivery Adapter
用户添加链接         (detect change)     (alert you)
                     检测变化              通知你
                     threshold check
                     阈值检查
```

1. You add markets by URL (`add`) / 通过链接添加市场
2. SignalRadar fetches live probability from Polymarket API / 从 Polymarket API 获取实时概率
3. Compares against recorded baseline / 与记录的基线对比
4. Sends alert when change exceeds threshold (default: 5 percentage points) / 变化超过阈值时发送警报（默认：5 个百分点）
5. Baseline updates after each alert / 每次警报后基线更新

## Commands / 命令

```bash
# Add a market (guided setup or by URL) / 添加市场（引导式或通过链接）
python3 scripts/signalradar.py add                              # Guided setup / 引导式
python3 scripts/signalradar.py add <polymarket-url> [--category AI]

# List all monitored entries / 列出所有监控条目
python3 scripts/signalradar.py list

# Remove an entry by number / 按编号移除条目
python3 scripts/signalradar.py remove 3

# Run a check / 执行检查
python3 scripts/signalradar.py run [--dry-run] [--output json]

# View or change settings / 查看或修改设置
python3 scripts/signalradar.py config [key] [value]

# Manage auto-monitoring schedule / 管理自动监控调度
python3 scripts/signalradar.py schedule [N|disable] [--driver crontab|openclaw]

# Health check / 健康检查
python3 scripts/signalradar.py doctor --output json
```

## Delivery: Get Alerts Your Way / 推送方式

### Webhook (Slack, Discord, Telegram, etc.)

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

Save as `config/signalradar_config.json`. / 保存为 `config/signalradar_config.json`。

### File (local JSONL log) / 文件（本地 JSONL 日志）

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

### OpenClaw (platform messaging / 平台消息)

Default when installed via ClawHub. See [OpenClaw install](#openclaw-install) below.
通过 ClawHub 安装时为默认选项。见下方 [OpenClaw 安装](#openclaw-install)。

## Auto-Monitoring / 自动监控

SignalRadar automatically enables 10-minute cron monitoring after the first successful `add` (v0.5.3+).

SignalRadar 在首次 `add` 成功后自动启用 10 分钟 cron 监控（v0.5.3+）。

```bash
signalradar.py schedule              # Show current status / 显示当前状态
signalradar.py schedule 30           # Change to 30-minute interval / 改为 30 分钟间隔
signalradar.py schedule disable      # Disable auto-monitoring / 禁用自动监控
```

### Threshold vs Frequency / 阈值 vs 频率

- **Threshold / 阈值** — how much probability must change before an alert fires. Use `config` to adjust.
  概率需要变化多少才触发警报。用 `config` 调整。
- **Frequency / 频率** — how often SignalRadar checks markets. Use `schedule` to adjust.
  SignalRadar 多久检查一次市场。用 `schedule` 调整。

## Understanding Results / 理解运行结果

| Status | Meaning / 含义 |
|--------|----------------|
| `BASELINE` | First observation. Baseline recorded, no alert. / 首次观测，记录基线，不发警报。 |
| `SILENT` | Change below threshold. No alert. / 变化低于阈值，不发警报。 |
| `HIT` | Threshold crossed. Alert sent. Baseline updated. / 超过阈值，发送警报，基线更新。 |
| `NO_REPLY` | No markets crossed threshold. / 无市场超过阈值。 |

Example HIT / HIT 示例：
```
GPT-5 release by June 2026: 32% -> 41% (+9pp), crossing 5pp threshold. Baseline updated to 41%.
GPT-5 在 2026 年 6 月前发布：32% -> 41%（+9pp），超过 5pp 阈值。基线已更新至 41%。
```

## Configuration / 配置

All optional. Works out of the box with defaults.
全部可选。开箱即用，默认配置即可运行。

| Setting / 设置 | Default / 默认值 | Description / 说明 |
|----------------|-------------------|---------------------|
| `threshold.abs_pp` | 5.0 | Alert threshold in percentage points / 警报阈值（百分点） |
| `threshold.per_category_abs_pp` | `{}` | Per-category override / 按分类覆盖阈值 |
| `delivery.primary.channel` | `openclaw` | Delivery adapter / 推送适配器 |
| `digest.frequency` | `weekly` | Periodic report frequency / 定期报告频率 |
| `baseline.cleanup_after_expiry_days` | 90 | Baseline cleanup after market ends / 市场到期后清理基线天数 |

See [`references/config.md`](references/config.md) for full reference. / 完整参考请查看 `references/config.md`。

## OpenClaw Install / OpenClaw 安装

If you use [OpenClaw](https://clawhub.com), install directly from the marketplace:
如果你使用 [OpenClaw](https://clawhub.com)，可以直接从市场安装：

```bash
clawhub install signalradar
```

## Requirements / 运行要求

- Python 3.9+
- Network access to `gamma-api.polymarket.com` / 需要网络访问 `gamma-api.polymarket.com`
- No pip dependencies (stdlib only) / 无 pip 依赖（仅标准库）

## License / 许可

MIT
