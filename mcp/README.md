# SignalRadar MCP Server

Optional MCP packaging for SignalRadar's read-only Polymarket market discovery,
market snapshot, trend, and threshold-preview helpers.

The parent SignalRadar skill remains zero-dependency. The `mcp` dependency is
isolated to this optional package under `mcp/`.

## Install

```bash
cd /path/to/signalradar/mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Claude Code Registration

```bash
claude mcp add signalradar -- python3 /path/to/signalradar/mcp/server.py
```

## Tools

| Tool | Arguments | Returns |
|------|-----------|---------|
| `discover_markets` | `query: str = ""`, `limit: int = 10` | Open events matching keywords (or trending when query is empty), ranked by 24h volume: `title`, `slug`, `url`, `volume_24h`, `liquidity`, `end_date`, `market_count`, `top_markets` (≤3 with probabilities). Limit caps at 25. |
| `search_markets` | `query: str` | Polymarket event title, event id, slug, and normalized market list with `id`, `question`, `probability`, `status`, `end_date`, `url`. |
| `get_market` | `market_id: str` | Current market snapshot with probability, 24h volume, liquidity, status, end date, and URL. |
| `get_price_trend` | `market_id: str` | 7-day CLOB trend summary plus capped raw point sample. |
| `check_threshold` | `market_id: str`, `baseline_pct: float`, `threshold_pp: float` | Stateless preview of current probability versus caller-provided baseline. |

## Error Contract

Tools never raise raw exceptions to MCP clients. Failures return:

```json
{"error": "SR_SOURCE_UNAVAILABLE", "message": "..."}
```

or:

```json
{"error": "SR_TIMEOUT", "message": "..."}
```

`check_threshold` is a read-only preview. It does not read, write, or update
SignalRadar's stateful baselines, watchlist, audit log, or runtime config.
