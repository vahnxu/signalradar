# SignalRadar

> Monitor Polymarket prediction markets for probability changes. Get alerts when thresholds are crossed.

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
                     (detect change)     (alert you)
                     threshold check
```

1. You add markets by URL (`add`)
2. SignalRadar fetches live probability from Polymarket API
3. Compares against recorded baseline
4. Sends alert when change exceeds threshold (default: 5 percentage points)
5. Baseline updates after each alert

## Commands

```bash
# First-time setup (bot mode, 3-step)
python3 scripts/signalradar.py onboard --step preview --output json
python3 scripts/signalradar.py onboard --step confirm --keep 1,2,3 --output json
python3 scripts/signalradar.py onboard --step finalize --output json

# Add a market (guided setup or by URL)
python3 scripts/signalradar.py add                              # Guided setup (terminal)
python3 scripts/signalradar.py add <polymarket-url> [--category AI]

# List all monitored entries
python3 scripts/signalradar.py list

# Show one monitored market
python3 scripts/signalradar.py show 2
python3 scripts/signalradar.py show gpt --output json

# Remove an entry by number
python3 scripts/signalradar.py remove 3

# Run a check
python3 scripts/signalradar.py run [--dry-run] [--output json]

# View or change settings
python3 scripts/signalradar.py config [key] [value]
python3 scripts/signalradar.py config threshold.abs_pp 8.0

# Manage auto-monitoring schedule
python3 scripts/signalradar.py schedule [N|disable] [--driver auto|crontab]

# Preview or send periodic digest
python3 scripts/signalradar.py digest [--dry-run] [--force] [--output text|json]

# Health check
python3 scripts/signalradar.py doctor --output json
```

For event URLs that expand to more than 3 markets, `add` force-shows a market preview (count, type summary, and market list) and requires interactive confirmation. `--yes` is rejected on that large-batch path.

## Delivery: Get Alerts Your Way

### Webhook (Recommended) — Slack, Discord, Telegram Bot API, etc.

Portable across all platforms (OpenClaw, Claude Code, standalone). Zero LLM cost when paired with `crontab` scheduling.

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

Save as `~/.signalradar/config/signalradar_config.json`, or use the CLI shortcut:

```bash
python3 scripts/signalradar.py config delivery webhook https://your-webhook-url
```

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

### OpenClaw (platform messaging — OpenClaw only)

Default when installed via ClawHub. Not portable to other platforms. See [OpenClaw install](#openclaw-install) below.

## Auto-Monitoring

SignalRadar attempts to auto-enable 10-minute background monitoring after the first successful `add` or `onboard finalize`. Prefers system `crontab` with `--push` (zero LLM cost).

If `profile.language` is still empty on the first successful `add`, SignalRadar snapshots the detected system-message language into user config so background notifications stay consistent.

```bash
signalradar.py schedule              # Show current status
signalradar.py schedule 30           # Auto driver (crontab-first)
signalradar.py schedule 10 --driver crontab   # Force system crontab
signalradar.py schedule disable      # Disable auto-monitoring
```

## Runtime Data Directory

SignalRadar stores user data outside the skill directory so updates will not wipe your watchlist or baselines.

- Default data root: `~/.signalradar/`
- Config: `~/.signalradar/config/signalradar_config.json`
- Watchlist: `~/.signalradar/config/watchlist.json`
- Baselines: `~/.signalradar/cache/baselines/`
- Audit log: `~/.signalradar/cache/events/signal_events.jsonl`
- Last run metadata: `~/.signalradar/cache/last_run.json`
- Digest snapshot state: `~/.signalradar/cache/digest_state.json`

For local testing, override with `SIGNALRADAR_DATA_DIR=/tmp/signalradar`.

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
| `delivery.primary.channel` | `webhook` | `webhook` (recommended), `file`, `openclaw` |
| `digest.frequency` | `weekly` | `off`, `daily`, `weekly`, `biweekly` |
| `digest.day_of_week` | `monday` | Weekly digest weekday |
| `digest.time_local` | `09:00` | Local send time for digest |
| `digest.top_n` | `10` | Top movers shown in human digest |
| `baseline.cleanup_after_expiry_days` | 90 | Baseline cleanup after market ends |
| `profile.language` | `""` | System-message locale (`zh` / `en`), empty = automatic detection |

See [`references/config.md`](references/config.md) for full reference.

## Digest

SignalRadar includes a periodic digest. It compares the current monitored state against the previous digest snapshot, not against the per-run alert baseline.

- Includes both markets that already triggered realtime HIT alerts and markets with net-over-period changes that never crossed the realtime threshold.
- Uses grouped event summaries for large multi-market events.
- Full detail remains available via `digest --output json`.
- The first automatic digest is bootstrap-only: SignalRadar records the initial digest snapshot silently, then starts user-facing automatic digest delivery from the next report cycle. Use `digest --force` if you want an immediate preview.

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
