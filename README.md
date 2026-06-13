# SignalRadar

> Monitor Polymarket prediction markets for probability changes. Get alerts when thresholds are crossed.

### English | [简体中文](README.zh-CN.md)

You choose exactly which markets to monitor by providing Polymarket URLs. Zero dependencies (Python stdlib only).

There are two ways to use SignalRadar:

1. **MCP server** — plug read-only Polymarket query tools into any AI agent (Claude Code/Desktop, Cursor, Windsurf, ...). Start here if you are wiring up an agent.
2. **CLI skill** — a stateful watchlist monitor with scheduled checks, threshold alerts, and weekly digests. Start here if you want standing alerts pushed to you.

## Use from AI Agents (MCP Server)

An optional read-only [MCP](https://modelcontextprotocol.io) server lives in [`mcp/`](mcp/). It exposes SignalRadar's battle-tested Polymarket data core to any MCP client:

| Tool | What it does |
|------|--------------|
| `search_markets` | Resolve a Polymarket event by URL, slug, or keywords |
| `get_market` | Current snapshot: probability, 24h volume, liquidity, status |
| `get_price_trend` | 7-day price trend stats plus sampled history points |
| `check_threshold` | Stateless preview of current probability vs a given baseline |

```bash
pip install -r mcp/requirements.txt
claude mcp add signalradar -- python3 /path/to/signalradar/mcp/server.py
```

The main skill stays zero-dependency; the `mcp` dependency is isolated to that folder. Tools never raise — failures return structured `{"error", "message"}` payloads. See [`mcp/README.md`](mcp/README.md) for the full reference.

## Quick Start (CLI)

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
python3 scripts/signalradar.py run [--dry-run] [--output json|openclaw]

# View or change settings
python3 scripts/signalradar.py config [key] [value]
python3 scripts/signalradar.py config threshold.abs_pp 8.0

# Manage auto-monitoring schedule
python3 scripts/signalradar.py schedule [N|disable] [--driver auto|crontab|openclaw]

# Preview or send periodic digest
python3 scripts/signalradar.py digest [--dry-run] [--force] [--output text|json|openclaw]

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

Save as `~/.signalradar/config/signalradar_config.json`.

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

SignalRadar attempts to auto-enable 10-minute background monitoring after the first successful `add` or `onboard finalize` (v0.9.0). Prefers system `crontab` with `--push` (zero LLM cost); falls back to `openclaw cron` when crontab is unavailable.

**Route gate (OpenClaw users):** When using `openclaw` delivery with `crontab` scheduling, auto-monitoring requires a captured reply route (`~/.signalradar/cache/openclaw_reply_route.json`). If no route is stored, the CLI **refuses to arm** the cron job and returns `route_missing` — it will not silently enable a schedule that cannot push. The route is automatically captured during any foreground bot interaction. Use `schedule --output json` to check `route_ready` status.

If `profile.language` is still empty on the first successful `add`, SignalRadar snapshots the detected system-message language into user config so background notifications stay consistent.

```bash
signalradar.py schedule              # Show current status
signalradar.py schedule 30           # Auto driver (crontab-first)
signalradar.py schedule 10 --driver openclaw  # Force OpenClaw cron
signalradar.py schedule 10 --driver crontab   # Force system crontab
signalradar.py schedule disable      # Disable auto-monitoring
```

## Runtime Data Directory

SignalRadar stores user data outside the skill directory so `clawhub update` will not wipe your watchlist or baselines.

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
📈 7d: 28% -> 41% (low 26% · high 43%)
💰 24h vol $12.7k · liq $690k
```

Since v1.1.0, HIT alerts include optional display-only context lines: a 7-day price trend and 24h volume / liquidity. Lines are omitted when data is unavailable; set `source.trend_context` to `false` to disable them. Context never affects threshold decisions or baselines.

## Configuration

All optional. Works out of the box with defaults.

| Setting | Default | Description |
|---------|---------|-------------|
| `threshold.abs_pp` | 5.0 | Alert threshold in percentage points |
| `threshold.per_category_abs_pp` | `{}` | Per-category override |
| `delivery.primary.channel` | `webhook` | Supported: `webhook` (recommended), `openclaw`, `file` |
| `digest.frequency` | `weekly` | `off`, `daily`, `weekly`, `biweekly` |
| `digest.day_of_week` | `monday` | Weekly digest weekday |
| `digest.time_local` | `09:00` | Local send time for digest |
| `digest.top_n` | `10` | Top movers shown in human digest |
| `baseline.cleanup_after_expiry_days` | 90 | Baseline cleanup after market ends |
| `source.trend_context` | `true` | Show 7d trend + 24h volume/liquidity context lines in HIT alerts |
| `profile.language` | `""` | System-message locale (`zh` / `en`), empty = automatic detection (env first, timezone fallback) |

See [`references/config.md`](references/config.md) for full reference.

`run --output json` keeps the frozen fields (`status`, `request_id`, `ts`, `hits`, `errors`) and may include an `observations` array for agent-side filtering.

`run --output openclaw` is reserved for platform scheduling. It prints `HEARTBEAT_OK` on quiet runs, user-ready alert text on HIT runs, and digest text when a scheduled digest is due and the primary delivery channel is `openclaw`.

`add --output json` returns structured `added` / `skipped` results and includes a `schedule` object when the first successful `add` attempts auto-monitoring (the object is present even when route gate blocks arming, with `auto_enabled: false`). `onboard --step finalize --output json` returns its own `ONBOARD_COMPLETE` payload with a separate `schedule` field.

`digest --output json` returns a structured digest preview/snapshot. Human-readable digest text groups large multi-market events by event and shows top movers instead of dumping every market.

## Digest

SignalRadar v0.8.3 includes a periodic digest. It compares the current monitored state against the previous digest snapshot, not against the per-run alert baseline.

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
- Network access to `gamma-api.polymarket.com` (and `clob.polymarket.com` for trend context)
- No pip dependencies (stdlib only); the optional MCP server has its own isolated requirement

## License

MIT
