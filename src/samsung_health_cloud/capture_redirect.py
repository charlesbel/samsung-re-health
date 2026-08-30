"""Securely capture Samsung Account OAuth redirect URIs."""

from __future__ import annotations

import sys
import urllib.parse

from .account_paths import resolve_redirect_path
from .account_storage import write_text
from .constants import REDIRECT_URI
from .exceptions import SamsungHealthCloudError


def is_expected_redirect_uri(value: str) -> bool:
    if not isinstance(value, str) or not value.startswith("ms-app://"):
        return False
    try:
        actual = urllib.parse.urlsplit(value)
        expected = urllib.parse.urlsplit(REDIRECT_URI)
    except (TypeError, ValueError):
        return False
    return (actual.scheme, actual.netloc, actual.path) == (
        expected.scheme,
        expected.netloc,
        expected.path,
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv if argv is None else argv
    if len(args) != 2 or not is_expected_redirect_uri(args[1]):
        return 2
    try:
        write_text(resolve_redirect_path(), args[1])
    except (SamsungHealthCloudError, OSError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
