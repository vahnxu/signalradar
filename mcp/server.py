#!/usr/bin/env python3
"""SignalRadar read-only MCP server.

This optional package exposes SignalRadar's Polymarket discovery and snapshot
helpers over MCP without adding dependencies to the parent skill runtime.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP


SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from discover_entries import (  # noqa: E402
    DISCOVER_DEFAULT_LIMIT,
    discover_events,
    fetch_market_current_result,
    fetch_price_history_points,
    parse_polymarket_url,
    resolve_event,
    summarize_trend,
)


mcp = FastMCP("signalradar")

SR_SOURCE_UNAVAILABLE = "SR_SOURCE_UNAVAILABLE"
SR_TIMEOUT = "SR_TIMEOUT"


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": code, "message": message}


def _exception_error(exc: Exception, context: str) -> dict[str, Any]:
    if isinstance(exc, TimeoutError):
        return _error(SR_TIMEOUT, f"{context} timed out.")
    return _error(SR_SOURCE_UNAVAILABLE, f"{context}: {exc}")


def _query_to_slug(query: str) -> str:
    parsed = parse_polymarket_url(query)
    if parsed:
        return parsed
    lowered = query.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")


def _market_summary(market: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": market.get("market_id", ""),
        "question": market.get("question", ""),
        "probability": market.get("probability"),
        "status": market.get("status"),
        "end_date": market.get("end_date"),
        "url": market.get("url"),
    }


def _market_snapshot(market: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": market.get("market_id", ""),
        "question": market.get("question", ""),
        "probability": market.get("probability"),
        "volume_24h": market.get("volume_24h"),
        "liquidity": market.get("liquidity"),
        "status": market.get("status"),
        "end_date": market.get("end_date"),
        "url": market.get("url"),
    }


def _probability_pct(value: Any) -> float:
    probability = float(value)
    if 0.0 <= probability <= 1.0:
        return probability * 100.0
    return probability


def _sample_points(points: list[Any], cap: int = 30) -> list[dict[str, Any]]:
    valid = []
    for point in points:
        if not isinstance(point, dict):
            continue
        if "t" not in point or "p" not in point:
            continue
        valid.append({"t": point.get("t"), "p": point.get("p")})
    if len(valid) <= cap:
        return valid
    if cap <= 1:
        return valid[:cap]

    last_index = len(valid) - 1
    indexes = sorted({round(i * last_index / (cap - 1)) for i in range(cap)})
    return [valid[i] for i in indexes]


@mcp.tool()
def search_markets(query: str) -> dict[str, Any]:
    """Resolve a Polymarket event by URL, slug, or keywords."""
    try:
        slug = _query_to_slug(query)
        if not slug:
            return _error(SR_SOURCE_UNAVAILABLE, "Provide a Polymarket URL, event slug, or keywords.")

        event = resolve_event(slug)
        if not event.get("ok"):
            return _error(SR_SOURCE_UNAVAILABLE, str(event.get("error", "Polymarket event not found.")))

        return {
            "event_title": event.get("event_title", ""),
            "event_id": event.get("event_id", ""),
            "slug": event.get("slug", slug),
            "markets": [_market_summary(market) for market in event.get("markets", [])],
        }
    except Exception as exc:  # noqa: BLE001 - MCP tools must return structured errors.
        return _exception_error(exc, "Could not resolve Polymarket markets")


@mcp.tool()
def discover_markets(query: str = "", limit: int = DISCOVER_DEFAULT_LIMIT) -> dict[str, Any]:
    """Discover open Polymarket events by keyword search or trending browse.

    Empty query returns trending events (24h volume desc). Read-only and
    stateless: touches no SignalRadar watchlist, baselines, or config. Each
    result includes a polymarket.com URL that can be fed to SignalRadar's
    `add` flow.
    """
    try:
        results, error = discover_events(query=query, limit=limit)
        if error:
            return _error(error.get("code", SR_SOURCE_UNAVAILABLE), error.get("message", "Discover failed."))
        return {
            "query": (query or "").strip(),
            "results": results or [],
        }
    except Exception as exc:  # noqa: BLE001 - MCP tools must return structured errors.
        return _exception_error(exc, "Could not discover Polymarket markets")


@mcp.tool()
def get_market(market_id: str) -> dict[str, Any]:
    """Return the current read-only snapshot for one Polymarket market."""
    try:
        market, error = fetch_market_current_result(market_id)
        if error:
            return _error(error.get("code", SR_SOURCE_UNAVAILABLE), error.get("message", "Market fetch failed."))
        if not market:
            return _error(SR_SOURCE_UNAVAILABLE, "Polymarket API did not return market data.")
        return _market_snapshot(market)
    except Exception as exc:  # noqa: BLE001 - MCP tools must return structured errors.
        return _exception_error(exc, "Could not fetch current market data")


@mcp.tool()
def get_price_trend(market_id: str) -> dict[str, Any]:
    """Return 7-day CLOB trend stats plus a capped raw point sample."""
    try:
        market, error = fetch_market_current_result(market_id)
        if error:
            return _error(error.get("code", SR_SOURCE_UNAVAILABLE), error.get("message", "Market fetch failed."))
        if not market:
            return _error(SR_SOURCE_UNAVAILABLE, "Polymarket API did not return market data.")

        clob_token_id = str(market.get("clob_token_id") or "").strip()
        if not clob_token_id:
            return _error(SR_SOURCE_UNAVAILABLE, "Market does not expose a CLOB token id for price history.")

        points = fetch_price_history_points(clob_token_id)
        trend = summarize_trend(points)
        if trend is None:
            return _error(SR_SOURCE_UNAVAILABLE, "CLOB price history did not contain enough valid points.")

        return {
            "market_id": market.get("market_id", market_id),
            "clob_token_id": clob_token_id,
            "trend": trend,
            "sampled_points": _sample_points(points),
        }
    except Exception as exc:  # noqa: BLE001 - MCP tools must return structured errors.
        return _exception_error(exc, "Could not fetch price trend")


@mcp.tool()
def check_threshold(market_id: str, baseline_pct: float, threshold_pp: float) -> dict[str, Any]:
    """Preview current probability against a caller-provided baseline.

    This is stateless and read-only. It does not read, write, or update
    SignalRadar's stateful baselines, watchlist, audit log, or runtime config.
    """
    try:
        market, error = fetch_market_current_result(market_id)
        if error:
            return _error(error.get("code", SR_SOURCE_UNAVAILABLE), error.get("message", "Market fetch failed."))
        if not market:
            return _error(SR_SOURCE_UNAVAILABLE, "Polymarket API did not return market data.")

        current_pct = _probability_pct(market["probability"])
        delta_pp = current_pct - float(baseline_pct)
        abs_pp = abs(delta_pp)
        if delta_pp > 0:
            direction = "up"
        elif delta_pp < 0:
            direction = "down"
        else:
            direction = "flat"

        return {
            "market_id": market.get("market_id", market_id),
            "current_pct": round(current_pct, 2),
            "baseline_pct": float(baseline_pct),
            "threshold_pp": float(threshold_pp),
            "abs_pp": round(abs_pp, 2),
            "crossed": abs_pp >= float(threshold_pp),
            "direction": direction,
            "stateless": True,
            "note": "Preview only; does not touch SignalRadar stateful baselines.",
        }
    except Exception as exc:  # noqa: BLE001 - MCP tools must return structured errors.
        return _exception_error(exc, "Could not check threshold")


if __name__ == "__main__":
    mcp.run(transport="stdio")
