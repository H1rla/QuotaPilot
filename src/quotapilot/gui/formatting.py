"""Small display-only formatters shared by GUI view models."""

from __future__ import annotations

from datetime import UTC, datetime


def fraction(value: float | None, *, digits: int = 1) -> str:
    return "Unknown" if value is None else f"{value:.{digits}%}"


def decimal(value: float | None, *, digits: int = 2) -> str:
    return "Unknown" if value is None else f"{value:.{digits}f}"


def duration(seconds: int | None) -> str:
    if seconds is None:
        return "Unknown"
    days, remainder = divmod(max(seconds, 0), 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes = remainder // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def timestamp(value: datetime | None) -> str:
    if value is None:
        return "Unknown"
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


def age(value: float | None) -> str:
    if value is None:
        return "Unknown"
    return duration(round(max(value, 0.0))) + " ago"


def utc_now() -> datetime:
    return datetime.now(UTC)

