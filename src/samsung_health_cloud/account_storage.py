from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

from .exceptions import SamsungHealthCloudError
from .file_lock import SidecarLock, secure_atomic_write, secure_read_file


def _absolute_lexical(path: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(path))))


def verify_no_symlink_components(path: str | Path) -> Path:
    target = _absolute_lexical(path)
    current = target
    while True:
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise SamsungHealthCloudError(
                f"cannot verify secure path component: {current}"
            ) from exc
        else:
            if stat.S_ISLNK(mode):
                raise SamsungHealthCloudError(
                    f"symlinks are forbidden in account state path: {current}"
                )
        if current == current.parent:
            break
        current = current.parent
    return target


def write_json(path: str | Path, value: dict[str, Any]) -> None:
    target = verify_no_symlink_components(path)
    secure_atomic_write(
        target,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        sidecar_lock_path=target.with_name(f"{target.name}.lock"),
        file_mode=0o600,
        dir_mode=0o700,
    )


def write_text(path: str | Path, value: str) -> None:
    target = verify_no_symlink_components(path)
    secure_atomic_write(
        target,
        value,
        sidecar_lock_path=target.with_name(f"{target.name}.lock"),
        file_mode=0o600,
        dir_mode=0o700,
    )


def read_json(path: str | Path) -> dict[str, Any]:
    target = verify_no_symlink_components(path)
    content = secure_read_file(
        target,
        sidecar_lock_path=target.with_name(f"{target.name}.lock"),
        require_private=True,
    )
    try:
        value = json.loads(content)
    except ValueError as exc:
        raise SamsungHealthCloudError(f"invalid JSON in {target.name}") from exc
    if not isinstance(value, dict):
        raise SamsungHealthCloudError(f"invalid object structure in {target.name}")
    return value


def consume_text(path: str | Path) -> str:
    target = verify_no_symlink_components(path)
    lock_path = target.with_name(f"{target.name}.lock")
    with SidecarLock(lock_path, exclusive=True):
        content = secure_read_file(target, require_private=True)
        try:
            target.unlink()
        except OSError as exc:
            raise SamsungHealthCloudError(f"unable to consume {target.name}") from exc
    return content.strip()


def secure_unlink(path: str | Path) -> None:
    target = verify_no_symlink_components(path)
    lock_path = target.with_name(f"{target.name}.lock")
    with SidecarLock(lock_path, exclusive=True):
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise SamsungHealthCloudError(f"unable to remove {target.name}") from exc
