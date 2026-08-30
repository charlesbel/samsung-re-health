#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import tarfile
import zipfile
from pathlib import Path

# Construct forbidden patterns dynamically to avoid self-matching
_MAINTAINER_NAME = "".join(["her", "mes"])
_MAINTAINER_HOME = "".join(["/ho", "me/", _MAINTAINER_NAME])
_PERSONAL_EMAIL = "".join(["char", "les@"])

FORBIDDEN_REGEXES = [
    re.compile(re.escape(_MAINTAINER_HOME)),
    re.compile(re.escape(_PERSONAL_EMAIL), re.IGNORECASE),
]

FORBIDDEN_EXTENSIONS = {
    ".apk",
    ".jadx",
    ".dex",
    ".sqlite3",
    ".db",
    ".pcap",
}

SCANNED_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".txt",
    ".sh",
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    ".agy",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}


def scan_tree(root_dir: Path) -> list[str]:
    violations = []
    for root, dirs, files in os.walk(root_dir):
        # Skip ignored directories in place
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for fname in files:
            fpath = Path(root) / fname
            rel_path = fpath.relative_to(root_dir)

            # Check forbidden file extensions
            if fpath.suffix.lower() in FORBIDDEN_EXTENSIONS:
                violations.append(f"Forbidden file extension: {rel_path}")
                continue

            # Check content of text files
            if fpath.suffix.lower() in SCANNED_EXTENSIONS:
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                except Exception as exc:  # noqa: BLE001
                    violations.append(f"Cannot read file {rel_path}: {exc}")
                    continue

                for pat in FORBIDDEN_REGEXES:
                    if pat.search(content):
                        violations.append(f"Forbidden string pattern found in {rel_path}")
                        break

    return violations


def scan_archives(dist_dir: Path) -> list[str]:
    violations = []
    sdists = list(dist_dir.glob("*.tar.gz"))
    wheels = list(dist_dir.glob("*.whl"))

    for sdist in sdists:
        try:
            with tarfile.open(sdist, "r:gz") as tf:
                names = tf.getnames()
                has_skills = any(".skills" in name for name in names)
                if not has_skills:
                    violations.append(f"sdist {sdist.name} must include .skills/ documentation")
                for name in names:
                    if any(name.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
                        violations.append(f"sdist {sdist.name} contains forbidden file: {name}")
                    if (
                        ".agy" in name
                        or ".git/" in name
                        or name.endswith("/.git")
                        or name == ".git"
                    ):
                        violations.append(f"sdist {sdist.name} contains internal directory: {name}")
        except Exception as exc:  # noqa: BLE001
            violations.append(f"Failed to inspect sdist {sdist}: {exc}")

    for wheel in wheels:
        try:
            with zipfile.ZipFile(wheel, "r") as zf:
                names = zf.namelist()
                has_skills = any(".skills" in name for name in names)
                if has_skills:
                    violations.append(f"wheel {wheel.name} must NOT include .skills/ directory")
                for name in names:
                    if any(name.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
                        violations.append(f"wheel {wheel.name} contains forbidden file: {name}")
                    if (
                        ".agy" in name
                        or ".git/" in name
                        or name.endswith("/.git")
                        or name == ".git"
                    ):
                        violations.append(f"wheel {wheel.name} contains internal directory: {name}")
        except Exception as exc:  # noqa: BLE001
            violations.append(f"Failed to inspect wheel {wheel}: {exc}")

    return violations


def main() -> int:
    repo_root = Path(__file__).parent.parent
    violations = scan_tree(repo_root)

    dist_path = repo_root / "dist"
    if dist_path.exists():
        archive_violations = scan_archives(dist_path)
        violations.extend(archive_violations)

    if violations:
        print(f"FAILED: Found {len(violations)} privacy/archive violation(s):", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("SUCCESS: Tree and archive privacy scan completely clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
