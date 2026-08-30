"""Field semantics backed by explicit, reviewable sources.

Manifest-specific definitions take priority. Samsung's documented common
measurement fields are then matched by exact field name across manifests.
Unknown fields deliberately keep raw names and receive neutral statistics
instead of inferred medical meaning.
"""

from __future__ import annotations

COMMON = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Common.html"
SESSION = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.SessionMeasurement.html"
SLEEP = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Sleep.html"
SLEEP_STAGE = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.SleepStage.html"
HEART_RATE = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.HeartRate.html"
OXYGEN = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.OxygenSaturation.html"
EXERCISE = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Exercise.html"
STEPS = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.StepDailyTrend.html"
WEIGHT = "https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Weight.html"


def _official(
    meaning: str,
    source: str,
    *,
    unit: str | None = None,
    enum: dict[int, str] | None = None,
    enum_exhaustive: bool = True,
    valid_range: tuple[float | None, float | None] | None = None,
    max_length: int | None = None,
) -> dict:
    result: dict[str, object] = {
        "meaning": meaning,
        "provenance": {
            "status": "official_documentation",
            "source": source,
        },
    }
    if unit is not None:
        result["unit"] = unit
    if enum is not None:
        result["enum"] = enum
        result["enum_exhaustive"] = enum_exhaustive
    if valid_range is not None:
        result["valid_range"] = {"minimum": valid_range[0], "maximum": valid_range[1]}
    if max_length is not None:
        result["max_length"] = max_length
    return result


def _apk(meaning: str, source: str, *, unit: str | None = None, enum: dict[int, str] | None = None) -> dict:
    result: dict[str, object] = {
        "meaning": meaning,
        "provenance": {
            "status": "apk_decompiled",
            "source": source,
            "apk_version": "7.00.6.003",
            "apk_sha256": "a778cb804a4c0ad03d540d027fb3d473d2b54451468fb03f32f6c457831e3554",
            "caveat": "JADX output is reconstructed; important semantics require a clear call path.",
        },
    }
    if unit is not None:
        result["unit"] = unit
    if enum is not None:
        result["enum"] = enum
    return result


def _convention(meaning: str, source: str, *, unit: str | None = None) -> dict:
    result: dict[str, object] = {
        "meaning": meaning,
        "provenance": {
            "status": "official_schema_convention",
            "source": source,
            "caveat": "Samsung documents this common field name, but this private manifest's formal inheritance is not public.",
        },
    }
    if unit is not None:
        result["unit"] = unit
    return result


APK_SLEEP_ITEM = "/home/hermes/projects/samsung-health-research/apk/jadx-7006003/sources/classes/sources/com/samsung/android/app/shealth/sleep/data/SleepItem.java"
APK_SCORE_FACTORS = "/home/hermes/projects/samsung-health-research/apk/jadx-7006003/sources/classes4/sources/com/samsung/android/app/shealth/sleep/data/ScoreFactors.java"
APK_SCORE_MAPPING = f"{APK_SLEEP_ITEM}#L145-L179 + {APK_SCORE_FACTORS}#L179-L193"


