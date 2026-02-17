import json
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional


# --- App log patterns (v1) ---
# Examples:
# 2025-12-31T12:15:41Z INFO auth-service User login ok
# 2025-12-31 12:15:41,120 ERROR billing Payment failed
APP_LOG_REGEXES = [
    re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s+"
        r"(?P<level>[A-Z]+)\s+(?P<service>[\w\-.]+)\s+(?P<msg>.*)$"
    ),
    re.compile(
        r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d{1,6})?)\s+"
        r"(?P<level>[A-Z]+)\s+(?P<service>[\w\-.]+)\s+(?P<msg>.*)$"
    ),
]

# --- Android logcat patterns ---
# threadtime: "11-01 08:11:52.482  1203  1203 D AndroidRuntime: CheckJNI is OFF"
# brief:      "D/AndroidRuntime( 1203): CheckJNI is OFF"
ANDROID_PRIORITY_MAP = {
    "V": "DEBUG", "D": "DEBUG", "I": "INFO", "W": "WARNING", "E": "ERROR", "F": "ERROR", "A": "ERROR",
}

ANDROID_THREADTIME_REGEX = re.compile(
    r"^(?P<ts>\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<pri>[VDIWEFA])\s+"
    r"(?P<tag>[^:]+?):\s+(?P<msg>.*)$"
)

ANDROID_BRIEF_REGEX = re.compile(
    r"^(?P<pri>[VDIWEFA])/(?P<tag>[^(]+?)\(\s*(?P<pid>\d+)\):\s+(?P<msg>.*)$"
)

def _parse_android_ts(ts: str) -> Optional[datetime]:
    """Parse Android logcat timestamp (MM-DD HH:MM:SS.mmm). Uses current year."""
    try:
        # Android logs lack year, assume current year
        year = datetime.utcnow().year
        dt = datetime.strptime(f"{year}-{ts}", "%Y-%m-%d %H:%M:%S.%f")
        return dt
    except Exception:
        return None


# --- Access log pattern (common/combined-ish) ---
# 127.0.0.1 - - [31/Dec/2025:12:15:41 +0000] "GET /path HTTP/1.1" 200 123
ACCESS_LOG_REGEX = re.compile(
    r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<ts>[^\]]+)\]\s+'
    r'"(?P<req>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)'
    r'(?:\s+"(?P<ref>[^"]*)"\s+"(?P<ua>[^"]*)")?\s*$'
)

MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}

def _parse_iso_z(ts: str) -> Optional[datetime]:
    # Example: 2025-12-31T12:15:41Z
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)  # store naive UTC
    except Exception:
        return None

def _parse_iso_space(ts: str) -> Optional[datetime]:
    # Example: 2025-12-31 12:15:41,120
    try:
        # Support comma milliseconds
        ts2 = ts.replace(",", ".")
        dt = datetime.fromisoformat(ts2)
        return dt  # naive local-ish; acceptable v1
    except Exception:
        return None

def _parse_access_time(ts: str) -> Optional[datetime]:
    # Example: 31/Dec/2025:12:15:41 +0000
    try:
        # Split: "31/Dec/2025:12:15:41 +0000"
        parts = ts.split()
        dt_part = parts[0]  # 31/Dec/2025:12:15:41
        tz_part = parts[1] if len(parts) > 1 else "+0000"

        day = int(dt_part[0:2])
        mon_str = dt_part[3:6]
        year = int(dt_part[7:11])
        hour = int(dt_part[12:14])
        minute = int(dt_part[15:17])
        second = int(dt_part[18:20])

        month = MONTHS.get(mon_str)
        if not month:
            return None

        dt = datetime(year, month, day, hour, minute, second)

        # Convert to UTC naive if tz is +0000/-0500
        if len(tz_part) == 5 and (tz_part[0] in "+-"):
            sign = 1 if tz_part[0] == "+" else -1
            tzh = int(tz_part[1:3])
            tzm = int(tz_part[3:5])
            offset_seconds = sign * (tzh * 3600 + tzm * 60)
            # dt is local with offset; convert to UTC naive:
            dt_utc = dt - timedelta(seconds=offset_seconds)
            return dt_utc
        return dt
    except Exception:
        return None

# --- JSON field-name mapping constants ---
_TS_KEYS = ["timestamp", "time", "ts", "@timestamp", "datetime", "date"]
_LEVEL_KEYS = ["level", "severity", "lvl", "log_level", "loglevel", "priority"]
_SERVICE_KEYS = ["service", "source", "app", "application", "component", "logger", "program"]
_MSG_KEYS = ["message", "msg", "text", "body", "log"]


