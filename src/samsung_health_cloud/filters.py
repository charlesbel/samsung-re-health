from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def parse_instant_ms(value: str, *, timezone: str = "Europe/Paris") -> int:
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        instant = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("time filters must use ISO-8601") from exc
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=ZoneInfo(timezone))
    return int(instant.timestamp() * 1000)


def parse_until_ms(value: str, *, timezone: str = "Europe/Paris") -> int:
    if len(value) == 10:
        try:
            end_of_day = (
                datetime.fromisoformat(value)
                + timedelta(days=1)
                - timedelta(milliseconds=1)
            )
        except ValueError as exc:
            raise ValueError("time filters must use ISO-8601") from exc
        return int(end_of_day.replace(tzinfo=ZoneInfo(timezone)).timestamp() * 1000)
    return parse_instant_ms(value, timezone=timezone)


def _number(value: object) -> int | float | None:
    number: int | float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = value
    elif isinstance(value, str) and value.strip():
        try:
            number = float(value)
        except ValueError:
            number = None
    if number is not None and not math.isfinite(number):
        raise ValueError("timestamps must be finite")
    return number


def filter_records(
    records: Iterable[dict],
    *,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> Iterator[dict]:
    if since_ms is not None and until_ms is not None and since_ms > until_ms:
        raise ValueError("since must not be after until")
    for record in records:
        if since_ms is None and until_ms is None:
            yield record
            continue
        data = record.get("data") if isinstance(record, dict) else None
        if not isinstance(data, dict):
            raise ValueError("filtered record is missing a timestamp")  # noqa: TRY004
        start = _number(data.get("start_time"))
        if start is None:
            start = _number(data.get("create_time"))
        if start is None:
            start = _number(data.get("update_time"))
        end = _number(data.get("end_time"))
        if end is None:
            end = start
        if start is None or end is None:
            raise ValueError("filtered record is missing a timestamp")
        if start > end:
            raise ValueError("record has an inverted time interval")
        if since_ms is not None and end < since_ms:
            continue
        if until_ms is not None and start > until_ms:
            continue
        yield record
