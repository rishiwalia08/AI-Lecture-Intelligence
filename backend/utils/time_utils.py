from __future__ import annotations


def format_timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    if hh > 0:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return f"{mm:02d}:{ss:02d}"


def timestamp_range(start: float, end: float) -> str:
    return f"{format_timestamp(start)} - {format_timestamp(end)}"
