from __future__ import annotations

import os
from pathlib import Path

from .account_storage import verify_no_symlink_components
from .credentials import default_master_state_path


def resolve_account_master_path(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return verify_no_symlink_components(explicit)
    configured = os.environ.get("SAMSUNG_ACCOUNT_MASTER_STATE")
    return verify_no_symlink_components(configured or default_master_state_path())


def resolve_pending_path(master_path: str | Path | None = None) -> Path:
    configured = os.environ.get("SAMSUNG_ACCOUNT_PENDING_PATH")
    master = resolve_account_master_path(master_path)
    return verify_no_symlink_components(configured or master.parent / "pending.json")


def resolve_redirect_path(master_path: str | Path | None = None) -> Path:
    configured = os.environ.get("SAMSUNG_ACCOUNT_REDIRECT_PATH")
    master = resolve_account_master_path(master_path)
    return verify_no_symlink_components(configured or master.parent / "redirect.uri")
