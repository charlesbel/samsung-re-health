from __future__ import annotations

import contextlib
import os
import stat
import tempfile
import threading
from pathlib import Path

from .exceptions import SamsungHealthCloudError

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

__all__ = [
    "InterprocessLock",
    "SidecarLock",
    "secure_atomic_write",
    "secure_read_file",
    "verify_directory_security",
]


class _ThreadLockRegistry(threading.local):
    def __init__(self) -> None:
        super().__init__()
        # Map canonical lock path string to dict of {exclusive: bool, depth: int, fd: int}
        self.held: dict[str, dict[str, object]] = {}


_LOCK_STATE = _ThreadLockRegistry()


def verify_directory_security(parent: Path, *, create_if_missing: bool = True) -> None:
    """Verify that parent directory is a secure, non-symlink, user-owned, 0700 directory on POSIX."""
    if parent.is_symlink():
        raise SamsungHealthCloudError(f"parent directory must not be a symlink: {parent}")

    if not parent.exists():
        if create_if_missing:
            parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if os.name != "nt":
                with contextlib.suppress(OSError):
                    parent.chmod(0o700)
            return
        raise SamsungHealthCloudError(f"parent directory does not exist: {parent}")

    # Inspect existing directory without following symlinks where possible
    try:
        st = parent.stat()
    except OSError as exc:
        raise SamsungHealthCloudError(f"cannot inspect parent directory {parent}") from exc

    if not stat.S_ISDIR(st.st_mode):
        raise SamsungHealthCloudError(f"parent path is not a directory: {parent}")

    if hasattr(os, "getuid") and st.st_uid != os.getuid():
        raise SamsungHealthCloudError(f"parent directory owner uid mismatch: {parent}")

    if os.name != "nt" and (stat.S_IMODE(st.st_mode) & 0o077 != 0):
        raise SamsungHealthCloudError(
            f"parent directory permissions must be private (0700), found {oct(stat.S_IMODE(st.st_mode))}: {parent}"
        )


class InterprocessLock:
    """Low-level interprocess lock on a specific file descriptor."""

    def __init__(self, fd: int, exclusive: bool = True) -> None:
        self.fd = fd
        self.exclusive = exclusive
        self._locked = False

    def acquire(self) -> None:
        if fcntl is not None:
            flags = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
            fcntl.flock(self.fd, flags)
            self._locked = True
        elif msvcrt is not None:
            try:
                msvcrt.locking(self.fd, msvcrt.LK_LOCK, 1)
                self._locked = True
            except OSError as exc:
                raise SamsungHealthCloudError("unable to acquire Windows file lock") from exc
        else:
            raise SamsungHealthCloudError("no platform file locking mechanism available")

    def release(self) -> None:
        if not self._locked:
            return
        if fcntl is not None:
            with contextlib.suppress(OSError):
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            self._locked = False
        elif msvcrt is not None:
            with contextlib.suppress(OSError):
                msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
            self._locked = False

    def __enter__(self) -> InterprocessLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.release()


class SidecarLock:
    """Reentrant per-thread stable sidecar lock coordination on `<target>.lock`."""

    def __init__(self, lock_path: Path, exclusive: bool = True) -> None:
        self.lock_path = lock_path
        self.exclusive = exclusive
        self._key = str(lock_path.resolve()) if lock_path.is_absolute() else str(lock_path)
        self._fd: int | None = None
        self._ip_lock: InterprocessLock | None = None
        self._reentrant = False

    def acquire(self) -> None:
        held = _LOCK_STATE.held.get(self._key)
        if held is not None:
            # Current thread already holds a lock on this file
            held_exclusive = held["exclusive"]
            if held_exclusive or (not self.exclusive and not held_exclusive):
                held["depth"] = int(held["depth"]) + 1
                self._reentrant = True
                return

        # Acquire real underlying sidecar lock
        verify_directory_security(self.lock_path.parent, create_if_missing=True)

        if self.lock_path.is_symlink():
            raise SamsungHealthCloudError(f"lock file must not be a symlink: {self.lock_path}")

        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC

        try:
            fd = os.open(self.lock_path, flags, 0o600)
        except OSError as exc:
            raise SamsungHealthCloudError(f"cannot open sidecar lock {self.lock_path}") from exc

        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise SamsungHealthCloudError(
                    f"lock target is not a regular file: {self.lock_path}"
                )
            if hasattr(os, "getuid") and st.st_uid != os.getuid():
                raise SamsungHealthCloudError(f"lock file owner mismatch: {self.lock_path}")
            if os.name != "nt" and (stat.S_IMODE(st.st_mode) & 0o077 != 0):
                raise SamsungHealthCloudError(
                    f"lock file permissions must be private (0600), found {oct(stat.S_IMODE(st.st_mode))}: {self.lock_path}"
                )

            ip_lock = InterprocessLock(fd, exclusive=self.exclusive)
            ip_lock.acquire()
            self._fd = fd
            self._ip_lock = ip_lock
            _LOCK_STATE.held[self._key] = {
                "exclusive": self.exclusive,
                "depth": 1,
                "fd": fd,
                "lock": ip_lock,
            }
        except Exception:
            os.close(fd)
            raise

    def release(self) -> None:
        held = _LOCK_STATE.held.get(self._key)
        if held is None:
            return

        if self._reentrant:
            held["depth"] = int(held["depth"]) - 1
            if held["depth"] <= 0:
                del _LOCK_STATE.held[self._key]
            self._reentrant = False
            return

        held["depth"] = int(held["depth"]) - 1
        if held["depth"] <= 0:
            if self._ip_lock is not None:
                self._ip_lock.release()
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            _LOCK_STATE.held.pop(self._key, None)

    def __enter__(self) -> SidecarLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.release()


