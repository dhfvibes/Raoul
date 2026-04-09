"""
tools.py — Raoul's NYC Open Data integrations

Data sources:
- NYC DOT Parking Regulation Locations and Signs
  https://data.cityofnewyork.us/Transportation/Parking-Regulation-Locations-and-Signs/xswq-wnv9
- NYC DOT Alternate Side Parking suspension page
  https://www.nyc.gov/html/dot/html/motorist/alternate-side-parking.shtml
- NYC 311 Service Requests (for context on common complaint types)
"""

import json
import requests
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional

NYC_TZ = ZoneInfo("America/New_York")

# ─────────────────────────────────────────────
# Tool 1: Current context (time, day, ASP)
# ─────────────────────────────────────────────

def get_current_context() -> dict:
    """Return the current NYC date, time, day of week, and ASP status."""
    now = datetime.now(NYC_TZ)
    asp_status = _asp_status_for_date(now.date())

    return {
        "date": now.strftime("%A, %B %d, %Y"),
        "time": now.strftime("%I:%M %p"),
        "day_of_week": now.strftime("%A"),
        "is_weekend": now.weekday() >= 5,
        "is_sunday": now.weekday() == 6,
        "timestamp_iso": now.isoformat(),
        "asp_suspended_today": asp_status["is_suspended"],
        "asp_suspension_reason": asp_status.get("reason", ""),
        "note": "All times are New York City time (Eastern).",
    }


# ─────────────────────────────────────────────
# Tool 2: ASP suspension check
# ─────────────────────────────────────────────

def check_asp_suspension(date_str: Optional[str] = None) -> dict:
    """
    Check whether Alternate Side Parking (ASP) is suspended on a given date.
    Defaults to today. date_str should be YYYY-MM-DD.
    """
    if date_str:
        try:
            check_date = date.fromisoformat(date_str)
        except ValueError:
            return {"error": f"Invalid date format: {date_str}. Use YYYY-MM-DD."}
    else:
        check_date = datetime.now(NYC_TZ).date()

    result = _asp_status_for_date(check_date)
    result["date_checked"] = check_date.isoformat()
    result["source"] = "NYC DOT Alternate Side Parking schedule"
    result["source_url"] = "https://www.nyc.gov/html/dot/html/motorist/alternate-side-parking.shtml"
    return result


def _asp_status_for_date(check_date: date) -> dict:
    """Internal: determine ASP status. Tries DOT live page first, falls back to holiday list."""
    # Always suspended on Sundays
    if check_date.weekday() == 6:
        return {
            "is_suspended": True,
            "reason": "ASP is always suspended on Sundays.",
        }

    # Try to fetch live status from NYC DOT
    try:
        live = _fetch_dot_asp_status(check_date)
        if live is not None:
            return live
    except Exception:
        pass  # Fall through to static list

    # Static fallback: known NYC holiday suspension calendar 2025–2027
    holiday_suspensions = _get_holiday_suspensions()
    if check_date in holiday_suspensions:
        return {
            "is_suspended": True,
            "reason": f"ASP is suspended on this date: {holiday_suspensions[check_date]}.",
        }

    return {
        "is_suspended": False,
        "reason": "ASP is in effect on this date. Check signs for specific block rules.",
    }


def _fetch_dot_asp_status(check_date: date) -> Optional[dict]:
    """Attempt to fetch live ASP suspension status from NYC DOT."""
    resp = requests.get(
        "https://www.nyc.gov/html/dot/html/motorist/alternate-side-parking.shtml",
        timeout=5,
        headers={"User-Agent": "Raoul-NYC-Rules-Assistant/1.0"},
    )
    if resp.status_code != 200:
        return None

    text = resp.text.lower()

    # Rough heuristic: look for "suspended" near today's date or current context
    today_str = check_date.strftime("%B %-d").lower()   # e.g. "april 9"
    alt_str = check_date.strftime("%-m/%-d").lower()    # e.g. "4/9"

    suspended_near_today = (today_str in text or alt_str in text) and "suspended" in text
    currently_suspended = "currently suspended" in text or "asp is suspended" in text

    if suspended_near_today or currently_suspended:
        return {
            "is_suspended": True,
            "reason": "ASP is suspended according to the current NYC DOT schedule.",
            "live_data": True,
        }
    return None


