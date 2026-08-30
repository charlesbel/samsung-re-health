from __future__ import annotations

from datetime import date
from pathlib import Path

from samsung_health_cloud.analysis_engine import HealthAnalysisEngine, summarize_generic
from samsung_health_cloud.cache import HealthCache


def add(cache, manifest, uuid, **data):
    cache.upsert_documents(
        manifest,
        [
            {
                "data": {"datauuid": uuid, **data},
                "files": [],
                "downloadUrls": [],
                "needToDecrypt": False,
            }
        ],
    )


def test_generic_analysis_uses_neutral_field_statistics_not_name_based_aggregations():
    result = summarize_generic(
        "com.samsung.health.weight",
        [
            {"weight": 70.0, "start_time": 1, "update_time": 2, "tag_id": 3},
            {"weight": 72.0, "start_time": 4, "update_time": 5, "tag_id": 6},
        ],
    )
    assert result["events"] == 2
    assert "metrics" not in result
    assert "distributions" not in result
    assert result["fields"]["weight"]["statistics"]["mean"] == 71.0
    assert result["fields"]["start_time"]["unit"] == "ms_since_epoch"
    assert result["fields"]["tag_id"]["statistics"] == {
        "count": 2,
        "unique_count": 2,
        "values_redacted": True,
    }


def test_generic_analysis_accounts_for_every_observed_field_without_guessing_semantics():
    result = summarize_generic(
        "com.samsung.health.unknown",
        [
            {
                "start_time": 1_000,
                "value": 2.0,
                "flag": True,
                "mode": "automatic",
                "comment": "private note",
                "payload": {"nested": 3},
                "samples": [1, 2, 3],
                "missing": None,
            },
            {"start_time": 2_000, "value": 4.0, "flag": False, "mode": "manual"},
        ],
    )

    assert result["coverage"] == {
        "observed_fields": 8,
        "analyzed_fields": 8,
        "ignored_fields": [],
        "coverage_percent": 100.0,
        "officially_documented_fields": 0,
        "official_schema_convention_fields": 1,
        "apk_documented_fields": 0,
        "open_source_documented_fields": 0,
        "raw_observed_fields": 7,
        "validation": {
            "fields_with_applicable_rule": 0,
            "fields_without_encoded_rule": 1,
            "checked_values": 0,
            "unchecked_values": 2,
            "violation_count": 0,
            "relationship_rules": [],
        },
    }
    assert set(result["fields"]) == {
        "start_time",
        "value",
        "flag",
        "mode",
        "comment",
        "payload",
        "samples",
        "missing",
    }
    assert result["fields"]["value"]["statistics"] == {
        "count": 2,
        "sum": 6.0,
        "mean": 3.0,
        "population_standard_deviation": 1.0,
        "sample_standard_deviation": 1.414,
        "minimum": 2.0,
        "maximum": 4.0,
        "latest": 4.0,
    }
    assert result["fields"]["comment"]["statistics"]["values_redacted"] is True
    assert "private note" not in str(result)
    assert result["fields"]["mode"]["statistics"] == {
        "count": 2,
        "unique_count": 2,
        "values_redacted": True,
    }
    assert "automatic" not in str(result)
    assert result["fields"]["payload"]["statistics"]["object_keys"] == ["nested"]
    assert result["fields"]["samples"]["statistics"]["element_count"] == 3
    assert result["fields"]["start_time"]["provenance"]["status"] == "official_schema_convention"
    assert all(
        field["provenance"]["status"] == "raw_observed"
        for key, field in result["fields"].items()
        if key != "start_time"
    )


def test_sensitive_identifiers_and_locations_are_redacted_regardless_of_value_type():
    result = summarize_generic(
        "com.samsung.health.unknown",
        [
            {
                "tag_id": 123,
                "latitude": 47.1,
                "deviceuuid": 999,
                "location_data": {"x": 1},
            },
            {
                "tag_id": 456,
                "latitude": 47.2,
                "deviceuuid": 888,
                "location_data": {"x": 2},
            },
        ],
    )

    for key in ("tag_id", "latitude", "deviceuuid", "location_data"):
        assert result["fields"][key]["statistics"]["values_redacted"] is True
        assert "sum" not in result["fields"][key]["statistics"]
        assert "minimum" not in result["fields"][key]["statistics"]
    assert "47.1" not in str(result)


def test_generic_analysis_attaches_official_semantics_only_to_documented_fields():
    result = summarize_generic(
        "com.samsung.shealth.step_daily_trend",
        [
            {
                "count": 1234,
                "distance": 987.5,
                "calorie": 42.0,
                "source_type": -2,
                "unknown_future_field": 7,
            }
        ],
    )

    assert result["fields"]["count"]["provenance"]["status"] == "official_documentation"
    assert result["fields"]["count"]["unit"] == "step"
    assert result["fields"]["distance"]["unit"] == "m"
    assert result["fields"]["calorie"]["unit"] == "kcal"
    assert result["fields"]["source_type"]["enum"][-2] == "all_sources_deduplicated"
    assert result["fields"]["unknown_future_field"]["provenance"]["status"] == "raw_observed"
    assert result["coverage"]["officially_documented_fields"] == 4
    assert result["coverage"]["raw_observed_fields"] == 1


