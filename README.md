# SignalRadar

Monitor Polymarket prediction markets for probability changes. Get alerts when thresholds are crossed.

Covers **AI model releases**, **crypto**, and **geopolitics** categories. Zero dependencies (Python stdlib only).

## Quick Start

```bash
git clone https://github.com/vahnxu/signalradar.git
cd signalradar

# Health check
python3 scripts/signalradar.py doctor --output json

# Run AI market monitoring (dry-run, no side effects)
python3 scripts/signalradar.py run --mode ai --dry-run --output json
```

First run returns `BASELINE` (records current probabilities). Run again later to detect changes.

## How It Works

```
Polymarket API  --->  SignalRadar  --->  Delivery Adapter
(live data)          (detect change)     (alert you)
                     threshold check
```

SignalRadar fetches live market data, compares against recorded baselines, and sends alerts when probability changes exceed your threshold (default: 5 percentage points).

## Monitoring Modes

```bash
# AI models, AGI timelines, AI regulation
python3 scripts/signalradar.py run --mode ai

# Bitcoin, Ethereum, DeFi
python3 scripts/signalradar.py run --mode crypto

# Elections, conflicts, sanctions
python3 scripts/signalradar.py run --mode geopolitics
```

## Delivery: Get Alerts Your Way

SignalRadar supports three delivery adapters. **Webhook is the recommended method for most users.**

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

Save as `config/signalradar_config.json`. Works with any service that accepts HTTP POST webhooks.

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

## Automated Monitoring with Cron

```bash
# Every hour - AI markets
0 * * * * cd /path/to/signalradar && python3 scripts/signalradar.py run --mode ai

# Every 4 hours - Crypto
0 */4 * * * cd /path/to/signalradar && python3 scripts/signalradar.py run --mode crypto

# Every 6 hours - Geopolitics
0 */6 * * * cd /path/to/signalradar && python3 scripts/signalradar.py run --mode geopolitics
```

## Understanding Results

| Status | Meaning |
|--------|---------|
| `BASELINE` | First observation. Baseline recorded, no alert. |
| `SILENT` | Change below threshold. No alert. |
| `HIT` | Threshold crossed. Alert sent. |
| `NO_REPLY` | No markets crossed threshold. |

Example HIT output:
```
GPT-5 release by June 2026: 32% -> 41% (+9pp), crossing 5pp threshold
```

## Configuration

All optional. Works out of the box with defaults.

| Setting | Default | Description |
|---------|---------|-------------|
| `threshold.abs_pp` | 5.0 | Alert threshold in percentage points |
| `threshold.per_category_abs_pp` | varies | Per-category override |
| `baseline.cleanup_ttl_days` | 45 | Auto-cleanup stale baselines |

See [`references/config.md`](references/config.md) for full reference.

## Optional: Notion Watchlist

The `watchlist-refresh` mode syncs your monitoring list from Notion. This is the only feature requiring environment variables.

```bash
export NOTION_API_KEY="ntn_xxxxxxxxxxxx"
export NOTION_PARENT_PAGE_ID="32-char-hex-from-page-url"

# Preview first
python3 scripts/signalradar.py run --mode watchlist-refresh --dry-run

# Apply
python3 scripts/signalradar.py run --mode watchlist-refresh
```

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