def _get_holiday_suspensions() -> dict:
    """Static list of known NYC ASP suspension holidays 2025–2026."""
    return {
        # 2025
        date(2025, 1, 1): "New Year's Day",
        date(2025, 1, 2): "New Year's Day (observed)",
        date(2025, 1, 9): "Lunar New Year",
        date(2025, 1, 20): "Martin Luther King Jr. Day",
        date(2025, 2, 12): "Lincoln's Birthday",
        date(2025, 2, 17): "Presidents' Day",
        date(2025, 3, 31): "Eid al-Fitr (approx.)",
        date(2025, 4, 18): "Good Friday",
        date(2025, 5, 26): "Memorial Day",
        date(2025, 6, 7): "Eid al-Adha (approx.)",
        date(2025, 6, 19): "Juneteenth",
        date(2025, 7, 4): "Independence Day",
        date(2025, 9, 1): "Labor Day",
        date(2025, 9, 23): "Rosh Hashanah",
        date(2025, 9, 24): "Rosh Hashanah (Day 2)",
        date(2025, 10, 2): "Yom Kippur",
        date(2025, 10, 13): "Columbus Day / Indigenous Peoples Day",
        date(2025, 11, 1): "Diwali (approx.)",
        date(2025, 11, 4): "Election Day",
        date(2025, 11, 11): "Veterans Day",
        date(2025, 11, 27): "Thanksgiving Day",
        date(2025, 12, 25): "Christmas Day",
        # 2026
        date(2026, 1, 1): "New Year's Day",
        date(2026, 1, 19): "Martin Luther King Jr. Day",
        date(2026, 1, 29): "Lunar New Year",
        date(2026, 2, 12): "Lincoln's Birthday",
        date(2026, 2, 16): "Presidents' Day",
        date(2026, 3, 21): "Eid al-Fitr (approx.)",
        date(2026, 4, 3): "Good Friday",
        date(2026, 5, 25): "Memorial Day",
        date(2026, 5, 28): "Eid al-Adha (approx.)",
        date(2026, 6, 19): "Juneteenth",
        date(2026, 7, 4): "Independence Day",
        date(2026, 7, 6): "Independence Day (observed)",
        date(2026, 9, 7): "Labor Day",
        date(2026, 9, 12): "Rosh Hashanah",
        date(2026, 9, 13): "Rosh Hashanah (Day 2)",
        date(2026, 9, 21): "Yom Kippur",
        date(2026, 10, 12): "Columbus Day / Indigenous Peoples Day",
        date(2026, 11, 3): "Election Day",
        date(2026, 11, 11): "Veterans Day",
        date(2026, 11, 26): "Thanksgiving Day",
        date(2026, 12, 25): "Christmas Day",
    }


# ─────────────────────────────────────────────
# Tool 3: NYC DOT Parking Signs (Open Data)
# ─────────────────────────────────────────────

PARKING_SIGNS_API = "https://data.cityofnewyork.us/resource/xswq-wnv9.json"

BORO_CODES = {
    "manhattan": "1",
    "bronx": "2",
    "brooklyn": "3",
    "queens": "4",
    "staten island": "5",
    "si": "5",
    "bk": "3",
    "bx": "2",
    "mn": "1",
    "qn": "4",
}


