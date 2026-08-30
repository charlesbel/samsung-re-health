from __future__ import annotations

import contextlib
import os
import stat
import tempfile
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


class InterprocessLock:
    """Portable interprocess file lock supporting Linux, macOS, and Windows."""

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


def secure_read_file(
    path: Path,
    *,
    require_private: bool = True,
    lock: bool = True,
) -> str:
    """Safely open, lock, verify ownership/permissions, and read file without symlink TOCTOU."""
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
        if lock:
            ip_lock = InterprocessLock(fd, exclusive=False)
            ip_lock.acquire()
        else:
            ip_lock = None

        try:
            st = os.fstat(fd)
            if not stat.S_ISREG(st.st_mode):
                raise SamsungHealthCloudError(f"target is not a regular file: {path}")

            if hasattr(os, "getuid") and st.st_uid != os.getuid():
                raise SamsungHealthCloudError(f"file has unexpected owner uid: {path}")

            if require_private and os.name != "nt" and stat.S_IMODE(st.st_mode) & 0o077:
                raise SamsungHealthCloudError(f"file permissions must be private (0600): {path}")

            with open(fd, encoding="utf-8", closefd=False) as f:
                return f.read()
        finally:
            if ip_lock is not None:
                ip_lock.release()
    finally:
        os.close(fd)


def secure_atomic_write(
    path: Path,
    content: str,
    *,
    file_mode: int = 0o600,
    dir_mode: int = 0o700,
) -> None:
    """Atomically and securely write file with explicit permissions and parent fsync."""
    if path.is_symlink():
        raise SamsungHealthCloudError(f"cannot write to symlink: {path}")

    parent = path.parent
    if not parent.exists():
        parent.mkdir(mode=dir_mode, parents=True, exist_ok=True)

    prefix = f".tmp_{path.name}_"
    temp_fd, temp_path_str = tempfile.mkstemp(dir=parent, prefix=prefix)
    temp_path = Path(temp_path_str)

    try:
        if os.name != "nt":
            os.chmod(temp_path, file_mode)

        ip_lock = InterprocessLock(temp_fd, exclusive=True)
        ip_lock.acquire()
        try:
            with open(temp_fd, "w", encoding="utf-8", closefd=False) as f:
                f.write(content)
                f.flush()
                os.fsync(temp_fd)
        finally:
            ip_lock.release()

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
