import concurrent.futures
import os
from pathlib import Path

import pytest

from samsung_health_cloud.exceptions import SamsungHealthCloudError
from samsung_health_cloud.file_lock import (
    InterprocessLock,
    secure_atomic_write,
    secure_read_file,
)


def test_interprocess_lock_basic(tmp_path: Path):
    test_file = tmp_path / "test.lock"
    fd = os.open(test_file, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        lock = InterprocessLock(fd, exclusive=True)
        with lock:
            assert lock._locked is True
        assert lock._locked is False
    finally:
        os.close(fd)


def test_concurrent_shared_reads(tmp_path: Path):
    target = tmp_path / "data.json"
    secure_atomic_write(target, '{"key": "value"}', file_mode=0o600)

    def read_worker():
        return secure_read_file(target, require_private=True, lock=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(read_worker) for _ in range(10)]
        results = [f.result() for f in futures]

    assert all(r == '{"key": "value"}' for r in results)


def test_secure_read_rejects_symlinks(tmp_path: Path):
    real_file = tmp_path / "real.txt"
    real_file.write_text("hello", encoding="utf-8")
    real_file.chmod(0o600)

    symlink = tmp_path / "link.txt"
    symlink.symlink_to(real_file)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):
        secure_read_file(symlink)


def test_secure_atomic_write_creates_private_file(tmp_path: Path):
    target = tmp_path / "subdir" / "state.json"
    secure_atomic_write(target, '{"hello": "world"}')

    assert target.exists()
    assert secure_read_file(target) == '{"hello": "world"}'
    if os.name != "nt":
        assert (target.stat().st_mode & 0o077) == 0