def _find_field(data: dict, key_variants: list[str]) -> Any:
    """Top-level + one-level nested lookup for a field."""
    for key in key_variants:
        if key in data:
            return data[key]
    # One-level nested lookup
    for value in data.values():
        if isinstance(value, dict):
            for key in key_variants:
                if key in value:
                    return value[key]
    return None


def _parse_json_timestamp(raw_ts: Any) -> Optional[datetime]:
    """Try to parse a timestamp value from a JSON log."""
    if raw_ts is None:
        return None
    if isinstance(raw_ts, (int, float)):
        try:
            dt = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
            return dt.replace(tzinfo=None)
        except (OSError, ValueError):
            return None
    s = str(raw_ts)
    # Reuse existing parsers
    dt = _parse_iso_z(s) if s.endswith("Z") else None
    if dt:
        return dt
    dt = _parse_iso_space(s)
    if dt:
        return dt
    # Fallback to fromisoformat
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def _try_parse_json(line: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse a line as JSON and extract log fields."""
    stripped = line.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None

    ts_raw = _find_field(data, _TS_KEYS)
    level_raw = _find_field(data, _LEVEL_KEYS)
    service_raw = _find_field(data, _SERVICE_KEYS)
    msg_raw = _find_field(data, _MSG_KEYS)

    ts = _parse_json_timestamp(ts_raw) if ts_raw is not None else None
    level = str(level_raw).upper() if level_raw is not None else None
    service = str(service_raw) if service_raw is not None else None
    msg = str(msg_raw) if msg_raw is not None else None

    found_count = sum(1 for v in [ts, level, service, msg] if v is not None)

    if found_count == 4:
        confidence = 0.95
        status = "parsed"
    elif found_count >= 1:
        confidence = 0.7
        status = "partial"
    else:
        confidence = 0.5
        status = "partial"

    return {
        "timestamp": ts,
        "level": level,
        "service": service,
        "message": msg,
        "raw_line": line.rstrip("\n"),
        "parse_status": status,
        "parse_error": None,
        "parse_confidence": confidence,
        "parser_name": "json_v1",
    }


def parse_line(raw_line: str) -> Dict[str, Any]:
    """
    Returns a normalized dict matching LogEntry columns.
    Never raises.
    """
    line = raw_line.rstrip("\n")

    # 0) JSON logs
    json_result = _try_parse_json(line)
    if json_result is not None:
        return json_result

    # 1) App logs
    for rx in APP_LOG_REGEXES:
        m = rx.match(line)
        if m:
            ts = m.group("ts")
            level = m.group("level").upper() if m.group("level") else None
            service = m.group("service")
            msg = m.group("msg")

            dt = _parse_iso_z(ts) if "T" in ts and ts.endswith("Z") else _parse_iso_space(ts)
            status = "parsed" if (dt and level and service and msg is not None) else "partial"

            return {
                "timestamp": dt,
                "level": level,
                "service": service,
                "message": msg,
                "raw_line": line,
                "parse_status": status,
                "parse_error": None if status != "failed" else "app parse failed",
                "parse_confidence": 0.95 if status == "parsed" else 0.6,
                "parser_name": "app_v1",
            }

    # 2) Android logcat (threadtime + brief)
    m = ANDROID_THREADTIME_REGEX.match(line)
    if not m:
        m = ANDROID_BRIEF_REGEX.match(line)
    if m:
        groups = m.groupdict()
        pri = groups.get("pri", "")
        level = ANDROID_PRIORITY_MAP.get(pri, "INFO")
        tag = groups.get("tag", "").strip()
        msg = groups.get("msg", "")
        ts_str = groups.get("ts")
        dt = _parse_android_ts(ts_str) if ts_str else None
        status = "parsed" if (dt and level and tag) else "partial"

        return {
            "timestamp": dt,
            "level": level,
            "service": tag,
            "message": msg,
            "raw_line": line,
            "parse_status": status,
            "parse_error": None,
            "parse_confidence": 0.90 if status == "parsed" else 0.6,
            "parser_name": "android_v1",
        }

    # 3) Access logs
    m = ACCESS_LOG_REGEX.match(line)
    if m:
        req = m.group("req")
        status_code = m.group("status")
        ts = m.group("ts")

        dt = _parse_access_time(ts)

        msg = f'{req} -> {status_code}' if req else None

        return {
            "timestamp": dt,
            "level": None,
            "service": None,
            "message": msg,
            "raw_line": line,
            "parse_status": "parsed" if dt else "partial",
            "parse_error": None if dt else "access timestamp parse failed",
            "parse_confidence": 0.85 if dt else 0.7,
            "parser_name": "access_v1",
        }


    # 3) Fallback
    return {
        "timestamp": None,
        "level": None,
        "service": None,
        "message": None,
        "raw_line": line,
        "parse_status": "failed",
        "parse_error": "No parser matched",
        "parse_confidence": 0.0,
        "parser_name": None,
    }