def lookup_parking_signs(
    on_street: str,
    from_street: Optional[str] = None,
    to_street: Optional[str] = None,
    borough: Optional[str] = None,
) -> dict:
    """
    Look up parking sign regulations on a specific NYC block using NYC Open Data.
    Returns the official DOT sign descriptions for matching block faces.
    """
    on_street = on_street.strip().upper()

    where_parts = [f"upper(on_street) like upper('%{_safe(on_street)}%')"]

    if from_street:
        fs = from_street.strip().upper()
        where_parts.append(
            f"(upper(from_street) like upper('%{_safe(fs)}%') OR upper(to_street) like upper('%{_safe(fs)}%'))"
        )

    if to_street:
        ts = to_street.strip().upper()
        where_parts.append(
            f"(upper(from_street) like upper('%{_safe(ts)}%') OR upper(to_street) like upper('%{_safe(ts)}%'))"
        )

    if borough:
        boro_key = borough.lower().strip()
        boro_code = BORO_CODES.get(boro_key)
        if boro_code:
            where_parts.append(f"boro='{boro_code}'")

    params = {
        "$where": " AND ".join(where_parts),
        "$limit": 60,
        "$select": "on_street,from_street,to_street,boro,sg_desc,facing,order_no,seg_id",
        "$order": "on_street,from_street,order_no",
    }

    try:
        resp = requests.get(PARKING_SIGNS_API, params=params, timeout=10)
        resp.raise_for_status()
        signs = resp.json()
    except requests.RequestException as e:
        return {
            "error": f"Could not reach NYC Open Data: {str(e)}",
            "suggestion": "Visit nycdotsigns.net to look up parking signs on your block.",
        }

    if not signs:
        return {
            "signs_found": 0,
            "message": (
                f"No parking sign data found for '{on_street}'"
                + (f" near '{from_street}'" if from_street else "")
                + ". Try a different street spelling or visit nycdotsigns.net."
            ),
            "source": "NYC DOT Parking Regulation Locations and Signs",
            "source_url": "https://data.cityofnewyork.us/Transportation/Parking-Regulation-Locations-and-Signs/xswq-wnv9",
        }

    # Group signs by block face (on_street + from_street + to_street + facing)
    block_faces: dict = {}
    for sign in signs:
        boro_name = _boro_name(sign.get("boro", ""))
        key = f"{sign.get('on_street','')} ({sign.get('from_street','')} to {sign.get('to_street','')}) — {sign.get('facing','')} side, {boro_name}"
        if key not in block_faces:
            block_faces[key] = []
        desc = sign.get("sg_desc", "").strip()
        if desc and desc not in block_faces[key]:
            block_faces[key].append(desc)

    formatted = []
    for block, sign_list in block_faces.items():
        formatted.append({
            "block_face": block,
            "signs": sign_list,
        })

    return {
        "signs_found": len(signs),
        "block_faces": formatted,
        "source": "NYC DOT Parking Regulation Locations and Signs (updated daily)",
        "source_url": "https://data.cityofnewyork.us/Transportation/Parking-Regulation-Locations-and-Signs/xswq-wnv9",
        "interactive_map": "https://nycdotsigns.net/",
        "note": "Sign data reflects the official DOT database. Always check the physical signs on the block, as they are the legal standard.",
    }


def _safe(s: str) -> str:
    """Sanitize string for SoQL injection."""
    return s.replace("'", "''").replace(";", "").replace("--", "")


def _boro_name(code: str) -> str:
    return {
        "1": "Manhattan",
        "2": "Bronx",
        "3": "Brooklyn",
        "4": "Queens",
        "5": "Staten Island",
    }.get(str(code), "NYC")


# ─────────────────────────────────────────────
# Tool dispatcher
# ─────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_current_context",
        "description": (
            "Get the current New York City date, time, day of week, and whether "
            "Alternate Side Parking (ASP) is suspended today. "
            "Call this at the start of any parking or time-sensitive question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "check_asp_suspension",
        "description": (
            "Check whether NYC Alternate Side Parking (ASP) is suspended on a specific date. "
            "ASP is always suspended on Sundays. Also suspended on major city holidays and "
            "many religious holidays. Returns suspension status and reason."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date to check in YYYY-MM-DD format. Omit to check today.",
                }
            },
            "required": [],
        },
    },
    {
        "name": "lookup_parking_signs",
        "description": (
            "Look up the official NYC DOT parking sign regulations on a specific NYC block. "
            "Returns the parking rules (e.g. 'NO PARKING 8AM-6PM MON & THURS') for matching "
            "block faces. Use when someone asks about parking on a specific street or address."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "on_street": {
                    "type": "string",
                    "description": "The street name where the user wants to park (e.g. 'Broadway', 'W 86 ST', 'AMSTERDAM AVE').",
                },
                "from_street": {
                    "type": "string",
                    "description": "Nearest cross street or the lower cross street of the block (e.g. 'Columbus Ave', 'W 83 ST'). Highly recommended for accurate results.",
                },
                "to_street": {
                    "type": "string",
                    "description": "The upper cross street of the block (e.g. 'W 84 ST'). Optional.",
                },
                "borough": {
                    "type": "string",
                    "description": "The NYC borough. One of: manhattan, bronx, brooklyn, queens, staten island.",
                    "enum": ["manhattan", "bronx", "brooklyn", "queens", "staten island"],
                },
            },
            "required": ["on_street"],
        },
    },
]


def execute_tool(name: str, inputs: dict) -> dict:
    """Dispatch a tool call by name."""
    if name == "get_current_context":
        return get_current_context()
    elif name == "check_asp_suspension":
        return check_asp_suspension(date_str=inputs.get("date"))
    elif name == "lookup_parking_signs":
        return lookup_parking_signs(
            on_street=inputs.get("on_street", ""),
            from_street=inputs.get("from_street"),
            to_street=inputs.get("to_street"),
            borough=inputs.get("borough"),
        )
    else:
        return {"error": f"Unknown tool: {name}"}