def test_documented_ranges_and_enums_are_validated_against_observed_account_values():
    weight = summarize_generic("com.samsung.health.weight", [{"weight": 70.0}, {"weight": 600.0}])
    stages = summarize_generic(
        "com.samsung.health.sleep_stage", [{"stage": 40003}, {"stage": 99999}]
    )

    assert weight["fields"]["weight"]["validation"] == {
        "status": "violations_found",
        "rule": {"minimum": 2.0, "maximum": 500.0},
        "checked_count": 2,
        "unchecked_count": 0,
        "violation_count": 1,
    }
    assert stages["fields"]["stage"]["validation"]["checked_count"] == 2
    assert stages["fields"]["stage"]["validation"]["violation_count"] == 1

    composition = summarize_generic(
        "com.samsung.health.weight", [{"fat_free": 95.0, "skeletal_muscle": 95.0}]
    )
    assert composition["fields"]["fat_free"]["validation"]["status"] == "valid"
    assert composition["fields"]["skeletal_muscle"]["validation"]["violation_count"] == 1


def test_apk_semantics_are_distinct_from_official_docs_and_keep_unknown_units_unknown():
    sleep = summarize_generic(
        "com.samsung.health.sleep",
        [
            {
                "efficiency": 88.0,
                "sleep_duration": 420,
                "movement_awakening": 12.5,
            }
        ],
    )
    oxygen = summarize_generic("com.samsung.health.oxygen_saturation", [{"low_duration": 30}])

    assert sleep["fields"]["efficiency"]["provenance"]["status"] == "apk_decompiled"
    assert sleep["fields"]["efficiency"]["unit"] == "percent"
    assert sleep["fields"]["sleep_duration"]["unit"] == "min"
    assert (
        sleep["fields"]["movement_awakening"]["meaning"] == "Movement-awakenings sleep score factor"
    )
    assert "unit" not in sleep["fields"]["movement_awakening"]
    assert oxygen["fields"]["low_duration"]["provenance"]["status"] == "raw_observed"
    assert sleep["coverage"]["apk_documented_fields"] == 3


def test_sleep_analysis_joins_stages_heart_rate_oxygen_and_snoring(tmp_path: Path):
    c = HealthCache(tmp_path / "h.sqlite3")
    start, end = 1_000_000, 4_600_000
    add(
        c,
        "com.samsung.health.sleep",
        "sleep",
        start_time=start,
        end_time=end,
        efficiency=80.0,
    )
    add(
        c,
        "com.samsung.health.sleep_stage",
        "a",
        sleep_id="sleep",
        start_time=start,
        end_time=start + 600_000,
        stage=40001,
    )
    add(
        c,
        "com.samsung.health.sleep_stage",
        "b",
        sleep_id="sleep",
        start_time=start + 600_000,
        end_time=start + 1_800_000,
        stage=40002,
    )
    add(
        c,
        "com.samsung.health.sleep_stage",
        "c",
        sleep_id="sleep",
        start_time=start + 1_800_000,
        end_time=start + 2_700_000,
        stage=40003,
    )
    add(
        c,
        "com.samsung.health.sleep_stage",
        "d",
        sleep_id="sleep",
        start_time=start + 2_700_000,
        end_time=end,
        stage=40004,
    )
    add(c, "com.samsung.health.heart_rate", "hr1", start_time=start + 1, heart_rate=60)
    add(c, "com.samsung.health.heart_rate", "hr2", start_time=start + 2, heart_rate=80)
    add(
        c,
        "com.samsung.health.oxygen_saturation",
        "o",
        start_time=start,
        end_time=end,
        spo2=95,
        min=90,
        low_duration=120,
    )
    add(
        c,
        "com.samsung.shealth.sleep_snoring",
        "s",
        start_time=start,
        end_time=start + 60_000,
        duration=60_000,
    )

    report = HealthAnalysisEngine(c).sleep_latest()

    assert report["time_in_bed_minutes"] == 60
    assert report["asleep_minutes"] == 50
    assert report["stages_minutes"] == {"awake": 10, "light": 20, "deep": 15, "rem": 15}
    assert report["heart_rate"]["average_bpm"] == 70.0
    assert report["oxygen"]["average_percent"] == 95.0
    assert "minimum_percent" not in report["oxygen"]
    assert "duration_minutes" not in report["snoring"]
    assert report["awake_periods_detected"] == 1
    assert "awakenings" not in report
    assert report["reported_efficiency_percent"] == 80.0
    assert "efficiency_percent" not in report
    assert (
        report["calculations"]["awake_periods_detected"]["formula"]
        == "count starts of contiguous official AWAKE blocks, including the first interval"
    )
    assert (
        report["calculations"]["awake_periods_detected"]["not_equivalent_to"]
        == "number of conscious awakenings"
    )
    assert report["calculations"]["reported_efficiency_percent"]["kind"] == "direct_account_field"
    assert "baseline_previous_nights" not in report
    assert report["baseline_previous_source_records"]["source_records"] == 0
    assert report["coverage"]["ignored_fields"] == []
    assert set(report["field_analysis"]) == {
        "com.samsung.health.sleep",
        "com.samsung.health.sleep_stage",
        "com.samsung.health.heart_rate",
        "com.samsung.health.oxygen_saturation",
        "com.samsung.shealth.sleep_snoring",
    }
    assert (
        report["field_analysis"]["com.samsung.health.oxygen_saturation"]["fields"]["low_duration"][
            "provenance"
        ]["status"]
        == "raw_observed"
    )