def secure_read_file(
    path: Path,
    *,
    sidecar_lock_path: Path | None = None,
    require_private: bool = True,
) -> str:
    """Safely open, verify ownership/permissions, and read file under stable sidecar coordination."""
    if sidecar_lock_path is not None:
        with SidecarLock(sidecar_lock_path, exclusive=False):
            return secure_read_file(path, sidecar_lock_path=None, require_private=require_private)

    verify_directory_security(path.parent, create_if_missing=False)

    if not path.exists():
        raise SamsungHealthCloudError(f"file does not exist: {path}")
    if path.is_symlink():
        raise SamsungHealthCloudError(f"symlinks are forbidden: {path}")

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC

    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise SamsungHealthCloudError(f"unable to securely open file: {path}") from exc

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise SamsungHealthCloudError(f"target is not a regular file: {path}")

        if hasattr(os, "getuid") and st.st_uid != os.getuid():
            raise SamsungHealthCloudError(f"file has unexpected owner uid: {path}")

        if require_private and os.name != "nt" and (stat.S_IMODE(st.st_mode) & 0o077 != 0):
            raise SamsungHealthCloudError(
                f"file permissions must be private (0600), found {oct(stat.S_IMODE(st.st_mode))}: {path}"
            )

        with open(fd, encoding="utf-8", closefd=False) as f:
            return f.read()
    finally:
        os.close(fd)


def secure_atomic_write(
    path: Path,
    content: str,
    *,
    sidecar_lock_path: Path | None = None,
    file_mode: int = 0o600,
    dir_mode: int = 0o700,
) -> None:
    """Atomically and securely write file under exclusive sidecar lock with parent fsync."""
    if sidecar_lock_path is not None:
        with SidecarLock(sidecar_lock_path, exclusive=True):
            secure_atomic_write(
                path,
                content,
                sidecar_lock_path=None,
                file_mode=file_mode,
                dir_mode=dir_mode,
            )
            return

    verify_directory_security(path.parent, create_if_missing=True)

    if path.is_symlink():
        raise SamsungHealthCloudError(f"cannot write to symlink: {path}")

    parent = path.parent
    prefix = f".tmp_{path.name}_"
    temp_fd, temp_path_str = tempfile.mkstemp(dir=parent, prefix=prefix)
    temp_path = Path(temp_path_str)

    try:
        if os.name != "nt":
            os.chmod(temp_path, file_mode)

        with open(temp_fd, "w", encoding="utf-8", closefd=False) as f:
            f.write(content)
            f.flush()
            os.fsync(temp_fd)

        os.close(temp_fd)

        # Atomic replace
        os.replace(temp_path, path)

        # Fsync parent directory where supported
        if hasattr(os, "O_DIRECTORY") and hasattr(os, "fsync") and os.name != "nt":
            with contextlib.suppress(OSError):
                dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
    except Exception as exc:
        with contextlib.suppress(OSError):
            os.close(temp_fd)
        with contextlib.suppress(OSError):
            if temp_path.exists():
                temp_path.unlink()
        raise SamsungHealthCloudError(f"unable to atomically write state file {path}") from exc
