"""Schema-adaptive and composite analytics over the private Samsung Health mirror."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import fmean, pstdev, stdev
from zoneinfo import ZoneInfo

from .cache import HealthCache
from .semantics import field_semantics

TZ = ZoneInfo("Europe/Paris")
MAX_MS = 9_223_372_036_854_775_807


def _round(value: float) -> float:
    return round(float(value), 3)


def _is_sensitive_field(key: str) -> bool:
    low = key.lower()
    return (
        low.endswith("id")
        or "_id" in low
        or any(
            part in low
            for part in (
                "uuid",
                "comment",
                "pkg",
                "location",
                "latitude",
                "longitude",
                "address",
                "url",
                "uri",
                "file",
                "path",
                "device",
            )
        )
    )


def _field_summary(
    manifest_id: str, key: str, observed: list[object], record_count: int
) -> dict:
    non_null = [value for value in observed if value is not None]
    type_names = sorted({type(value).__name__ for value in non_null})
    numeric = [
        float(value)
        for value in non_null
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    statistics: dict[str, object]
    if _is_sensitive_field(key):
        statistics = {"count": len(non_null), "values_redacted": True}
        try:
            statistics["unique_count"] = len(set(non_null))
        except TypeError:
            pass
    elif numeric and len(numeric) == len(non_null):
        statistics = {
            "count": len(numeric),
            "sum": _round(sum(numeric)),
            "mean": _round(fmean(numeric)),
            "population_standard_deviation": _round(pstdev(numeric)),
            "sample_standard_deviation": _round(stdev(numeric))
            if len(numeric) > 1
            else None,
            "minimum": _round(min(numeric)),
            "maximum": _round(max(numeric)),
            "latest": _round(numeric[-1]),
        }
    elif non_null and all(isinstance(value, bool) for value in non_null):
        statistics = {
            "count": len(non_null),
            "true": sum(value is True for value in non_null),
            "false": sum(value is False for value in non_null),
        }
    elif non_null and all(isinstance(value, str) for value in non_null):
        statistics = {
            "count": len(non_null),
            "unique_count": len(set(non_null)),
            "values_redacted": True,
        }
    elif non_null and all(isinstance(value, dict) for value in non_null):
        statistics = {
            "count": len(non_null),
            "object_keys": sorted(
                {nested_key for value in non_null for nested_key in value}
            ),
        }
    elif non_null and all(isinstance(value, list) for value in non_null):
        statistics = {
            "count": len(non_null),
            "element_count": sum(len(value) for value in non_null),
        }
    else:
        statistics = {"count": len(non_null)}
    result = {
        "observed_count": len(observed),
        "missing_count": record_count - len(observed),
        "null_count": sum(value is None for value in observed),
        "types": type_names or ["null"],
        "statistics": statistics,
        "provenance": {
            "status": "raw_observed",
            "source": "Samsung Health Cloud account data",
            "meaning": "Raw field name; no semantic meaning inferred.",
        },
    }
    documented = field_semantics(manifest_id, key)
    if documented is not None:
        result.update(documented)
        validation_rule: dict[str, object] | None = None
        violation_count = 0
        checked_count = 0
        if "valid_range" in documented:
            rule = documented["valid_range"]
            checked = [
                value
                for value in non_null
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            checked_count = len(checked)
            violation_count = sum(
                (rule["minimum"] is not None and float(value) < rule["minimum"])
                or (rule["maximum"] is not None and float(value) > rule["maximum"])
                for value in checked
            )
            validation_rule = dict(rule)
        elif "max_length" in documented:
            checked = [value for value in non_null if isinstance(value, str)]
            checked_count = len(checked)
            violation_count = sum(
                len(value) > documented["max_length"] for value in checked
            )
            validation_rule = {"maximum_length": documented["max_length"]}
        elif "enum" in documented and documented.get("enum_exhaustive", True):
            checked = [
                value
                for value in non_null
                if isinstance(value, (str, int, float, bool))
            ]
            checked_count = len(checked)
            violation_count = sum(value not in documented["enum"] for value in checked)
            validation_rule = {"allowed_values": sorted(documented["enum"])}
        if validation_rule is not None:
            result["validation"] = {
                "status": "violations_found" if violation_count else "valid",
                "rule": validation_rule,
                "checked_count": checked_count,
                "unchecked_count": len(non_null) - checked_count,
                "violation_count": violation_count,
            }
        else:
            result["validation"] = {
                "status": "no_encoded_rule",
                "checked_count": 0,
                "unchecked_count": len(non_null),
                "violation_count": 0,
            }
    return result


def summarize_generic(manifest_id: str, records: list[dict]) -> dict:
    """Provide useful numeric statistics without assuming a fixed Samsung schema."""
    observed_keys = sorted({key for record in records for key in record})
    fields = {
        key: _field_summary(
            manifest_id,
            key,
            [record[key] for record in records if key in record],
            len(records),
        )
        for key in observed_keys
    }
    status_counts: dict[str, int] = defaultdict(int)
    for field in fields.values():
        status_counts[field["provenance"]["status"]] += 1
    validations = [
        field["validation"] for field in fields.values() if "validation" in field
    ]
    relationship_validation = []
    start_semantics = field_semantics(manifest_id, "start_time")
    end_semantics = field_semantics(manifest_id, "end_time")
    has_official_session_bounds = (
        start_semantics is not None
        and end_semantics is not None
        and start_semantics["provenance"]["status"] == "official_documentation"
        and end_semantics["provenance"]["status"] == "official_documentation"
    )
    if (
        has_official_session_bounds
        and "start_time" in observed_keys
        and "end_time" in observed_keys
    ):
        comparable = [
            record
            for record in records
            if isinstance(record.get("start_time"), (int, float))
            and not isinstance(record.get("start_time"), bool)
            and isinstance(record.get("end_time"), (int, float))
            and not isinstance(record.get("end_time"), bool)
        ]
        relationship_validation.append(
            {
                "rule": "end_time >= start_time",
                "checked_count": len(comparable),
                "unchecked_count": len(records) - len(comparable),
                "violation_count": sum(
                    record["end_time"] < record["start_time"] for record in comparable
                ),
            }
        )
    return {
        "analysis": "generic",
        "manifest_id": manifest_id,
        "events": len(records),
        "fields": fields,
        "coverage": {
            "observed_fields": len(observed_keys),
            "analyzed_fields": len(fields),
            "ignored_fields": [],
            "coverage_percent": 100.0,
            "officially_documented_fields": status_counts["official_documentation"],
            "official_schema_convention_fields": status_counts[
                "official_schema_convention"
            ],
            "apk_documented_fields": status_counts["apk_decompiled"],
            "open_source_documented_fields": status_counts["open_source"],
            "raw_observed_fields": status_counts["raw_observed"],
            "validation": {
                "fields_with_applicable_rule": sum(
                    item["status"] != "no_encoded_rule" for item in validations
                ),
                "fields_without_encoded_rule": sum(
                    item["status"] == "no_encoded_rule" for item in validations
                ),
                "checked_values": sum(item["checked_count"] for item in validations),
                "unchecked_values": sum(
                    item["unchecked_count"] for item in validations
                ),
                "violation_count": sum(item["violation_count"] for item in validations),
                "relationship_rules": relationship_validation,
            },
        },
    }


def _dt_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def period_bounds(
    period: str,
    anchor_date: date,
    tz: ZoneInfo | None = None,
    offset: int = 0,
) -> tuple[int, int]:
    target_tz = tz or TZ
    if period == "day":
        target_day = anchor_date + timedelta(days=offset)
        start = datetime.combine(target_day, time.min, target_tz)
        end = start + timedelta(days=1)
    elif period == "month":
        year = anchor_date.year
        month = anchor_date.month + offset
        while month < 1:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1
        start = datetime(year, month, 1, tzinfo=target_tz)
        next_month = 1 if month == 12 else month + 1
        next_year = year + 1 if month == 12 else year
        end = datetime(next_year, next_month, 1, tzinfo=target_tz)
    else:
        start_day = (
            anchor_date
            - timedelta(days=anchor_date.weekday())
            + timedelta(weeks=offset)
        )
        start = datetime.combine(start_day, time.min, target_tz)
        end = start + timedelta(days=7)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000) - 1


def _period_week(day: date, tz: ZoneInfo | None = None) -> tuple[int, int]:
    return period_bounds("week", day, tz=tz)


class HealthAnalysisEngine:
    def __init__(
        self, cache: HealthCache, *, timezone: str | ZoneInfo = "Europe/Paris"
    ):
        self.cache = cache
        self.tz = ZoneInfo(timezone) if isinstance(timezone, str) else timezone

    def generic(self, manifest_id: str, since_ms: int, until_ms: int) -> dict:
        return summarize_generic(
            manifest_id,
            self.cache.records(manifest_id, since_ms=since_ms, until_ms=until_ms),
        )

    def generic_latest(self, manifest_id: str) -> dict:
        rows = self.cache.records(manifest_id, since_ms=0, until_ms=MAX_MS)
        if not rows:
            return summarize_generic(manifest_id, [])
        latest = max(
            rows,
            key=lambda row: row.get(
                "end_time", row.get("start_time", row.get("update_time", 0))
            ),
        )
        result = summarize_generic(manifest_id, [latest])
        result["event"] = "latest"
        return result

    def sleep_latest(self) -> dict:
        source_records = self.cache.records(
            "com.samsung.health.sleep", since_ms=0, until_ms=MAX_MS
        )
        if not source_records:
            return {
                "analysis": "sleep",
                "available": False,
                "reason": "no sleep source record",
            }
        source_record = max(
            source_records,
            key=lambda row: row.get("end_time", row.get("start_time", 0)),
        )
        start = int(source_record.get("start_time", 0))
        end = int(source_record.get("end_time", start))
        sleep_id = source_record.get("datauuid") or source_record.get("sleep_id")
        stages = [
            row
            for row in self.cache.records(
                "com.samsung.health.sleep_stage", since_ms=start, until_ms=end
            )
            if not sleep_id or row.get("sleep_id") == sleep_id
        ]
        stage_names = {40001: "awake", 40002: "light", 40003: "deep", 40004: "rem"}
        minutes = {name: 0.0 for name in stage_names.values()}
        valid_stages: list[tuple[dict, int, float, float]] = []
        invalid_stage_values = invalid_stage_intervals = 0
        for row in stages:
            stage_code = row.get("stage")
            if (
                not isinstance(stage_code, int)
                or isinstance(stage_code, bool)
                or stage_code not in stage_names
            ):
                invalid_stage_values += 1
                continue
            row_start, row_end = row.get("start_time"), row.get("end_time")
            if (
                not isinstance(row_start, (int, float))
                or not isinstance(row_end, (int, float))
                or row_end < row_start
            ):
                invalid_stage_intervals += 1
                continue
            clipped_start, clipped_end = (
                max(float(start), float(row_start)),
                min(float(end), float(row_end)),
            )
            if clipped_end < clipped_start:
                invalid_stage_intervals += 1
                continue
            valid_stages.append((row, stage_code, clipped_start, clipped_end))
            minutes[stage_names[stage_code]] += (clipped_end - clipped_start) / 60_000
        minutes = {key: round(value, 1) for key, value in minutes.items()}
        asleep = sum(minutes[key] for key in ("light", "deep", "rem"))
        in_bed = max(0, end - start) / 60_000
        ordered = sorted(valid_stages, key=lambda item: item[2])
        awake_periods = sum(
            1
            for index, current in enumerate(ordered)
            if current[1] == 40001 and (index == 0 or ordered[index - 1][1] != 40001)
        )
        rem_periods = sum(
            1
            for index, current in enumerate(ordered)
            if current[1] == 40004 and (index == 0 or ordered[index - 1][1] != 40004)
        )
        merged_stage_intervals: list[list[float]] = []
        stage_interval_overlap_count = 0
        for _, _, interval_start, interval_end in ordered:
            if (
                not merged_stage_intervals
                or interval_start >= merged_stage_intervals[-1][1]
            ):
                merged_stage_intervals.append([interval_start, interval_end])
            else:
                stage_interval_overlap_count += 1
                merged_stage_intervals[-1][1] = max(
                    merged_stage_intervals[-1][1], interval_end
                )
        covered_stage_minutes = (
            sum(
                interval_end - interval_start
                for interval_start, interval_end in merged_stage_intervals
            )
            / 60_000
        )

        heart = self.cache.records(
            "com.samsung.health.heart_rate", since_ms=start, until_ms=end
        )
        heart_values = [
            float(row["heart_rate"])
            for row in heart
            if isinstance(row.get("heart_rate"), (int, float))
        ]
        oxygen_rows = self.cache.records(
            "com.samsung.health.oxygen_saturation", since_ms=start, until_ms=end
        )
        oxygen_values = [
            float(row["spo2"])
            for row in oxygen_rows
            if isinstance(row.get("spo2"), (int, float))
        ]
        snores = self.cache.records(
            "com.samsung.shealth.sleep_snoring", since_ms=start, until_ms=end
        )

        previous_source_records = sorted(
            (row for row in source_records if row.get("end_time", 0) < start),
            key=lambda row: row.get("end_time", 0),
            reverse=True,
        )[:7]
        baseline = {"source_records": 0}
        if previous_source_records:
            baseline_start = min(
                int(row.get("start_time", 0)) for row in previous_source_records
            )
            baseline_end = max(
                int(row.get("end_time", 0)) for row in previous_source_records
            )
            prior_stages = self.cache.records(
                "com.samsung.health.sleep_stage",
                since_ms=baseline_start,
                until_ms=baseline_end,
            )
            asleep_by_id: dict[str, float] = defaultdict(float)
            for row in prior_stages:
                if isinstance(row.get("stage"), int) and row.get("stage") in {
                    40002,
                    40003,
                    40004,
                }:
                    asleep_by_id[str(row.get("sleep_id"))] += (
                        max(0, row.get("end_time", 0) - row.get("start_time", 0))
                        / 60_000
                    )
            prior_asleep = []
            prior_efficiency = []
            for row in previous_source_records:
                value = asleep_by_id.get(
                    str(row.get("datauuid") or row.get("sleep_id")), 0
                )
                bed = max(0, row.get("end_time", 0) - row.get("start_time", 0)) / 60_000
                if value:
                    prior_asleep.append(value)
                    if bed:
                        prior_efficiency.append(100 * value / bed)
            baseline = {
                "source_records": len(previous_source_records),
                "records_with_stages": len(prior_asleep),
                "arithmetic_mean_stage_asleep_minutes": round(fmean(prior_asleep), 1)
                if prior_asleep
                else None,
                "arithmetic_mean_derived_stage_efficiency_percent": round(
                    fmean(prior_efficiency), 1
                )
                if prior_efficiency
                else None,
                "difference_from_record_mean_asleep_minutes": round(
                    asleep - fmean(prior_asleep), 1
                )
                if prior_asleep
                else None,
            }

        sources = {
            "com.samsung.health.sleep": [source_record],
            "com.samsung.health.sleep_stage": stages,
            "com.samsung.health.heart_rate": heart,
            "com.samsung.health.oxygen_saturation": oxygen_rows,
            "com.samsung.shealth.sleep_snoring": snores,
        }
        field_analysis = {
            manifest: summarize_generic(manifest, rows)
            for manifest, rows in sources.items()
        }
        observed_field_count = sum(
            item["coverage"]["observed_fields"] for item in field_analysis.values()
        )
        official_field_count = sum(
            item["coverage"]["officially_documented_fields"]
            for item in field_analysis.values()
        )
        convention_field_count = sum(
            item["coverage"]["official_schema_convention_fields"]
            for item in field_analysis.values()
        )
        apk_field_count = sum(
            item["coverage"]["apk_documented_fields"]
            for item in field_analysis.values()
        )
        open_source_field_count = sum(
            item["coverage"]["open_source_documented_fields"]
            for item in field_analysis.values()
        )
        return {
            "analysis": "sleep",
            "available": True,
            "start": datetime.fromtimestamp(start / 1000, TZ).isoformat(),
            "end": datetime.fromtimestamp(end / 1000, TZ).isoformat(),
            "time_in_bed_minutes": round(in_bed, 1),
            "asleep_minutes": round(asleep, 1),
            "reported_efficiency_percent": source_record.get("efficiency")
            if isinstance(source_record.get("efficiency"), (int, float))
            else None,
            "derived_stage_coverage_percent": round(
                100 * covered_stage_minutes / in_bed, 1
            )
            if in_bed
            else None,
            "stages_minutes": minutes,
            "stage_interval_validation": {
                "invalid_stage_values": invalid_stage_values,
                "invalid_intervals": invalid_stage_intervals,
                "overlap_count": stage_interval_overlap_count,
            },
            "stages_percent": {
                key: round(100 * value / asleep, 1) if asleep else 0
                for key, value in minutes.items()
                if key != "awake"
            },
            "awake_periods_detected": awake_periods,
            "rem_periods_detected": rem_periods,
            "heart_rate": (
                {
                    "samples": len(heart_values),
                    "average_bpm": round(fmean(heart_values), 1),
                    "minimum_bpm": min(heart_values),
                    "maximum_bpm": max(heart_values),
                }
                if heart_values
                else {"available": False}
            ),
            "oxygen": (
                {
                    "samples": len(oxygen_values),
                    "average_percent": round(fmean(oxygen_values), 1),
                }
                if oxygen_values
                else {"available": False}
            ),
            "snoring": {"source_records": len(snores)},
            "baseline_previous_source_records": baseline,
            "joins": {
                "sleep_stages": {
                    "join_kind": "sleep_id_when_available_plus_time_window"
                },
                "heart_rate": {
                    "join_kind": "time_window_only",
                    "meaning": "temporally concomitant measurements",
                },
                "oxygen_saturation": {
                    "join_kind": "time_window_only",
                    "meaning": "temporally concomitant measurements",
                },
                "snoring": {
                    "join_kind": "time_window_only",
                    "meaning": "temporally concomitant source records",
                },
            },
            "calculations": {
                "start": {
                    "kind": "direct_account_field",
                    "field": "com.samsung.health.sleep.start_time",
                    "rendering": "Europe/Paris ISO-8601",
                },
                "end": {
                    "kind": "direct_account_field",
                    "field": "com.samsung.health.sleep.end_time",
                    "rendering": "Europe/Paris ISO-8601",
                },
                "time_in_bed_minutes": {
                    "kind": "derived_basic",
                    "formula": "max(0, end_time - start_time) / 60000",
                },
                "stages_minutes": {
                    "kind": "derived_basic",
                    "formula": "sum valid clipped stage interval durations / 60000 grouped by official stage enum",
                },
                "asleep_minutes": {
                    "kind": "derived_basic",
                    "formula": "light_minutes + deep_minutes + rem_minutes",
                },
                "reported_efficiency_percent": {
                    "kind": "direct_account_field",
                    "field": "com.samsung.health.sleep.efficiency",
                    "semantic_source": "apk_decompiled",
                },
                "derived_stage_coverage_percent": {
                    "kind": "derived_basic",
                    "formula": "100 * duration(union(clipped valid stage intervals)) / time_in_bed_minutes",
                    "not_equivalent_to": "Samsung sleep efficiency",
                },
                "stages_percent": {
                    "kind": "derived_basic",
                    "formula": "100 * stage_minutes / (light_minutes + deep_minutes + rem_minutes); awake excluded",
                },
                "stage_interval_validation": {
                    "kind": "derived_validation",
                    "formula": "count unknown stage values, invalid intervals, and overlaps after clipping to source-record window",
                },
                "awake_periods_detected": {
                    "kind": "derived_basic",
                    "formula": "count starts of contiguous official AWAKE blocks, including the first interval",
                    "not_equivalent_to": "number of conscious awakenings",
                },
                "rem_periods_detected": {
                    "kind": "derived_basic",
                    "formula": "count starts of contiguous official REM blocks, including the first interval",
                },
                "heart_rate.samples": {
                    "kind": "derived_basic",
                    "formula": "count numeric heart_rate values in time window",
                },
                "heart_rate.average_bpm": {
                    "kind": "derived_basic",
                    "formula": "arithmetic mean of numeric heart_rate values in time window",
                },
                "heart_rate.minimum_bpm": {
                    "kind": "derived_basic",
                    "formula": "minimum of numeric heart_rate values in time window",
                },
                "heart_rate.maximum_bpm": {
                    "kind": "derived_basic",
                    "formula": "maximum of numeric heart_rate values in time window",
                },
                "oxygen.samples": {
                    "kind": "derived_basic",
                    "formula": "count numeric spo2 values in time window",
                },
                "oxygen.average_percent": {
                    "kind": "derived_basic",
                    "formula": "arithmetic mean of numeric spo2 values in time window",
                },
                "snoring.source_records": {
                    "kind": "derived_basic",
                    "formula": "count snoring source records overlapping the time window",
                },
                "baseline_previous_source_records": {
                    "kind": "derived_basic",
                    "formula": "up to seven prior sleep source records ordered by end_time; nested means are arithmetic and differences subtract those means",
                },
            },
            "field_analysis": field_analysis,
            "coverage": {
                "observed_fields": observed_field_count,
                "analyzed_fields": observed_field_count,
                "ignored_fields": [],
                "coverage_percent": 100.0,
                "officially_documented_fields": official_field_count,
                "official_schema_convention_fields": convention_field_count,
                "apk_documented_fields": apk_field_count,
                "open_source_documented_fields": open_source_field_count,
                "raw_observed_fields": observed_field_count
                - official_field_count
                - convention_field_count
                - apk_field_count
                - open_source_field_count,
            },
            "medical_notice": "Analyse descriptive, sans valeur diagnostique.",
        }

    def _activity_period(self, since_ms: int, until_ms: int) -> dict:
        rows = self.cache.records(
            "com.samsung.shealth.step_daily_trend", since_ms=since_ms, until_ms=until_ms
        )
        observed_days = {
            int(row.get("day_time", row.get("start_time", 0))) for row in rows
        }
        by_day: dict[int, dict] = {}
        for row in rows:
            day = int(row.get("day_time", row.get("start_time", 0)))
            if row.get("source_type") != -2:
                continue
            current = by_day.get(day)
            if current is None or int(row.get("update_time", 0)) >= int(
                current.get("update_time", 0)
            ):
                by_day[day] = row
        return {
            "days_with_data": len(by_day),
            "days_without_authoritative_all_sources": len(observed_days - set(by_day)),
            "distance_km": round(
                sum(float(row.get("distance", 0)) for row in by_day.values()) / 1000, 3
            ),
            "steps": int(sum(float(row.get("count", 0)) for row in by_day.values())),
            "calories_kcal": round(
                sum(float(row.get("calorie", 0)) for row in by_day.values()), 1
            ),
            "calculations": {
                "daily_selection": {
                    "kind": "official_aggregation_selection",
                    "rule": "source_type == -2 only",
                    "meaning": "Samsung all-sources deduplicated daily record",
                },
                "period_totals": {
                    "kind": "derived_basic",
                    "formula": "sum selected daily all-sources records",
                },
            },
            "field_analysis": summarize_generic(
                "com.samsung.shealth.step_daily_trend", rows
            ),
        }

    def activity_interval(
        self, since_ms: int, until_ms: int, *, compare_previous: bool = False
    ) -> dict:
        result = {
            "analysis": "activity",
            "since_ms": since_ms,
            "until_ms": until_ms,
            **self._activity_period(since_ms, until_ms),
        }
        if compare_previous:
            width = until_ms - since_ms + 1
            previous = self._activity_period(since_ms - width, until_ms - width)
            diff = result["distance_km"] - previous["distance_km"]
            result["comparison"] = {
                "previous_distance_km": previous["distance_km"],
                "previous_days_with_data": previous["days_with_data"],
                "difference_km": round(diff, 3),
                "change_percent": round(100 * diff / previous["distance_km"], 1)
                if previous["distance_km"]
                else None,
                "more_than_previous": diff > 0,
            }
            result["calculations"]["comparison"] = {
                "kind": "derived_basic",
                "formula": "current period minus immediately preceding equal-width period; percent = 100 * difference / previous",
            }
        return result

    def activity_week(self, day: date, *, compare_previous: bool = False) -> dict:
        since, until = _period_week(day)
        result = self.activity_interval(since, until, compare_previous=compare_previous)
        result["period"] = "week"
        return result

    def exercise(self, since_ms: int, until_ms: int) -> dict:
        rows = self.cache.records(
            "com.samsung.health.exercise", since_ms=since_ms, until_ms=until_ms
        )
        weighted = [
            (
                float(row["mean_heart_rate"]),
                float(
                    row.get(
                        "duration",
                        max(1, row.get("end_time", 0) - row.get("start_time", 0)),
                    )
                ),
            )
            for row in rows
            if isinstance(row.get("mean_heart_rate"), (int, float))
        ]
        total_weight = sum(weight for _, weight in weighted)
        mins = [
            float(row["min_heart_rate"])
            for row in rows
            if isinstance(row.get("min_heart_rate"), (int, float))
        ]
        maxs = [
            float(row["max_heart_rate"])
            for row in rows
            if isinstance(row.get("max_heart_rate"), (int, float))
        ]
        return {
            "analysis": "exercise",
            "events": len(rows),
            "duration_minutes": round(
                sum(float(row.get("duration", 0)) for row in rows) / 60_000, 1
            ),
            "distance_km": round(
                sum(float(row.get("distance", 0)) for row in rows) / 1000, 3
            ),
            "calories_kcal": round(
                sum(float(row.get("calorie", 0)) for row in rows), 1
            ),
            "heart_rate": (
                {
                    "events_with_heart_rate": len(weighted),
                    "duration_weighted_mean_bpm": round(
                        sum(value * weight for value, weight in weighted)
                        / total_weight,
                        1,
                    ),
                    "minimum_bpm": min(mins) if mins else None,
                    "maximum_bpm": max(maxs) if maxs else None,
                }
                if weighted and total_weight
                else {"available": False}
            ),
            "calculations": {
                "events": {
                    "kind": "derived_basic",
                    "formula": "count exercise source records in interval",
                },
                "duration_minutes": {
                    "kind": "derived_basic",
                    "formula": "sum(duration) / 60000",
                },
                "distance_km": {
                    "kind": "derived_basic",
                    "formula": "sum(distance) / 1000",
                },
                "calories_kcal": {"kind": "derived_basic", "formula": "sum(calorie)"},
                "heart_rate.events_with_heart_rate": {
                    "kind": "derived_basic",
                    "formula": "count source records with numeric mean_heart_rate",
                },
                "heart_rate.duration_weighted_mean_bpm": {
                    "kind": "derived_basic",
                    "formula": "sum(mean_heart_rate * duration) / sum(duration)",
                },
                "heart_rate.minimum_bpm": {
                    "kind": "derived_basic",
                    "formula": "minimum of numeric min_heart_rate source fields",
                },
                "heart_rate.maximum_bpm": {
                    "kind": "derived_basic",
                    "formula": "maximum of numeric max_heart_rate source fields",
                },
            },
            "field_analysis": summarize_generic("com.samsung.health.exercise", rows),
        }