SEMANTICS: dict[tuple[str, str], dict] = {
    # Sleep: the official legacy API documents these exact temporal fields.
    ("com.samsung.health.sleep", "start_time"): _official("UTC measurement start (user goes to bed)", SLEEP, unit="ms_since_epoch"),
    ("com.samsung.health.sleep", "end_time"): _official("UTC measurement end (user wakes up)", SLEEP, unit="ms_since_epoch"),
    ("com.samsung.health.sleep", "time_offset"): _official("Time-zone and daylight-saving offset", SESSION, unit="ms"),
    ("com.samsung.health.sleep", "efficiency"): _apk("Samsung Health sleep efficiency used as a percentage in actual-sleep-time calculation", f"{APK_SLEEP_ITEM}#L211-L213", unit="percent"),
    ("com.samsung.health.sleep", "sleep_duration"): _apk("Sleep-duration score factor converted from minutes to milliseconds by the app", f"{APK_SLEEP_ITEM}#L315-L333", unit="min"),
    ("com.samsung.health.sleep", "movement_awakening"): _apk("Movement-awakenings sleep score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "physical_recovery"): _apk("Physical-recovery sleep score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "mental_recovery"): _apk("Mental-recovery sleep score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "sleep_cycle"): _apk("Sleep-cycle count score factor", APK_SCORE_MAPPING, unit="count"),
    ("com.samsung.health.sleep", "factor_01"): _apk("First-cycle deep-sleep score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_02"): _apk("Total deep-sleep score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_03"): _apk("First-cycle awake score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_04"): _apk("Awake-in-REM score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_05"): _apk("Total-awake score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_06"): _apk("Sleep-time score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_07"): _apk("First-cycle-duration score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_08"): _apk("Wake-after-sleep-onset-in-REM score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_09"): _apk("Total wake-after-sleep-onset score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "factor_10"): _apk("Sleep-latency score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "total_rem_duration"): _apk("Total REM-duration score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "total_light_duration"): _apk("Total light-sleep-duration score factor", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "deep_score"): _apk("Deep-sleep component score", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "rem_score"): _apk("REM component score", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "wake_score"): _apk("Awake/restfulness component score", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "latency_score"): _apk("Sleep-latency component score", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "total_sleep_time_score"): _apk("Total-sleep-time component score", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "deep_weight"): _apk("Deep-sleep score weight", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "rem_weight"): _apk("REM score weight", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "wake_weight"): _apk("Awake/restfulness score weight", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "latency_weight"): _apk("Sleep-latency score weight", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "total_sleep_time_weight"): _apk("Total-sleep-time score weight", APK_SCORE_MAPPING),
    ("com.samsung.health.sleep", "sleep_efficiency_with_latency"): _apk("Sleep-efficiency-with-latency score factor", APK_SCORE_MAPPING),
    # Sleep stages and their official numeric constants.
    ("com.samsung.health.sleep_stage", "start_time"): _official("UTC sleep-stage interval start", SLEEP_STAGE, unit="ms_since_epoch"),
    ("com.samsung.health.sleep_stage", "end_time"): _official("UTC sleep-stage interval end", SLEEP_STAGE, unit="ms_since_epoch"),
    ("com.samsung.health.sleep_stage", "time_offset"): _official("Time-zone and daylight-saving offset", SLEEP_STAGE, unit="ms"),
    ("com.samsung.health.sleep_stage", "sleep_id"): _official("Identifier of the parent sleep record", SLEEP_STAGE),
    ("com.samsung.health.sleep_stage", "stage"): _official(
        "Sleep stage assigned to this interval",
        SLEEP_STAGE,
        enum={40001: "awake", 40002: "light", 40003: "deep", 40004: "rem"},
    ),
    # Daily steps. SOURCE_TYPE_ALL (-2) is Samsung's deduplicated all-source total.
    ("com.samsung.shealth.step_daily_trend", "day_time"): _official("UTC midnight of the summarized day", STEPS, unit="ms_since_epoch"),
    ("com.samsung.shealth.step_daily_trend", "count"): _official("Total daily step count", STEPS, unit="step"),
    ("com.samsung.shealth.step_daily_trend", "distance"): _official("Total distance for daily steps", STEPS, unit="m"),
    ("com.samsung.shealth.step_daily_trend", "calorie"): _official("Total calories burned for daily steps", STEPS, unit="kcal"),
    ("com.samsung.shealth.step_daily_trend", "speed"): _official("Average speed of daily steps", STEPS, unit="m/s"),
    ("com.samsung.shealth.step_daily_trend", "source_pkg_name"): _official("Package providing the step data", STEPS),
    ("com.samsung.shealth.step_daily_trend", "source_type"): _official(
        "Kind of step-data source",
        STEPS,
        enum={-2: "all_sources_deduplicated", -1: "partner_app", 0: "phone_only"},
        enum_exhaustive=False,
    ),
    ("com.samsung.shealth.step_daily_trend", "binning_data"): _official("ZIP-compressed JSON with 10-minute step bins", STEPS),
    # Heart rate.
    ("com.samsung.health.heart_rate", "start_time"): _official("UTC measurement start", HEART_RATE, unit="ms_since_epoch"),
    ("com.samsung.health.heart_rate", "end_time"): _official("UTC measurement end", HEART_RATE, unit="ms_since_epoch"),
    ("com.samsung.health.heart_rate", "heart_rate"): _official("Heart-rate value", HEART_RATE, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.heart_rate", "heart_beat_count"): _official("Total heartbeat count during measurement", HEART_RATE, unit="beat", valid_range=(0.0, None)),
    ("com.samsung.health.heart_rate", "min"): _official("Minimum value represented in binning_data", HEART_RATE, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.heart_rate", "max"): _official("Maximum value represented in binning_data", HEART_RATE, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.heart_rate", "binning_data"): _official("Binned heart-rate measurement payload", HEART_RATE),
    ("com.samsung.health.heart_rate", "comment"): _official("Comment for the measurement", HEART_RATE, max_length=255),
    # Oxygen saturation. Only fields explicitly covered by Samsung are marked.
    ("com.samsung.health.oxygen_saturation", "start_time"): _official("UTC measurement start", OXYGEN, unit="ms_since_epoch"),
    ("com.samsung.health.oxygen_saturation", "end_time"): _official("UTC measurement end", OXYGEN, unit="ms_since_epoch"),
    ("com.samsung.health.oxygen_saturation", "spo2"): _official("Oxygen saturation value", OXYGEN, unit="percent", valid_range=(0.0, 100.0)),
    ("com.samsung.health.oxygen_saturation", "heart_rate"): _official("Heart-rate value associated with the measurement", OXYGEN, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.oxygen_saturation", "comment"): _official("Comment for the measurement", OXYGEN, max_length=255),
    # Exercise core measures.
    ("com.samsung.health.exercise", "start_time"): _official("UTC exercise start", EXERCISE, unit="ms_since_epoch"),
    ("com.samsung.health.exercise", "end_time"): _official("UTC exercise end", EXERCISE, unit="ms_since_epoch"),
    ("com.samsung.health.exercise", "duration"): _official("Exercise duration", EXERCISE, unit="ms"),
    ("com.samsung.health.exercise", "distance"): _official("Distance covered during exercise", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "calorie"): _official("Calories burned during exercise", EXERCISE, unit="kcal"),
    ("com.samsung.health.exercise", "mean_heart_rate"): _official("Mean heart rate", EXERCISE, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.exercise", "min_heart_rate"): _official("Minimum heart rate", EXERCISE, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.exercise", "max_heart_rate"): _official("Maximum heart rate", EXERCISE, unit="bpm", valid_range=(0.0, 300.0)),
    ("com.samsung.health.exercise", "altitude_gain"): _official("Increased altitude during activity", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "altitude_loss"): _official("Decreased altitude during activity", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "incline_distance"): _official("Uphill distance during activity", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "decline_distance"): _official("Downhill distance during activity", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "mean_cadence"): _official("Mean cadence", EXERCISE, unit="count/min"),
    ("com.samsung.health.exercise", "max_cadence"): _official("Maximum cadence", EXERCISE, unit="count/min"),
    ("com.samsung.health.exercise", "exercise_type"): _official("Predefined exercise type", EXERCISE),
    ("com.samsung.health.exercise", "count"): _official("Count of a repetitive action", EXERCISE, unit="count"),
    ("com.samsung.health.exercise", "count_type"): _official("Type of repetitive-action count", EXERCISE),
    ("com.samsung.health.exercise", "max_speed"): _official("Maximum speed", EXERCISE, unit="m/s"),
    ("com.samsung.health.exercise", "mean_speed"): _official("Mean speed", EXERCISE, unit="m/s"),
    ("com.samsung.health.exercise", "max_altitude"): _official("Maximum altitude", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "min_altitude"): _official("Minimum altitude", EXERCISE, unit="m"),
    ("com.samsung.health.exercise", "max_power"): _official("Maximum power", EXERCISE, unit="W"),
    ("com.samsung.health.exercise", "mean_power"): _official("Mean power", EXERCISE, unit="W"),
    ("com.samsung.health.exercise", "max_rpm"): _official("Maximum revolutions per minute", EXERCISE, unit="rpm"),
    ("com.samsung.health.exercise", "mean_rpm"): _official("Mean revolutions per minute", EXERCISE, unit="rpm"),
    ("com.samsung.health.exercise", "live_data"): _official("Compressed JSON live measurements recorded during exercise", EXERCISE),
    ("com.samsung.health.exercise", "location_data"): _official("Compressed JSON trajectory data recorded during exercise", EXERCISE),
    ("com.samsung.health.exercise", "vo2_max"): _official("Maximal oxygen consumption during exercise", EXERCISE),
    ("com.samsung.health.exercise", "comment"): _official("Comment attached to the exercise", EXERCISE, max_length=255),
    ("com.samsung.health.exercise", "additional"): _official("Additional exercise detail payload", EXERCISE),
    # Weight and body composition.
    ("com.samsung.health.weight", "start_time"): _official("UTC measurement time", WEIGHT, unit="ms_since_epoch"),
    ("com.samsung.health.weight", "time_offset"): _official("Time-zone and daylight-saving offset", WEIGHT, unit="ms"),
    ("com.samsung.health.weight", "weight"): _official("Measured weight", WEIGHT, unit="kg", valid_range=(2.0, 500.0)),
    ("com.samsung.health.weight", "height"): _official("Height", WEIGHT, unit="cm", valid_range=(20.0, 300.0)),
    ("com.samsung.health.weight", "body_fat"): _official("Body-fat ratio", WEIGHT, unit="percent", valid_range=(1.0, 75.0)),
    ("com.samsung.health.weight", "body_fat_mass"): _official("Body-fat mass", WEIGHT, unit="kg", valid_range=(2.0, 500.0)),
    ("com.samsung.health.weight", "muscle_mass"): _official("Muscle-mass ratio", WEIGHT, unit="percent", valid_range=(10.0, 99.0)),
    ("com.samsung.health.weight", "fat_free"): _official("Fat-free ratio", WEIGHT, unit="percent", valid_range=(0.0, 100.0)),
    ("com.samsung.health.weight", "fat_free_mass"): _official("Fat-free mass", WEIGHT, unit="kg", valid_range=(2.0, 500.0)),
    ("com.samsung.health.weight", "skeletal_muscle"): _official("Skeletal-muscle ratio", WEIGHT, unit="percent", valid_range=(5.0, 90.0)),
    ("com.samsung.health.weight", "skeletal_muscle_mass"): _official("Skeletal-muscle mass", WEIGHT, unit="kg", valid_range=(2.0, 500.0)),
    ("com.samsung.health.weight", "total_body_water"): _official("Total body water", WEIGHT, unit="L", valid_range=(2.0, 500.0)),
    ("com.samsung.health.weight", "basal_metabolic_rate"): _official("Basal metabolic rate", WEIGHT, unit="kcal/day", valid_range=(100.0, 10_000.0)),
    ("com.samsung.health.weight", "comment"): _official("Comment for the measurement", WEIGHT, max_length=255),
}


# Samsung documents these names in its Common/Discrete/Session contracts.
# Private Cloud manifests reuse them, but unpublished inheritance is not assumed;
# they therefore use the separate official_schema_convention status.
COMMON_SEMANTICS: dict[str, dict] = {
    "datauuid": _convention("Unique record identifier", COMMON),
    "create_time": _convention("UTC record creation time", COMMON, unit="ms_since_epoch"),
    "update_time": _convention("UTC record last-update time", COMMON, unit="ms_since_epoch"),
    "pkg_name": _convention("Package that supplied the record", COMMON),
    "deviceuuid": _convention("Device identifier associated with the record", COMMON),
    "start_time": _convention("UTC measurement start time", SESSION, unit="ms_since_epoch"),
    "end_time": _convention("UTC measurement end time", SESSION, unit="ms_since_epoch"),
    "time_offset": _convention("Time-zone and daylight-saving offset", SESSION, unit="ms"),
}


def field_semantics(manifest_id: str, field: str) -> dict | None:
    """Return an independently reviewable exact-match semantic definition."""
    definition = SEMANTICS.get((manifest_id, field)) or COMMON_SEMANTICS.get(field)
    return dict(definition) if definition is not None else None
