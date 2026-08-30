from __future__ import annotations

from datetime import date, datetime, time, timedelta
from statistics import fmean
from zoneinfo import ZoneInfo

from .cache import HealthCache

UTC = ZoneInfo("UTC")
PARIS = ZoneInfo("Europe/Paris")
STEP_DAILY = "com.samsung.shealth.step_daily_trend"
SLEEP = "com.samsung.health.sleep"
HEART_RATE = "com.samsung.health.heart_rate"
WEIGHT = "com.samsung.health.weight"


def _ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _day_bounds(day: date, tz: ZoneInfo = UTC) -> tuple[int, int]:
    start = datetime.combine(day, time.min, tz)
    return _ms(start), _ms(start + timedelta(days=1)) - 1


class HealthAnalytics:
    def __init__(self, cache: HealthCache, *, timezone: str | ZoneInfo = "UTC") -> None:
        self.cache = cache
        self.tz = ZoneInfo(timezone) if isinstance(timezone, str) else timezone

    def steps(self, day: date) -> dict:
        since, until = _day_bounds(day, self.tz)
        records = self.cache.records(STEP_DAILY, since_ms=since, until_ms=until)
        if not records:
            return {
                "date": day.isoformat(),
                "steps": None,
                "distance_m": None,
                "calories_kcal": None,
                "availability_reason": "no Samsung daily trend source record",
            }
        all_sources = [row for row in records if row.get("source_type") == -2]
        if not all_sources:
            return {
                "date": day.isoformat(),
                "steps": None,
                "distance_m": None,
                "calories_kcal": None,
                "availability_reason": "no authoritative Samsung all-sources record (source_type == -2)",
            }
        best = max(all_sources, key=lambda row: int(row.get("update_time") or 0))
        return {
            "date": day.isoformat(),
            "steps": int(best.get("count") or 0),
            "distance_m": round(float(best.get("distance") or 0), 1),
            "calories_kcal": round(float(best.get("calorie") or 0), 1),
            "calculations": {
                "record_selection": {
                    "kind": "official_aggregation_selection",
                    "rule": "source_type == -2, then greatest update_time",
                    "meaning": "Samsung all-sources deduplicated daily record",
                },
                "steps": {
                    "kind": "direct_account_field",
                    "field": f"{STEP_DAILY}.count",
                },
                "distance_m": {
                    "kind": "direct_account_field",
                    "field": f"{STEP_DAILY}.distance",
                    "unit": "m",
                },
                "calories_kcal": {
                    "kind": "direct_account_field",
                    "field": f"{STEP_DAILY}.calorie",
                    "unit": "kcal",
                },
            },
        }

    def sleep(self, day: date) -> dict:
        # A sleep day is the night that wakes on `day`, including late morning sleep.
        start = datetime.combine(day - timedelta(days=1), time(12), self.tz)
        end = datetime.combine(day, time(18), self.tz)
        records = self.cache.records(SLEEP, since_ms=_ms(start), until_ms=_ms(end))
        intervals = sorted(
            (int(row["start_time"]), int(row["end_time"]))
            for row in records
            if isinstance(row.get("start_time"), (int, float))
            and isinstance(row.get("end_time"), (int, float))
            and row["end_time"] > row["start_time"]
        )
        merged: list[list[int]] = []
        for interval_start, interval_end in intervals:
            if merged and interval_start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], interval_end)
            else:
                merged.append([interval_start, interval_end])
        duration = round(sum(end_ms - start_ms for start_ms, end_ms in merged) / 60_000)
        efficiencies = [
            float(row["efficiency"])
            for row in records
            if isinstance(row.get("efficiency"), (int, float))
        ]
        return {
            "date": day.isoformat(),
            "duration_minutes": duration if intervals else None,
            "source_records": len(records),
            "merged_sleep_intervals": len(merged),
            "average_reported_efficiency_percent": round(fmean(efficiencies), 1)
            if efficiencies
            else None,
            "calculations": {
                "duration_minutes": {
                    "kind": "derived_basic",
                    "formula": "duration(union(valid overlapping source-record intervals)) / 60000",
                },
                "source_records": {
                    "kind": "derived_basic",
                    "formula": "count Samsung sleep source records in noon-to-18:00 sleep-day window",
                },
                "merged_sleep_intervals": {
                    "kind": "derived_basic",
                    "formula": "count connected components after interval union",
                },
                "average_reported_efficiency_percent": {
                    "kind": "derived_basic",
                    "formula": "arithmetic mean of numeric Samsung-reported efficiency fields",
                    "source_field": f"{SLEEP}.efficiency",
                },
            },
        }

    def heart_rate(self, day: date) -> dict:
        since, until = _day_bounds(day, self.tz)
        records = self.cache.records(HEART_RATE, since_ms=since, until_ms=until)
        values = [
            float(row["heart_rate"])
            for row in records
            if isinstance(row.get("heart_rate"), (int, float))
        ]
        return {
            "date": day.isoformat(),
            "samples": len(values),
            "arithmetic_mean_bpm": round(fmean(values), 1) if values else None,
            "minimum_bpm": round(min(values), 1) if values else None,
            "maximum_bpm": round(max(values), 1) if values else None,
            "calculations": {
                "samples": {
                    "kind": "derived_basic",
                    "formula": "count numeric heart_rate values in civil day",
                },
                "arithmetic_mean_bpm": {
                    "kind": "derived_basic",
                    "formula": "arithmetic mean of numeric heart_rate values",
                    "source_field": f"{HEART_RATE}.heart_rate",
                },
                "minimum_bpm": {
                    "kind": "derived_basic",
                    "formula": "minimum of numeric heart_rate values",
                },
                "maximum_bpm": {
                    "kind": "derived_basic",
                    "formula": "maximum of numeric heart_rate values",
                },
            },
        }

    def latest_weight(self, *, until: date | None = None) -> dict:
        end = _day_bounds(until)[1] if until else 9_223_372_036_854_775_807
        records = self.cache.records(WEIGHT, since_ms=0, until_ms=end)
        if not records:
            return {
                "weight_kg": None,
                "measured_at": None,
                "availability_reason": "no weight source record",
            }
        latest = max(
            records,
            key=lambda row: int(row.get("start_time") or row.get("create_time") or 0),
        )
        measured_ms = int(latest.get("start_time") or latest.get("create_time") or 0)
        return {
            "weight_kg": round(float(latest["weight"]), 2)
            if isinstance(latest.get("weight"), (int, float))
            else None,
            "measured_at": datetime.fromtimestamp(measured_ms / 1000, self.tz).isoformat()
            if measured_ms
            else None,
            "calculations": {
                "record_selection": {
                    "kind": "derived_basic",
                    "formula": "greatest start_time, falling back to create_time, not after requested date",
                },
                "weight_kg": {
                    "kind": "direct_account_field",
                    "field": f"{WEIGHT}.weight",
                    "unit": "kg",
                },
                "measured_at": {
                    "kind": "direct_account_field",
                    "field": f"{WEIGHT}.start_time or create_time",
                    "rendering": f"{getattr(self.tz, 'key', str(self.tz))} ISO-8601",
                },
            },
        }

    def summary(self, day: date) -> dict:
        return {
            "date": day.isoformat(),
            "steps": self.steps(day),
            "sleep": self.sleep(day),
            "heart_rate": self.heart_rate(day),
            "latest_weight": self.latest_weight(until=day),
        }
