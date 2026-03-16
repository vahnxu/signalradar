# CLAUDE.md — SignalRadar

## Project Overview

SignalRadar monitors Polymarket prediction markets for probability changes and sends alerts when thresholds are crossed. Users explicitly add markets by URL — no auto-discovery.

## Key Architecture

- **Entry point**: `scripts/signalradar.py` (CLI dispatcher)
- **Core pipeline**: `run_signalradar_job.py` → ingest → decide → deliver
- **Commands**: `doctor`, `add`, `list`, `show`, `remove`, `run`, `config`, `schedule`, `digest`, `onboard`
- **Zero dependencies**: Python 3.9+ stdlib only (no pip packages)
- **Data source**: Polymarket gamma API (`gamma-api.polymarket.com`)
- **Watchlist storage**: `~/.signalradar/config/watchlist.json` (single source of truth)
- **Crontab-first scheduling**: prefer system `crontab` (zero LLM cost)
- **Digest model**: compare against the previous digest snapshot (`~/.signalradar/cache/digest_state.json`), not against the realtime alert baseline

## Important Conventions

- All scripts are in `scripts/`. No top-level Python files.
- Shipped defaults live in `config/default_config.json`.
- Runtime user config lives in `~/.signalradar/config/signalradar_config.json`.
- Runtime watchlist lives in `~/.signalradar/config/watchlist.json`.
- Runtime baselines live in `~/.signalradar/cache/baselines/`.
- Runtime digest state lives in `~/.signalradar/cache/digest_state.json`.
- `profile.language` controls system-message locale only; Polymarket market names/questions stay in original English.
- Empty `profile.language` uses automatic detection (environment first, timezone fallback).
- The `outcomePrices` field from Polymarket API is a JSON-encoded string, not a Python list. Always use `json.loads()` to parse it.
- There are no "modes" — all entries are checked together via `signalradar.py run`.

## Testing

```bash
# Health check
python3 scripts/signalradar.py doctor --output json

# Dry-run (no side effects)
python3 scripts/signalradar.py run --dry-run --output json
```

## Delivery Adapters

- `webhook` (recommended, portable) — HTTP POST to any webhook endpoint (Slack, Telegram Bot API, Discord, etc.). Zero LLM cost when paired with crontab.
- `file` (portable) — append alerts to local JSONL file
- `openclaw` (OpenClaw-only) — OpenClaw platform messaging. Not portable to other platforms.

## Do NOT

- Modify `~/.signalradar/cache/` or baseline files unless user explicitly asks
- Auto-add markets — wait for user to provide URLs
- Create cron jobs outside of the `schedule` command flow
- Assume `outcomePrices` is a Python list (it's a JSON string)
- Use or mention Notion integration (removed in v0.5.0)
