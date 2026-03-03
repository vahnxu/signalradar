# CLAUDE.md — SignalRadar

## Project Overview

SignalRadar monitors Polymarket prediction markets for probability changes and sends alerts when thresholds are crossed. Three categories: AI model releases, crypto, geopolitics.

## Key Architecture

- **Entry point**: `scripts/signalradar.py` (CLI dispatcher)
- **Core pipeline**: `run_signalradar_job.py` → ingest → decide → deliver
- **Modes**: `ai`, `crypto`, `geopolitics`, `watchlist-refresh`
- **Zero dependencies**: Python 3.9+ stdlib only (no pip packages)
- **Data source**: Polymarket gamma API (`gamma-api.polymarket.com`)

## Important Conventions

- All scripts are in `scripts/`. No top-level Python files.
- Config lives in `config/`. User config: `config/signalradar_config.json`.
- Baselines stored in `cache/baselines/` (gitignored).
- The `outcomePrices` field from Polymarket API is a JSON-encoded string, not a Python list. Always use `json.loads()` to parse it.
- Watchlist for `ai` mode is in `memory/polymarket_watchlist_2026.md`.

## Testing

```bash
# Health check
python3 scripts/signalradar.py doctor --output json

# Dry-run (no side effects)
python3 scripts/signalradar.py run --mode ai --dry-run --output json

# Prepublish gate
python3 scripts/sr_prepublish_gate.py --json
```

## Delivery Adapters

- `openclaw:direct` — OpenClaw platform messaging (default when installed via ClawHub)
- `file:/path` — append alerts to local JSONL file
- `webhook:https://...` — HTTP POST to any webhook endpoint (Slack, Discord, etc.)

## Do NOT

- Modify `cache/` or baseline files unless user explicitly asks
- Create cron jobs automatically
- Assume `outcomePrices` is a Python list (it's a JSON string)
- Put optional env vars in `requires.env` (use `envHelp` instead)
