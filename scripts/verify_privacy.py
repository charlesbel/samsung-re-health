#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

# Construct forbidden patterns dynamically to avoid self-matching
_MAINTAINER_NAME = "".join(["her", "mes"])
_MAINTAINER_HOME = "".join(["/ho", "me/", _MAINTAINER_NAME])
_PERSONAL_EMAIL = "".join(["char", "les@"])
_FORBIDDEN_MODELS = ["".join(["SM-S", "928B"]), "".join(["SM-S", "938B"])]

FORBIDDEN_REGEXES = [
    re.compile(re.escape(_MAINTAINER_HOME)),
    re.compile(re.escape(_PERSONAL_EMAIL), re.IGNORECASE),
] + [re.compile(re.escape(m)) for m in _FORBIDDEN_MODELS]

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


def scan_git_history(repo_root: Path) -> list[str]:
    violations = []
    try:
        res = subprocess.run(
            ["git", "log", "-p", "-n", "50", "--", "."],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout:
            # Check commit messages and diff additions
            added_lines = [
                line[1:]
                for line in res.stdout.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            ]
            for line in added_lines:
                for pat in FORBIDDEN_REGEXES:
                    if pat.search(line):
                        violations.append(
                            "Forbidden string pattern found in recent git history diff"
                        )
                        return violations
    except Exception as exc:  # noqa: BLE001
        violations.append(f"Failed to scan git history: {exc}")
    return violations


def scan_archives(dist_dir: Path) -> list[str]:
    violations = []
    sdists = list(dist_dir.glob("*.tar.gz"))
    wheels = list(dist_dir.glob("*.whl"))

    for sdist in sdists:
        try:
            with tarfile.open(sdist, "r:gz") as tf:
                members = tf.getmembers()
                names = [m.name for m in members]
                has_skills = any(".skills" in name for name in names)
                if not has_skills:
                    violations.append(f"sdist {sdist.name} must include .skills/ documentation")
                for m in members:
                    name = m.name
                    if any(name.endswith(ext) for ext in FORBIDDEN_EXTENSIONS):
                        violations.append(f"sdist {sdist.name} contains forbidden file: {name}")
                    if (
                        ".agy" in name
                        or ".git/" in name
                        or name.endswith("/.git")
                        or name == ".git"
                    ):
                        violations.append(f"sdist {sdist.name} contains internal directory: {name}")
                    # Check text content of archive files
                    if any(name.endswith(ext) for ext in SCANNED_EXTENSIONS) and m.isfile():
                        fileobj = tf.extractfile(m)
                        if fileobj:
                            text_content = fileobj.read().decode("utf-8", errors="ignore")
                            for pat in FORBIDDEN_REGEXES:
                                if pat.search(text_content):
                                    violations.append(
                                        f"sdist {sdist.name} file {name} contains forbidden string pattern"
                                    )
                                    break
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
                    # Check text content of archive files
                    if any(name.endswith(ext) for ext in SCANNED_EXTENSIONS):
                        with zf.open(name, "r") as f:
                            text_content = f.read().decode("utf-8", errors="ignore")
                            for pat in FORBIDDEN_REGEXES:
                                if pat.search(text_content):
                                    violations.append(
                                        f"wheel {wheel.name} file {name} contains forbidden string pattern"
                                    )
                                    break
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
