# SignalRadar

Monitor Polymarket prediction markets for probability changes. Get alerts when thresholds are crossed.

You choose exactly which markets to monitor by providing Polymarket URLs. Zero dependencies (Python stdlib only).

## Quick Start

```bash
git clone https://github.com/vahnxu/signalradar.git
cd signalradar

# 1. Health check
python3 scripts/signalradar.py doctor --output json

# 2. Add markets (guided setup or by URL)
python3 scripts/signalradar.py add
python3 scripts/signalradar.py add https://polymarket.com/event/gpt5-release-june

# 3. Monitoring auto-starts after first add (every 10 min)

# 4. Check schedule status
python3 scripts/signalradar.py schedule

# 5. Manual check (dry-run)
python3 scripts/signalradar.py run --dry-run --output json
```

First run records baselines. Subsequent runs detect changes and send alerts.

## How It Works

```
User adds URL  --->  SignalRadar  --->  Delivery Adapter
                     (detect change)    (alert you)
                     threshold check
```

1. You add markets by URL (`add`)
2. SignalRadar fetches live probability from Polymarket API
3. Compares against recorded baseline
4. Sends alert when change exceeds threshold (default: 5 percentage points)
5. Baseline updates after each alert

## Commands

```bash
# Add a market (guided setup or by URL)
python3 scripts/signalradar.py add                              # Guided setup
python3 scripts/signalradar.py add <polymarket-url> [--category AI]

# List all monitored entries
python3 scripts/signalradar.py list

# Remove an entry by number
python3 scripts/signalradar.py remove 3

# Run a check
python3 scripts/signalradar.py run [--dry-run] [--output json]

# View or change settings
python3 scripts/signalradar.py config [key] [value]

# Manage auto-monitoring schedule
python3 scripts/signalradar.py schedule [N|disable] [--driver crontab|openclaw]

# Health check
python3 scripts/signalradar.py doctor --output json
```

## Delivery: Get Alerts Your Way

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

Save as `config/signalradar_config.json`.

### File (local JSONL log)

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

### OpenClaw (platform messaging)

Default when installed via ClawHub. See [OpenClaw install](#openclaw-install) below.

## Auto-Monitoring

SignalRadar automatically enables 10-minute cron monitoring after the first successful `add` (v0.5.3+).

```bash
signalradar.py schedule              # Show current status
signalradar.py schedule 30           # Change to 30-minute interval
signalradar.py schedule disable      # Disable auto-monitoring
```

### Threshold vs Frequency

- **Threshold** — how much probability must change before an alert fires. Use `config` to adjust.
- **Frequency** — how often SignalRadar checks markets. Use `schedule` to adjust.

## Understanding Results

| Status | Meaning |
|--------|---------|
| `BASELINE` | First observation. Baseline recorded, no alert. |
| `SILENT` | Change below threshold. No alert. |
| `HIT` | Threshold crossed. Alert sent. Baseline updated. |
| `NO_REPLY` | No markets crossed threshold. |

Example HIT:
```
GPT-5 release by June 2026: 32% -> 41% (+9pp), crossing 5pp threshold. Baseline updated to 41%.
```

## Configuration

All optional. Works out of the box with defaults.

| Setting | Default | Description |
|---------|---------|-------------|
| `threshold.abs_pp` | 5.0 | Alert threshold in percentage points |
| `threshold.per_category_abs_pp` | `{}` | Per-category override |
| `delivery.primary.channel` | `openclaw` | Delivery adapter |
| `digest.frequency` | `weekly` | Periodic report frequency |
| `baseline.cleanup_after_expiry_days` | 90 | Baseline cleanup after market ends |

See [`references/config.md`](references/config.md) for full reference.

## OpenClaw Install

If you use [OpenClaw](https://clawhub.com), install directly from the marketplace:

```bash
clawhub install signalradar
```

## Requirements

- Python 3.9+
- Network access to `gamma-api.polymarket.com`
- No pip dependencies (stdlib only)

## License

MIT
