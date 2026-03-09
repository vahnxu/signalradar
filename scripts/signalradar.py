#!/usr/bin/env python3
"""SignalRadar v0.5.3 unified CLI entrypoint.

Commands: doctor, add, list, show, remove, run, config, schedule
Single source of truth: config/watchlist.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.9+ should have zoneinfo
    ZoneInfo = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Resolve paths before importing sibling modules (they use relative imports)
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from config_utils import (
    DEFAULT_CONFIG,
    add_entries,
    archive_entry,
    deep_merge,
    get_entry_by_number,
    get_nested_value,
    load_json_config,
    load_watchlist,
    save_json_config,
    save_watchlist,
    set_nested_value,
)
from decide_threshold import check_entry, safe_name
from discover_entries import (
    ONBOARDING_URLS,
    extract_probability,
    fetch_market_current_result,
    is_settled,
    normalize_market,
    parse_polymarket_url,
    resolve_event,
)
from route_delivery import deliver_hit, severity_for_event


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _workspace_root() -> Path:
    env = os.environ.get("SIGNALRADAR_WORKSPACE_ROOT", "").strip()
    if env:
        return Path(env)
    return SKILL_ROOT.parent.parent


def _watchlist_path() -> Path:
    return SKILL_ROOT / "config" / "watchlist.json"


def _config_path(override: str = "") -> Path:
    if override:
        return Path(override)
    return SKILL_ROOT / "config" / "signalradar_config.json"


def _baseline_dir() -> Path:
    return SKILL_ROOT / "cache" / "baselines"


def _audit_log_path() -> Path:
    return SKILL_ROOT / "cache" / "events" / "signal_events.jsonl"


def _last_run_path() -> Path:
    return SKILL_ROOT / "cache" / "last_run.json"


def _load_config(override: str = "") -> dict[str, Any]:
    user_cfg = load_json_config(_config_path(override))
    return deep_merge(DEFAULT_CONFIG, user_cfg)


def _save_config_key(override: str, key: str, value: Any) -> None:
    """Write a single key to the user config file."""
    cfg_path = _config_path(override)
    user_cfg = load_json_config(cfg_path)
    set_nested_value(user_cfg, key, value)
    save_json_config(cfg_path, user_cfg)


def _is_dynamic_config_key(key: str) -> bool:
    dynamic_prefixes = (
        "threshold.per_category_abs_pp.",
        "threshold.per_entry_abs_pp.",
        "delivery.primary.",
    )
    return any(key.startswith(prefix) for prefix in dynamic_prefixes)


def _config_key_exists(key: str, merged: dict[str, Any]) -> bool:
    found, _value = get_nested_value(merged, key)
    return found or _is_dynamic_config_key(key)


def _format_user_time(value: str, config: dict[str, Any]) -> str:
    if value in ("", "never", "unknown"):
        return value
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if ZoneInfo is None:
        return value
    timezone_name = str(config.get("profile", {}).get("timezone", "UTC") or "UTC")
    try:
        local_dt = dt.astimezone(ZoneInfo(timezone_name))
    except Exception:
        return value
    return f"{local_dt.strftime('%Y-%m-%d %H:%M:%S')} {timezone_name}"


def _parse_cli_value(raw_value: str) -> Any:
    lowered = raw_value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw_value)
    except ValueError:
        try:
            return float(raw_value)
        except ValueError:
            return raw_value


def _validate_config_value(key: str, value: Any) -> str | None:
    if key == "threshold.abs_pp" or key.startswith("threshold.per_category_abs_pp.") or key.startswith("threshold.per_entry_abs_pp."):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "Threshold must be a number."
        if numeric < 0.1:
            return "Minimum threshold is 0.1 percentage points."
    if key == "profile.timezone" and ZoneInfo is not None:
        try:
            ZoneInfo(str(value))
        except Exception:
            return f"Unknown timezone: {value}"
    return None


def _run_error(entry_id: str, code: str, message: str) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "code": code,
        "message": message,
        "error": message,
    }


def _build_observation(
    entry: dict[str, Any],
    *,
    state: str,
    decision: str,
    threshold: float | None = None,
    current_market: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "entry_id": entry.get("entry_id", ""),
        "question": entry.get("question", ""),
        "category": entry.get("category", "default"),
        "state": state,
        "decision": decision,
        "threshold_abs_pp": threshold,
        "url": entry.get("url", ""),
        "end_date": entry.get("end_date", ""),
    }
    if current_market is not None:
        observation["current"] = current_market.get("probability")
        observation["market_status"] = current_market.get("status", "unknown")
    if result is not None:
        observation["baseline"] = result.get("baseline")
        observation["abs_pp"] = result.get("abs_pp")
        if result.get("event") is not None:
            observation["reason"] = result["event"].get("reason", "")
    if error is not None:
        observation["error_code"] = error.get("code", "SR_SOURCE_UNAVAILABLE")
        observation["error_message"] = error.get("message", "Unknown error")
    return observation


def _find_entries_for_show(data: dict[str, Any], target: str) -> list[dict[str, Any]]:
    """Resolve show target by list number or case-insensitive text search."""
    entries = data.get("entries", [])
    if target.isdigit():
        entry = get_entry_by_number(data, int(target))
        return [entry] if entry is not None else []

    needle = target.strip().lower()
    matches: list[dict[str, Any]] = []
    for entry in entries:
        haystacks = [
            str(entry.get("question", "")).lower(),
            str(entry.get("slug", "")).lower(),
            str(entry.get("entry_id", "")).lower(),
            str(entry.get("category", "")).lower(),
        ]
        if any(needle in hay for hay in haystacks):
            matches.append(entry)
    return matches


def _classify_market_type(question: str) -> str:
    text = question.strip().lower()
    downside_patterns = (
        r"\bbelow\b",
        r"\bunder\b",
        r"\bless than\b",
        r"\bdrop below\b",
        r"\bfall below\b",
        r"\bfall to\b",
        r"\bat most\b",
    )
    upside_patterns = (
        r"\babove\b",
        r"\bover\b",
        r"\bgreater than\b",
        r"\bexceed\b",
        r"\breach\b",
        r"\bhit\b",
        r"\bat least\b",
    )
    if any(re.search(pattern, text) for pattern in downside_patterns):
        return "downside"
    if any(re.search(pattern, text) for pattern in upside_patterns):
        return "upside"
    return "other"


def _summarize_market_types(markets: list[dict[str, Any]]) -> str:
    counts = {"upside": 0, "downside": 0, "other": 0}
    for market in markets:
        counts[_classify_market_type(str(market.get("question", "")))] += 1
    parts: list[str] = []
    if counts["upside"]:
        parts.append(f"{counts['upside']} upside")
    if counts["downside"]:
        parts.append(f"{counts['downside']} downside")
    if counts["other"]:
        parts.append(f"{counts['other']} other")
    return ", ".join(parts) if parts else "no active markets"


def _print_market_preview(event_title: str, active_markets: list[dict[str, Any]], settled_markets: list[dict[str, Any]]) -> None:
    print(f"\n{event_title}")
    print(f"Active markets: {len(active_markets)}")
    if settled_markets:
        print(f"Settled markets skipped: {len(settled_markets)}")
    print(f"Type summary: {_summarize_market_types(active_markets)}")
    print("Markets to add:")
    for idx, market in enumerate(active_markets, 1):
        probability = market.get("probability")
        probability_text = f"{probability:.0f}%" if isinstance(probability, (int, float)) else "N/A"
        market_type = _classify_market_type(str(market.get("question", "")))
        print(f"  {idx}. [{market_type}] {market.get('question', '?')}  {probability_text}")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Scheduling helpers (crontab + openclaw cron)
# ---------------------------------------------------------------------------

_CRON_TAG = "# signalradar-auto"
_OPENCLAW_CRON_NAME = "SignalRadar Auto-Monitor"


def _cron_command_line() -> str:
    """Build the crontab command that runs SignalRadar."""
    return (
        f"cd {SKILL_ROOT} && python3 scripts/signalradar.py run --yes --output json "
        f">> cache/cron.log 2>&1  {_CRON_TAG}"
    )


def _has_crontab() -> bool:
    """Check if crontab command is available."""
    return shutil.which("crontab") is not None


def _read_crontab() -> str:
    """Read current crontab. Returns empty string if none."""
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return ""
        return result.stdout or ""
    except Exception:
        return ""


def _write_crontab(content: str) -> bool:
    """Write crontab from string content. Returns True on success."""
    try:
        fd, tmp = tempfile.mkstemp(suffix=".crontab", prefix="signalradar_")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            result = subprocess.run(
                ["crontab", tmp], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        return False


def _setup_cron(interval_minutes: int, driver: str = "crontab") -> tuple[bool, str]:
    """Set up auto-monitoring cron job. Returns (success, message)."""
    if driver == "crontab":
        if not _has_crontab():
            return False, (
                "Note: crontab not available in this environment.\n"
                "To enable auto-monitoring, either:\n"
                "  - Install crontab, then: signalradar.py schedule 10\n"
                "  - Use openclaw: signalradar.py schedule 10 --driver openclaw\n"
                "  - Run manually: signalradar.py run"
            )

        # Remove existing signalradar cron line, then add new one
        existing = _read_crontab()
        lines = [l for l in existing.splitlines() if _CRON_TAG not in l]
        new_line = f"*/{interval_minutes} * * * * {_cron_command_line()}"
        lines.append(new_line)
        # Ensure trailing newline
        content = "\n".join(lines).strip() + "\n"
        if _write_crontab(content):
            return True, f"Auto-monitoring enabled: every {interval_minutes} minutes (crontab)."
        return False, "Failed to write crontab."

    elif driver == "openclaw":
        cmd = [
            "openclaw", "cron", "add",
            "--name", _OPENCLAW_CRON_NAME,
            "--every", f"{interval_minutes}m",
            "--session", "isolated",
            "--message", (
                f"Run SignalRadar monitoring: cd {SKILL_ROOT} && "
                f"python3 scripts/signalradar.py run --yes --output json"
            ),
            "--no-deliver",
            "--json",
        ]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                try:
                    payload = json.loads(result.stdout)
                    if payload.get("ok"):
                        return True, f"Auto-monitoring enabled: every {interval_minutes} minutes (openclaw cron)."
                except json.JSONDecodeError:
                    pass
            stderr = (result.stderr or "").strip()
            return False, f"Failed to create openclaw cron job. {stderr}"
        except FileNotFoundError:
            return False, "openclaw command not found."
        except Exception as e:
            return False, f"Error creating openclaw cron: {e}"

    return False, f"Unknown driver: {driver}"


def _remove_cron() -> tuple[bool, str]:
    """Remove all signalradar cron jobs (both drivers). Returns (success, message)."""
    removed_any = False

    # Try crontab removal
    if _has_crontab():
        existing = _read_crontab()
        if _CRON_TAG in existing:
            lines = [l for l in existing.splitlines() if _CRON_TAG not in l]
            content = "\n".join(lines).strip()
            if content:
                content += "\n"
            else:
                # Empty crontab — remove entirely
                subprocess.run(
                    ["crontab", "-r"], capture_output=True, text=True, timeout=10
                )
                removed_any = True
                # Skip write since we removed
                content = ""
            if content:
                if _write_crontab(content):
                    removed_any = True
            elif not removed_any:
                removed_any = True  # nothing to write, crontab already cleared

    # Try openclaw cron removal
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout:
            jobs = json.loads(result.stdout)
            if isinstance(jobs, list):
                for job in jobs:
                    if "SignalRadar" in str(job.get("name", "")):
                        job_id = job.get("id", "")
                        if job_id:
                            subprocess.run(
                                ["openclaw", "cron", "delete", str(job_id)],
                                capture_output=True, text=True, timeout=15
                            )
                            removed_any = True
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass  # openclaw not available, skip

    if removed_any:
        return True, "Auto-monitoring disabled."
    return True, "No active auto-monitoring found."


def _check_cron_status() -> dict[str, Any]:
    """Check current cron scheduling status. Returns frozen-contract dict."""
    status: dict[str, Any] = {
        "enabled": False,
        "interval": 0,
        "driver": "none",
        "next_run": "unknown",
        "last_run": "never",
        "last_run_status": "unknown",
    }

    # Check last_run from cache
    last_run_file = _last_run_path()
    if last_run_file.exists():
        try:
            lr = json.loads(last_run_file.read_text(encoding="utf-8"))
            status["last_run"] = lr.get("ts", "never")
            status["last_run_status"] = lr.get("status", "unknown")
        except Exception:
            pass

    # Check crontab
    if _has_crontab():
        existing = _read_crontab()
        for line in existing.splitlines():
            if _CRON_TAG in line and not line.strip().startswith("#"):
                status["enabled"] = True
                status["driver"] = "crontab"
                # Parse interval from */N pattern
                parts = line.strip().split()
                if parts and parts[0].startswith("*/"):
                    try:
                        status["interval"] = int(parts[0][2:])
                    except ValueError:
                        pass
                status["next_run"] = "unknown"
                return status

    # Check openclaw cron
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout:
            jobs = json.loads(result.stdout)
            if isinstance(jobs, list):
                for job in jobs:
                    if "SignalRadar" in str(job.get("name", "")):
                        status["enabled"] = True
                        status["driver"] = "openclaw"
                        # Parse interval from every field
                        every = str(job.get("every", ""))
                        if every.endswith("m"):
                            try:
                                status["interval"] = int(every[:-1])
                            except ValueError:
                                pass
                        next_run = job.get("next_run")
                        status["next_run"] = next_run if next_run else "unknown"
                        return status
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        pass

    return status


def _ensure_auto_monitoring(interval: int = 10, config_override: str = "") -> None:
    """Check if cron exists; if not, set it up. Idempotent."""
    cron_status = _check_cron_status()
    if cron_status["enabled"]:
        return  # already running, skip

    ok, msg = _setup_cron(interval)
    print(f"\n{msg}")
    if ok:
        print(f"To change frequency: signalradar.py schedule 30")
        print(f"To disable: signalradar.py schedule disable")
        # Sync check_interval_minutes to config
        _save_config_key(config_override, "check_interval_minutes", interval)


# ---------------------------------------------------------------------------
# cmd_doctor
# ---------------------------------------------------------------------------

def cmd_doctor(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    check("skill_root_exists", SKILL_ROOT.exists(), str(SKILL_ROOT))
    wl_path = _watchlist_path()
    if not wl_path.exists():
        check("watchlist_loadable", True, f"not yet created: {wl_path}")
    else:
        # Try strict JSON parse first to detect corruption
        try:
            raw = json.loads(wl_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                check("watchlist_loadable", False, f"watchlist is not a JSON object: {wl_path}")
            elif not isinstance(raw.get("entries"), list):
                check("watchlist_loadable", False, f"watchlist.entries missing or not a list: {wl_path}")
            elif not isinstance(raw.get("archived", []), list):
                check("watchlist_loadable", False, f"watchlist.archived is not a list: {wl_path}")
            else:
                check("watchlist_loadable", True, str(wl_path))
                check("watchlist_entries", True, f"{len(raw.get('entries', []))} entries")
        except (json.JSONDecodeError, ValueError) as e:
            check("watchlist_corrupted", False, f"JSON parse error: {e} — file: {wl_path}")

    cfg_path = _config_path(args.config)
    check("config_exists_optional", True, str(cfg_path) if cfg_path.exists() else f"missing(optional): {cfg_path}")
    cache_dir = SKILL_ROOT / "cache"
    check("cache_dir_writable", cache_dir.exists() or SKILL_ROOT.exists(), str(cache_dir))

    interval = config.get("check_interval_minutes", 10)
    ok = all(item["ok"] for item in checks)
    payload: dict[str, Any] = {
        "status": "HEALTHY" if ok else "WARN",
        "check_interval_minutes": interval,
        "checks": checks,
    }

    if args.output == "json":
        _json_print(payload)
    else:
        if ok:
            print(f"HEALTHY — check_interval_minutes={interval}")
        else:
            print("WARN")
            for item in checks:
                if not item["ok"]:
                    print(f"  - {item['name']}: {item['detail']}")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> int:
    url = args.url

    # No URL provided
    if not url:
        wl = load_watchlist(_watchlist_path())
        if not wl.get("entries"):
            # Empty watchlist + no URL → onboarding
            return _onboarding(args)
        else:
            print("Usage: signalradar.py add <polymarket-event-url>")
            print("       signalradar.py add  (guided setup, first time only)")
            return 1

    slug = parse_polymarket_url(url)
    if not slug:
        print(f"Error: Cannot parse Polymarket event URL: {url}")
        return 1

    result = resolve_event(slug)
    if not result["ok"]:
        print(f"Error: {result['error']}")
        return 1

    event_title = result["event_title"]
    markets = result["markets"]
    event_id = result["event_id"]

    if not markets:
        print(f"No markets found for event '{event_title}'.")
        return 1

    # Check for settled markets
    settled_markets = [m for m in markets if is_settled(m)]
    active_markets = [m for m in markets if not is_settled(m)]

    if settled_markets and not active_markets:
        print(f"Warning: All {len(markets)} markets in '{event_title}' are settled.")
        if not args.yes:
            answer = input("Add anyway? (y/N): ").strip().lower()
            if answer not in ("y", "yes"):
                print("Cancelled.")
                return 0

    # Multi-market events: always preview before write. Large batches require
    # interactive confirmation even if --yes was passed.
    if len(active_markets) > 3:
        _print_market_preview(event_title, active_markets, settled_markets)
        if args.yes:
            print("\nError: bulk add (>3 markets) requires interactive confirmation.")
            print("Re-run without --yes after reviewing the market preview above.")
            return 1
        answer = input(f"Confirm adding all {len(active_markets)} markets? (Y/n): ").strip().lower()
        if answer in ("n", "no"):
            print("Cancelled.")
            return 0
    elif len(active_markets) > 1:
        _print_market_preview(event_title, active_markets, settled_markets)
        if not args.yes:
            answer = input(f"Add all {len(active_markets)} markets? (Y/n): ").strip().lower()
            if answer in ("n", "no"):
                print("Cancelled.")
                return 0

    elif len(active_markets) == 1:
        m = active_markets[0]
        print(f"\n{m['question']}  {m['probability']:.0f}%")
        if not args.yes:
            answer = input("Add this market? (Y/n): ").strip().lower()
            if answer in ("n", "no"):
                print("Cancelled.")
                return 0
    else:
        # Only settled markets but user confirmed above
        active_markets = markets

    # Check if watchlist was empty before this add
    wl_path = _watchlist_path()
    wl_before = load_watchlist(wl_path)
    was_empty = not wl_before.get("entries")

    # Build watchlist entries
    category = args.category or "default"
    now = _utc_now()
    new_entries = []
    for m in active_markets:
        new_entries.append({
            "entry_id": m["entry_id"],
            "slug": m["slug"],
            "question": m["question"],
            "category": category,
            "url": m["url"],
            "end_date": m.get("end_date", ""),
            "added_at": now,
        })

    added, skipped = add_entries(wl_path, new_entries)

    # Record baselines for newly added entries
    baseline_dir = _baseline_dir()
    for entry in added:
        # Find the market data to get probability
        for m in active_markets:
            if m["entry_id"] == entry["entry_id"]:
                check_entry(
                    entry_id=entry["entry_id"],
                    question=entry["question"],
                    current_prob=m["probability"],
                    baseline_dir=baseline_dir,
                    threshold_abs_pp=5.0,
                    dry_run=False,
                )
                break

    # Show results
    if added:
        print(f"\nAdded {len(added)} market(s):")
        for entry in added:
            prob = ""
            for m in active_markets:
                if m["entry_id"] == entry["entry_id"]:
                    prob = f"  {m['probability']:.0f}% (baseline)"
                    break
            print(f"  {entry['question']}{prob}")

    if skipped:
        print(f"\nSkipped {len(skipped)} (already in watchlist):")
        for entry in skipped:
            print(f"  {entry['question']}")

    # Auto-monitoring: enable on first add (watchlist was empty)
    if added and was_empty:
        _ensure_auto_monitoring(interval=10, config_override=getattr(args, "config", ""))

    return 0


# ---------------------------------------------------------------------------
# cmd_config
# ---------------------------------------------------------------------------

def cmd_config(args: argparse.Namespace) -> int:
    cfg_path = _config_path(args.config)
    user_cfg = load_json_config(cfg_path)
    merged = deep_merge(DEFAULT_CONFIG, user_cfg)

    # No key specified: show current config
    if not args.key:
        if args.output == "json":
            _json_print(merged)
        else:
            print("Current config:\n")
            for k, v in sorted(merged.items()):
                if isinstance(v, dict):
                    print(f"  {k}:")
                    for k2, v2 in sorted(v.items()):
                        print(f"    {k2}: {v2}")
                else:
                    print(f"  {k}: {v}")
            print(f"\nConfig file: {cfg_path}")
        return 0

    key = args.key

    # No value specified: show current value for that key
    if args.value is None:
        found, value = get_nested_value(merged, key)
        if not found:
            print(f"Unknown key: {key}")
            return 1
        if isinstance(value, (dict, list)):
            print(json.dumps(value, ensure_ascii=False, indent=2))
        else:
            print(f"{key}: {value}")
        return 0

    if not _config_key_exists(key, merged):
        print(f"Unknown key: {key}")
        return 1

    parsed_value = _parse_cli_value(args.value)
    validation_error = _validate_config_value(key, parsed_value)
    if validation_error:
        print(f"Error: {validation_error}")
        return 1

    set_nested_value(user_cfg, key, parsed_value)
    save_json_config(cfg_path, user_cfg)

    print(f"Set {key} = {parsed_value}")
    print(f"Saved to {cfg_path}")
    if key == "check_interval_minutes":
        print("Note: this updates the display value only. Use 'signalradar.py schedule N' to change actual monitoring frequency.")
    return 0


# ---------------------------------------------------------------------------
# cmd_schedule
# ---------------------------------------------------------------------------

def cmd_schedule(args: argparse.Namespace) -> int:
    action = args.action
    config = _load_config(getattr(args, "config", ""))

    # No argument: show current status
    if not action:
        status = _check_cron_status()
        if args.output == "json":
            _json_print(status)
        else:
            if status["enabled"]:
                print(f"Auto-monitoring: enabled")
                print(f"  Interval: every {status['interval']} minutes")
                print(f"  Driver: {status['driver']}")
                print(f"  Next run: {_format_user_time(status['next_run'], config)}")
                print(f"  Last run: {_format_user_time(status['last_run'], config)}")
                print(f"  Last status: {status['last_run_status']}")
            else:
                print("Auto-monitoring: disabled")
                if status["last_run"] != "never":
                    print(f"  Last run: {_format_user_time(status['last_run'], config)}")
                    print(f"  Last status: {status['last_run_status']}")
                print("\nTo enable: signalradar.py schedule 10")
        return 0

    # Disable
    if action == "disable":
        ok, msg = _remove_cron()
        print(msg)
        return 0 if ok else 1

    # Numeric interval
    try:
        interval = int(action)
    except ValueError:
        print(f"Error: Invalid argument '{action}'. Use a number (minutes) or 'disable'.")
        return 1

    if interval < 5:
        print("Minimum interval is 5 minutes (prevents overlapping runs).")
        return 1

    driver = args.driver

    # Remove existing first (any driver), then set up new
    _remove_cron()

    ok, msg = _setup_cron(interval, driver=driver)
    print(msg)

    if ok:
        # Sync check_interval_minutes to config
        config_override = getattr(args, "config", "")
        _save_config_key(config_override, "check_interval_minutes", interval)
        print(f"To change: signalradar.py schedule {interval}")
        print(f"To disable: signalradar.py schedule disable")

    return 0 if ok else 1


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    wl = load_watchlist(_watchlist_path())

    if args.archived:
        archived = wl.get("archived", [])
        if not archived:
            print("No archived entries.")
            return 0
        print(f"Archived entries ({len(archived)}):\n")
        for i, entry in enumerate(archived, 1):
            reason = entry.get("archive_reason", "unknown")
            archived_at = entry.get("archived_at", "")[:10]
            print(f"  {i}. {entry.get('question', entry.get('entry_id', '?'))}")
            print(f"     Reason: {reason}  Archived: {archived_at}")
        return 0

    entries = wl.get("entries", [])
    if not entries:
        print("Watchlist is empty. Use 'signalradar.py add <url>' to add markets.")
        return 0

    # Group by category
    by_category: dict[str, list[tuple[int, dict]]] = {}
    for i, entry in enumerate(entries, 1):
        cat = entry.get("category", "default")
        if args.category and cat != args.category:
            continue
        by_category.setdefault(cat, []).append((i, entry))

    if not by_category:
        print(f"No entries in category '{args.category}'.")
        return 0

    total = sum(len(v) for v in by_category.values())
    print(f"Watchlist ({total} entries):\n")
    for cat in sorted(by_category.keys()):
        print(f"  [{cat}]")
        for num, entry in by_category[cat]:
            q = entry.get("question", entry.get("entry_id", "?"))
            end = entry.get("end_date", "")
            print(f"    {num}. {q}" + (f"  (ends {end})" if end else ""))
        print()

    return 0


# ---------------------------------------------------------------------------
# cmd_show
# ---------------------------------------------------------------------------

def cmd_show(args: argparse.Namespace) -> int:
    wl = load_watchlist(_watchlist_path())
    entries = wl.get("entries", [])

    if not entries:
        if args.output == "json":
            _json_print({
                "status": "NO_REPLY",
                "request_id": str(uuid.uuid4()),
                "ts": _utc_now(),
                "matches": [],
                "errors": [],
                "message": "Watchlist is empty",
            })
        else:
            print("No monitored markets yet. Add one with: signalradar.py add <url>")
        return 0

    matches = _find_entries_for_show(wl, args.target)
    if not matches:
        if args.output == "json":
            _json_print({
                "status": "NO_REPLY",
                "request_id": str(uuid.uuid4()),
                "ts": _utc_now(),
                "matches": [],
                "errors": [],
                "message": f"No monitored market matched '{args.target}'",
            })
        else:
            print(f"No monitored market matched '{args.target}'.")
            print("Tip: use a list number from 'signalradar.py list' or a keyword from the market question.")
        return 1

    request_id = str(uuid.uuid4())
    run_ts = _utc_now()
    config = _load_config(getattr(args, "config", ""))
    payload_matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for entry in matches:
        entry_id = str(entry.get("entry_id", ""))
        market_id = entry_id.split(":")[1] if ":" in entry_id else ""
        if not market_id:
            errors.append(_run_error(entry_id, "SR_VALIDATION_ERROR", "Entry ID format is invalid."))
            continue

        current_market, fetch_error = fetch_market_current_result(market_id)
        if current_market is None:
            if is_settled(entry):
                payload_matches.append(
                    _build_observation(
                        entry,
                        state="settled",
                        decision="SETTLED",
                    )
                )
                continue
            errors.append(
                _run_error(
                    entry_id,
                    fetch_error.get("code", "SR_SOURCE_UNAVAILABLE") if fetch_error else "SR_SOURCE_UNAVAILABLE",
                    fetch_error.get("message", "Could not fetch current market data from Polymarket API.") if fetch_error else "Could not fetch current market data from Polymarket API.",
                )
            )
            continue

        payload_matches.append(
            _build_observation(
                entry,
                state="settled" if is_settled(current_market) else "checked",
                decision="SETTLED" if is_settled(current_market) else "SNAPSHOT",
                current_market=current_market,
            )
        )

    status = "ERROR" if errors and not payload_matches else "OK"
    if args.output == "json":
        _json_print({
            "status": status,
            "request_id": request_id,
            "ts": run_ts,
            "matches": payload_matches,
            "errors": errors,
        })
        return 0 if status != "ERROR" else 1

    print(f"Matched {len(payload_matches)} monitored market(s):\n")
    for item in payload_matches:
        print(f"  {item.get('question', item.get('entry_id', '?'))}")
        if item.get("state") == "settled":
            print("    Market appears settled. No new alerts will fire.")
        else:
            print(f"    Current probability: {item.get('current')}%")
        if item.get("category"):
            print(f"    Category: {item.get('category')}")
        if item.get("url"):
            print(f"    URL: {item.get('url')}")
        print()

    if errors:
        print(f"Could not fetch {len(errors)} matched market(s):")
        for error in errors:
            print(f"  {error.get('entry_id', 'unknown')}: {error.get('message', 'Unknown error')} ({error.get('code', 'SR_SOURCE_UNAVAILABLE')})")

    if payload_matches:
        print(f"Snapshot time: {_format_user_time(run_ts, config)}")

    return 0 if status != "ERROR" else 1


# ---------------------------------------------------------------------------
# cmd_remove
# ---------------------------------------------------------------------------

def cmd_remove(args: argparse.Namespace) -> int:
    wl = load_watchlist(_watchlist_path())
    entry = get_entry_by_number(wl, args.number)

    if entry is None:
        print(f"Error: No entry #{args.number}. Use 'signalradar.py list' to see entries.")
        return 1

    question = entry.get("question", entry.get("entry_id", "?"))
    print(f"\nRemoving #{args.number}: {question}")

    if not args.yes:
        answer = input("Confirm removal? (y/N): ").strip().lower()
        if answer not in ("y", "yes"):
            print("Cancelled.")
            return 0

    # Collect baseline history before archiving
    entry_id = entry.get("entry_id", "")
    baseline_dir = _baseline_dir()
    baseline_file = baseline_dir / f"{safe_name(entry_id)}.json"
    baseline_history = []
    if baseline_file.exists():
        try:
            bl = json.loads(baseline_file.read_text(encoding="utf-8"))
            baseline_history.append({
                "value": bl.get("baseline"),
                "ts": bl.get("baseline_ts"),
            })
        except Exception:
            pass

    archived = archive_entry(
        _watchlist_path(),
        entry_id,
        reason="user_removed",
        baseline_history=baseline_history if baseline_history else None,
    )

    if archived:
        print(f"Archived: {question}")
    else:
        print("Error: Entry not found during archive.")
        return 1

    return 0


# ---------------------------------------------------------------------------
# cmd_run
# ---------------------------------------------------------------------------

def _write_last_run(status: str, checked: int, hits_count: int) -> None:
    """Write cache/last_run.json after each run."""
    lr_path = _last_run_path()
    lr_path.parent.mkdir(parents=True, exist_ok=True)
    lr_data = {
        "ts": _utc_now(),
        "status": status,
        "checked": checked,
        "hits": hits_count,
    }
    lr_path.write_text(
        json.dumps(lr_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def cmd_run(args: argparse.Namespace) -> int:
    wl = load_watchlist(_watchlist_path())
    entries = wl.get("entries", [])
    config = _load_config(args.config)

    # Empty watchlist handling
    if not entries:
        if args.yes:
            # --yes mode: no onboarding, just report empty
            if args.output == "json":
                _json_print({
                    "status": "NO_REPLY",
                    "request_id": str(uuid.uuid4()),
                    "ts": _utc_now(),
                    "hits": [],
                    "errors": [],
                    "observations": [],
                    "message": "Watchlist is empty",
                })
            else:
                print("Watchlist is empty. Use 'signalradar.py add <url>' to add markets.")
            return 0
        else:
            # Interactive mode: trigger onboarding
            return _onboarding(args)

    # Normal run: check each entry
    threshold_cfg = config.get("threshold", {})
    default_threshold = float(threshold_cfg.get("abs_pp", 5.0))
    per_entry_thresholds = threshold_cfg.get("per_entry_abs_pp", {})
    per_category_thresholds = threshold_cfg.get("per_category_abs_pp", {})

    baseline_dir = _baseline_dir()
    audit_log = _audit_log_path()

    request_id = str(uuid.uuid4())
    run_ts = _utc_now()
    hits: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    settled_entries: list[dict[str, Any]] = []
    checked = 0

    for entry in entries:
        entry_id = entry.get("entry_id", "")
        question = entry.get("question", "")
        category = entry.get("category", "default")

        # Fetch current market state
        market_id = entry_id.split(":")[1] if ":" in entry_id else ""
        if not market_id:
            err = _run_error(entry_id, "SR_VALIDATION_ERROR", "Entry ID format is invalid.")
            errors.append(err)
            observations.append(
                _build_observation(
                    entry,
                    state="error",
                    decision="ERROR",
                    error=err,
                )
            )
            continue

        current_market, fetch_error = fetch_market_current_result(market_id)
        if current_market is None:
            # API failure — check end_date as fallback for settled
            if is_settled(entry):
                settled_entries.append(entry)
                observations.append(
                    _build_observation(
                        entry,
                        state="settled",
                        decision="SETTLED",
                    )
                )
                continue
            err = _run_error(
                entry_id,
                fetch_error.get("code", "SR_SOURCE_UNAVAILABLE") if fetch_error else "SR_SOURCE_UNAVAILABLE",
                fetch_error.get("message", "Could not fetch current market data from Polymarket API.") if fetch_error else "Could not fetch current market data from Polymarket API.",
            )
            errors.append(err)
            observations.append(
                _build_observation(
                    entry,
                    state="error",
                    decision="ERROR",
                    error=err,
                )
            )
            continue

        # Settled detection: API status priority
        if is_settled(current_market):
            settled_entries.append(entry)
            observations.append(
                _build_observation(
                    entry,
                    state="settled",
                    decision="SETTLED",
                    current_market=current_market,
                )
            )
            continue

        current_prob = current_market.get("probability")
        if current_prob is None:
            err = _run_error(
                entry_id,
                "SR_VALIDATION_ERROR",
                "Polymarket API returned market data without a probability value.",
            )
            errors.append(err)
            observations.append(
                _build_observation(
                    entry,
                    state="error",
                    decision="ERROR",
                    current_market=current_market,
                    error=err,
                )
            )
            continue

        # Resolve threshold: per_entry > per_category > default
        threshold = default_threshold
        if entry_id in per_entry_thresholds:
            try:
                threshold = float(per_entry_thresholds[entry_id])
            except (TypeError, ValueError):
                pass
        elif category in per_category_thresholds:
            try:
                threshold = float(per_category_thresholds[category])
            except (TypeError, ValueError):
                pass

        result = check_entry(
            entry_id=entry_id,
            question=question,
            current_prob=current_prob,
            baseline_dir=baseline_dir,
            threshold_abs_pp=threshold,
            dry_run=args.dry_run,
            audit_log_path=audit_log,
        )
        checked += 1
        observations.append(
            _build_observation(
                entry,
                state="checked",
                decision=result["decision"],
                threshold=threshold,
                current_market=current_market,
                result=result,
            )
        )

        if result["decision"] == "HIT" and result["event"] is not None:
            hits.append(result["event"])
            # Deliver
            if not args.dry_run:
                deliver_hit(result["event"], config, dry_run=False)

    # Determine overall status
    if errors and not hits:
        status = "ERROR"
    elif hits:
        status = "HIT"
    else:
        status = "NO_REPLY"

    # Write last_run.json (not on dry-run)
    if not args.dry_run:
        _write_last_run(status, checked, len(hits))

    # Output
    if args.output == "json":
        payload: dict[str, Any] = {
            "status": status,
            "request_id": request_id,
            "ts": run_ts,
            "hits": hits,
            "errors": errors,
            "checked_count": checked,
            "settled_count": len(settled_entries),
            "observations": observations,
        }
        _json_print(payload)
    else:
        if hits:
            print(f"Detected {len(hits)} market change(s) above your threshold:\n")
            for h in hits:
                print(f"  {h.get('question', h.get('entry_id'))}")
                print(f"    {h.get('baseline')}% → {h.get('current')}%  ({h.get('abs_pp')}pp)")
                print(f"    Baseline updated to {h.get('current')}%")
                print()
        else:
            print(f"Checked {checked} monitored market(s). No changes exceeded the threshold.")

        if errors:
            print(f"\nCould not check {len(errors)} market(s):")
            for e in errors:
                label = e.get("entry_id", "unknown")
                code = e.get("code", "SR_SOURCE_UNAVAILABLE")
                print(f"  {label}: {e.get('message', e.get('error', 'Unknown error'))} ({code})")

        if settled_entries:
            print(f"\n{len(settled_entries)} monitored market(s) appear settled and will not trigger new alerts:")
            for e in settled_entries:
                print(f"  {e.get('question', e.get('entry_id', '?'))}")

    return 0 if status != "ERROR" else 1


# ---------------------------------------------------------------------------
# Onboarding: 3-step code-enforced flow
# ---------------------------------------------------------------------------

def _onboarding(args: argparse.Namespace) -> int:
    """First-time setup with 6 preset events. 3-step interactive flow."""

    print("Welcome to SignalRadar! Loading popular events...\n")

    # Resolve all preset URLs
    events_data: list[dict[str, Any]] = []
    for url in ONBOARDING_URLS:
        slug = parse_polymarket_url(url)
        if not slug:
            continue
        result = resolve_event(slug)
        if result["ok"]:
            markets = [m for m in result["markets"] if not is_settled(m)]
            events_data.append({
                "title": result["event_title"],
                "slug": result["slug"],
                "event_id": result["event_id"],
                "markets": markets,
                "url": url,
            })
        else:
            events_data.append({
                "title": slug.replace("-", " ").title(),
                "slug": slug,
                "event_id": "",
                "markets": [],
                "url": url,
                "unavailable": True,
            })

    if not events_data:
        print("Error: Could not load any preset events. Check network connection.")
        return 1

    # --- STEP 1: Show event titles + market counts ---
    print(f"Found {len(events_data)} events:\n")
    for i, ev in enumerate(events_data, 1):
        market_count = len(ev["markets"])
        unavail = " (unavailable)" if ev.get("unavailable") else ""
        suffix = f"({market_count} market{'s' if market_count != 1 else ''})"
        print(f"  {i}. {ev['title']}  {suffix}{unavail}")

    print()
    user_input = input("Enter numbers to REMOVE (e.g. 1,5), or press Enter to keep all: ").strip()

    # Parse removal choices
    remove_set: set[int] = set()
    if user_input:
        for part in user_input.replace(" ", ",").split(","):
            part = part.strip()
            if part.isdigit():
                remove_set.add(int(part))

    # Filter events
    kept_events = []
    for i, ev in enumerate(events_data, 1):
        if i not in remove_set and not ev.get("unavailable") and ev["markets"]:
            kept_events.append(ev)

    if not kept_events:
        print("\nNo events selected. You can add markets later with: signalradar.py add <url>")
        return 0

    # --- STEP 2: Show sub-market details, confirm ---
    total_markets = sum(len(ev["markets"]) for ev in kept_events)
    print(f"\nAdding {len(kept_events)} events ({total_markets} markets):\n")

    # Group by inferred category
    num = 0
    for ev in kept_events:
        for m in ev["markets"]:
            num += 1
            print(f"  {num}. {m['question']}  {m['probability']:.0f}%")
    print()

    answer = input(f"Confirm adding {total_markets} markets? (Y/n): ").strip().lower()
    if answer in ("n", "no"):
        print("Cancelled. You can add markets later with: signalradar.py add <url>")
        return 0

    # --- STEP 3: Add entries + show results ---
    now = _utc_now()
    wl_path = _watchlist_path()
    baseline_dir = _baseline_dir()
    all_new_entries = []

    for ev in kept_events:
        category = _infer_category(ev["title"])
        for m in ev["markets"]:
            entry = {
                "entry_id": m["entry_id"],
                "slug": m["slug"],
                "question": m["question"],
                "category": category,
                "url": m["url"],
                "end_date": m.get("end_date", ""),
                "added_at": now,
            }
            all_new_entries.append((entry, m["probability"]))

    entries_to_add = [e for e, _ in all_new_entries]
    added, skipped = add_entries(wl_path, entries_to_add)

    # Record baselines
    for entry, prob in all_new_entries:
        if entry in added:
            check_entry(
                entry_id=entry["entry_id"],
                question=entry["question"],
                current_prob=prob,
                baseline_dir=baseline_dir,
                threshold_abs_pp=5.0,
                dry_run=False,
            )

    print(f"\nDone! {len(added)} markets added, baselines recorded.")
    if skipped:
        print(f"({len(skipped)} already in watchlist, skipped)")
    print("Remove any you don't need with: signalradar.py remove <number>")

    print(
        "\nWhat is a baseline?\n"
        "A baseline is the \"last known probability\" SignalRadar records. When probability\n"
        "changes by more than the threshold (default 5pp) and a notification is sent,\n"
        "the baseline updates to the new value. Example:\n"
        "  baseline 7% -> probability rises to 15% -> alert sent -> baseline updates to 15%\n"
        "  Next alert requires another 5pp change from 15%."
    )

    # Auto-monitoring: enable after successful onboarding
    if added:
        _ensure_auto_monitoring(interval=10, config_override=getattr(args, "config", ""))

    return 0


def _infer_category(title: str) -> str:
    """Simple keyword-based category for onboarding events."""
    lower = title.lower()
    ai_keywords = ["gpt", "claude", "ai", "model", "llm", "openai", "anthropic", "gemini", "grok"]
    crypto_keywords = ["bitcoin", "btc", "ethereum", "eth", "crypto", "token"]
    if any(k in lower for k in ai_keywords):
        return "AI"
    if any(k in lower for k in crypto_keywords):
        return "crypto"
    return "default"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _normalize_argv(argv: list[str]) -> list[str]:
    """Allow --yes/-y and --config before or after subcommand.

    Moves global flags that appear before the subcommand to after it,
    so argparse subparsers can parse them correctly.
    """
    commands = {"doctor", "add", "list", "show", "remove", "run", "config", "schedule"}
    # Find subcommand position
    cmd_idx = None
    for i, arg in enumerate(argv):
        if arg in commands:
            cmd_idx = i
            break
    if cmd_idx is None:
        return argv  # no subcommand found, let argparse handle the error

    # Move --yes/-y/--config from before subcommand to after
    before = argv[:cmd_idx]
    after = argv[cmd_idx:]
    relocated = []
    remaining = []
    skip_next = False
    for i, arg in enumerate(before):
        if skip_next:
            skip_next = False
            continue
        if arg in ("--yes", "-y"):
            relocated.append(arg)
        elif arg == "--config":
            relocated.append(arg)
            if i + 1 < len(before):
                relocated.append(before[i + 1])
                skip_next = True
        else:
            remaining.append(arg)
    # Insert relocated flags after the subcommand name
    return remaining + [after[0]] + relocated + after[1:]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SignalRadar v0.5.3 — Polymarket probability monitor"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # doctor
    p_doc = sub.add_parser("doctor", help="Check runtime health")
    p_doc.add_argument("--output", choices=["text", "json"], default="text")
    p_doc.add_argument("--config", default="", help="Path to config JSON")

    # add
    p_add = sub.add_parser("add", help="Add market(s) by Polymarket URL")
    p_add.add_argument("url", nargs="?", default="", help="Polymarket event URL (omit for guided setup)")
    p_add.add_argument("--category", default="", help="Category for the entries")
    p_add.add_argument("--yes", "-y", action="store_true", default=False, help="Skip confirmation")
    p_add.add_argument("--config", default="", help="Path to config JSON")

    # list
    p_list = sub.add_parser("list", help="List watchlist entries")
    p_list.add_argument("--category", default="", help="Filter by category")
    p_list.add_argument("--archived", action="store_true", help="Show archived entries")

    # show
    p_show = sub.add_parser("show", help="Show current probability for one monitored market")
    p_show.add_argument("target", help="List number or keyword to match a monitored market")
    p_show.add_argument("--output", choices=["text", "json"], default="text")
    p_show.add_argument("--config", default="", help="Path to config JSON")

    # remove
    p_rm = sub.add_parser("remove", help="Remove entry by number")
    p_rm.add_argument("number", type=int, help="Entry number from 'list'")
    p_rm.add_argument("--yes", "-y", action="store_true", default=False, help="Skip confirmation")

    # config
    p_cfg = sub.add_parser("config", help="View or change settings")
    p_cfg.add_argument("key", nargs="?", default="", help="Setting name (e.g. check_interval_minutes)")
    p_cfg.add_argument("value", nargs="?", default=None, help="New value")
    p_cfg.add_argument("--output", choices=["text", "json"], default="text")
    p_cfg.add_argument("--config", default="", help="Path to config JSON")

    # schedule
    p_sched = sub.add_parser("schedule", help="Manage auto-monitoring schedule")
    p_sched.add_argument("action", nargs="?", default="", help="Interval in minutes, or 'disable'")
    p_sched.add_argument("--driver", choices=["crontab", "openclaw"], default="crontab",
                         help="Scheduling driver (default: crontab)")
    p_sched.add_argument("--output", choices=["text", "json"], default="text")
    p_sched.add_argument("--config", default="", help="Path to config JSON")

    # run
    p_run = sub.add_parser("run", help="Check all entries for probability changes")
    p_run.add_argument("--dry-run", action="store_true", help="No side effects")
    p_run.add_argument("--output", choices=["text", "json"], default="text")
    p_run.add_argument("--yes", "-y", action="store_true", default=False, help="Skip confirmation")
    p_run.add_argument("--config", default="", help="Path to config JSON")

    args = parser.parse_args(_normalize_argv(sys.argv[1:]))

    # Dispatch
    cmd = args.command
    if cmd == "doctor":
        return cmd_doctor(args)
    elif cmd == "add":
        return cmd_add(args)
    elif cmd == "list":
        return cmd_list(args)
    elif cmd == "show":
        return cmd_show(args)
    elif cmd == "remove":
        return cmd_remove(args)
    elif cmd == "config":
        return cmd_config(args)
    elif cmd == "schedule":
        return cmd_schedule(args)
    elif cmd == "run":
        return cmd_run(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