def test_sleep_stage_coverage_uses_interval_union_and_reports_invalid_values(
    tmp_path: Path,
):
    c = HealthCache(tmp_path / "h.sqlite3")
    start, end = 1_000_000, 4_600_000
    add(c, "com.samsung.health.sleep", "sleep", start_time=start, end_time=end)
    add(
        c,
        "com.samsung.health.sleep_stage",
        "light",
        sleep_id="sleep",
        start_time=start,
        end_time=start + 2_400_000,
        stage=40002,
    )
    add(
        c,
        "com.samsung.health.sleep_stage",
        "deep",
        sleep_id="sleep",
        start_time=start + 1_200_000,
        end_time=end,
        stage=40003,
    )
    add(
        c,
        "com.samsung.health.sleep_stage",
        "invalid",
        sleep_id="sleep",
        start_time=start,
        end_time=end,
        stage=[],
    )

    report = HealthAnalysisEngine(c).sleep_latest()

    assert report["derived_stage_coverage_percent"] == 100.0
    assert report["stage_interval_validation"] == {
        "invalid_stage_values": 1,
        "invalid_intervals": 0,
        "overlap_count": 1,
    }
    assert report["joins"]["heart_rate"]["join_kind"] == "time_window_only"


def test_activity_week_comparison_uses_one_authoritative_daily_total(tmp_path: Path):
    c = HealthCache(tmp_path / "h.sqlite3")
    # Europe/Paris midnights: 2026-08-17 and 2026-08-24 weeks.
    for idx, (ms, distance) in enumerate(
        (
            (1786917600000, 1000),
            (1787004000000, 2000),
            (1787522400000, 4000),
            (1787608800000, 5000),
        )
    ):
        add(
            c,
            "com.samsung.shealth.step_daily_trend",
            str(idx),
            day_time=ms,
            start_time=ms,
            distance=distance,
            count=distance,
            source_type=-2,
        )
    add(
        c,
        "com.samsung.shealth.step_daily_trend",
        "duplicate",
        day_time=1787522400000,
        start_time=1787522400000,
        distance=3000,
        count=3000,
        source_type=0,
    )

    report = HealthAnalysisEngine(c).activity_week(date(2026, 8, 28), compare_previous=True)

    assert report["distance_km"] == 9.0
    assert report["comparison"]["previous_distance_km"] == 3.0
    assert report["comparison"]["difference_km"] == 6.0
    assert report["days_without_authoritative_all_sources"] == 0
    assert report["calculations"]["daily_selection"]["rule"] == "source_type == -2 only"
    assert report["field_analysis"]["coverage"]["ignored_fields"] == []


def test_activity_does_not_invent_a_total_when_all_sources_record_is_missing(
    tmp_path: Path,
):
    c = HealthCache(tmp_path / "h.sqlite3")
    add(
        c,
        "com.samsung.shealth.step_daily_trend",
        "phone",
        day_time=1_000,
        start_time=1_000,
        distance=1000,
        count=1000,
        source_type=0,
    )
    add(
        c,
        "com.samsung.shealth.step_daily_trend",
        "watch",
        day_time=1_000,
        start_time=1_000,
        distance=1200,
        count=1200,
        source_type=1,
    )

    report = HealthAnalysisEngine(c).activity_interval(0, 2_000)

    assert report["days_with_data"] == 0
    assert report["days_without_authoritative_all_sources"] == 1
    assert report["steps"] == 0


def test_exercise_analysis_weights_average_heart_rate_by_duration(tmp_path: Path):
    c = HealthCache(tmp_path / "h.sqlite3")
    add(
        c,
        "com.samsung.health.exercise",
        "a",
        start_time=1,
        end_time=1001,
        duration=1000,
        mean_heart_rate=100,
        min_heart_rate=80,
        max_heart_rate=140,
        distance=1000,
    )
    add(
        c,
        "com.samsung.health.exercise",
        "b",
        start_time=2000,
        end_time=5000,
        duration=3000,
        mean_heart_rate=140,
        min_heart_rate=90,
        max_heart_rate=180,
        distance=2000,
    )

    report = HealthAnalysisEngine(c).exercise(0, 10_000)

    assert report["heart_rate"]["duration_weighted_mean_bpm"] == 130.0
    assert report["heart_rate"]["minimum_bpm"] == 80.0
    assert report["heart_rate"]["maximum_bpm"] == 180.0
    assert (
        report["calculations"]["heart_rate.duration_weighted_mean_bpm"]["formula"]
        == "sum(mean_heart_rate * duration) / sum(duration)"
    )
    assert report["field_analysis"]["coverage"]["ignored_fields"] == []
