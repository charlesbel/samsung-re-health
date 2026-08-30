import httpx
import pytest

from samsung_health_cloud import cli
from samsung_health_cloud.cli import _analysis_bounds, _limited, _schema_report, _validate_analysis_options, build_parser
from samsung_health_cloud.cache import HealthCache
from samsung_health_cloud.catalog import ManifestInfo


def test_cli_exposes_complete_read_only_commands():
    parser = build_parser()
    status = parser.parse_args(["status"])
    doctor = parser.parse_args(["doctor"])
    listing = parser.parse_args(["manifests", "list"])
    show = parser.parse_args(["manifests", "show", "com.samsung.health.sleep"])
    read_all = parser.parse_args(
        ["read", "com.samsung.health.step_count", "--all", "--format", "jsonl", "--since", "2026-01-01"]
    )
    export = parser.parse_args(
        ["export", "com.samsung.health.sleep", "--output", "/tmp/sleep.jsonl", "--until", "2026-12-31"]
    )
    export_all = parser.parse_args(["export-all", "--output-dir", "/tmp/health"])
    documents = parser.parse_args(
        ["documents", "com.samsung.health.step_count", "--schema-revision", "5", "--limit", "1"]
    )
    summary = parser.parse_args(["summary", "2026-08-28"])
    steps = parser.parse_args(["steps", "2026-08-28"])
    sleep = parser.parse_args(["sleep", "2026-08-28"])
    heart_rate = parser.parse_args(["heart-rate", "2026-08-28"])
    weight = parser.parse_args(["weight"])
    sync = parser.parse_args(["sync", "--days", "30", "--force"])
    cache_status = parser.parse_args(["cache-status"])
    types = parser.parse_args(["types", "sleep"])
    data = parser.parse_args(["data", "exercise", "--since", "2026-01-01", "--limit", "50", "--offset", "100"])
    inventory = parser.parse_args(["inventory", "exercise"])
    schema = parser.parse_args(["schema", "sleep"])
    analyze_sleep = parser.parse_args(["analyze", "sleep", "--latest", "--no-sync"])
    analyze_week = parser.parse_args(["analyze", "activity", "--period", "week", "--compare", "previous"])
    analyze_exercise = parser.parse_args(["analyze", "exercise", "--all-history"])

    assert status.command == "status"
    assert doctor.command == "doctor"
    assert listing.manifests_command == "list"
    assert show.manifest_id == "com.samsung.health.sleep"
    assert read_all.all is True
    assert read_all.format == "jsonl"
    assert read_all.since == "2026-01-01"
    assert str(export.output) == "/tmp/sleep.jsonl"
    assert export.until == "2026-12-31"
    assert str(export_all.output_dir) == "/tmp/health"
    assert documents.schema_revision == 5
    assert summary.day == "2026-08-28"
    assert steps.command == "steps"
    assert sleep.command == "sleep"
    assert heart_rate.command == "heart-rate"
    assert weight.command == "weight"
    assert sync.days == 30 and sync.force is True
    assert cache_status.command == "cache-status"
    assert types.filter == "sleep"
    assert data.query == "exercise" and data.limit == 50 and data.offset == 100
    assert inventory.query == "exercise"
    assert schema.query == "sleep"
    assert analyze_sleep.latest and analyze_sleep.no_sync
    assert analyze_week.period == "week" and analyze_week.compare == "previous"
    assert analyze_exercise.all_history
    help_text = parser.format_help()
    assert "upsert" not in help_text
    assert "delete" not in help_text
    assert "deregister" not in help_text


def test_schema_report_proves_every_account_field_has_semantics_or_neutral_fallback(tmp_path):
    cache = HealthCache(tmp_path / "health.sqlite3")
    cache.upsert_documents("com.samsung.health.weight", [{
        "data": {"datauuid": "a", "start_time": 1, "weight": 70.0, "future": 9},
        "files": [], "downloadUrls": [], "needToDecrypt": False,
    }])
    manifests = [ManifestInfo("com.samsung.health.weight", 1, 1)]

    report = _schema_report(cache, manifests, None)

    assert report["observed_manifest_fields"] == 4
    assert report["officially_documented_manifest_fields"] == 2
    assert report["official_schema_convention_manifest_fields"] == 1
    assert report["raw_fallback_manifest_fields"] == 1
    assert report["ignored_fields"] == 0
    assert report["coverage_percent"] == 100.0


def test_analysis_rejects_an_inverted_explicit_interval():
    args = build_parser().parse_args([
        "analyze", "weight", "--since", "2026-08-02", "--until", "2026-08-01",
    ])

    with pytest.raises(ValueError, match="since must not be after until"):
        _analysis_bounds(args)


def test_analysis_rejects_options_that_a_specialized_analyzer_would_ignore():
    sleep = build_parser().parse_args(["analyze", "sleep", "--period", "week"])
    exercise = build_parser().parse_args(["analyze", "exercise", "--latest"])
    generic = build_parser().parse_args(["analyze", "weight", "--latest", "--since", "2026-01-01"])

    with pytest.raises(ValueError, match="sleep analysis only supports --latest"):
        _validate_analysis_options(sleep, "sleep")
    with pytest.raises(ValueError, match="--latest is not supported for exercise"):
        _validate_analysis_options(exercise, "exercise")
    with pytest.raises(ValueError, match="--latest cannot be combined"):
        _validate_analysis_options(generic, "weight")


def test_limited_does_not_consume_an_extra_cloud_record():
    consumed = []

    def records():
        for value in range(4):
            consumed.append(value)
            yield {"value": value}

    assert list(_limited(records(), 2)) == [{"value": 0}, {"value": 1}]
    assert consumed == [0, 1]


def test_cli_redacts_network_exception_details(monkeypatch, capsys):
    def fail_catalog(client, args):
        raise httpx.ConnectError("request URL contained secret-material")

    monkeypatch.setattr(cli, "_catalog", fail_catalog)
    result = cli.main(["manifests", "list"])
    captured = capsys.readouterr()
    assert result == 2
    assert "network request failed" in captured.err
    assert "secret-material" not in captured.err


def test_status_reports_corrupt_state_without_traceback(tmp_path, capsys):
    state = tmp_path / "state.json"
    state.write_text("not-json")
    state.chmod(0o600)
    result = cli.main(["--state", str(state), "status"])
    captured = capsys.readouterr()
    assert result == 2
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
