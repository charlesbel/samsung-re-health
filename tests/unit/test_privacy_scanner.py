import sys
from pathlib import Path

# Add scripts directory to sys.path
scripts_dir = Path(__file__).parent.parent.parent / "scripts"
sys.path.insert(0, str(scripts_dir))

from verify_privacy import scan_tree  # noqa: E402


def test_privacy_scanner_detects_forbidden_content(tmp_path: Path):
    clean_file = tmp_path / "clean.py"
    clean_file.write_text("print('clean')", encoding="utf-8")

    violations = scan_tree(tmp_path)
    assert len(violations) == 0

    bad_file = tmp_path / "bad.py"
    secret_path = "".join(["/ho", "me/he", "rmes"]) + "/secret"
    bad_file.write_text(f"user_path = {secret_path!r}", encoding="utf-8")
    violations = scan_tree(tmp_path)
    assert len(violations) == 1
    assert "Forbidden string pattern" in violations[0]


def test_privacy_scanner_detects_forbidden_extensions(tmp_path: Path):
    db_file = tmp_path / "cache.sqlite3"
    db_file.write_bytes(b"sqlite-data")

    violations = scan_tree(tmp_path)
    assert len(violations) == 1
    assert "Forbidden file extension" in violations[0]
