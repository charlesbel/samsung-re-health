import concurrent.futures
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from samsung_health_cloud.exceptions import SamsungHealthCloudError
from samsung_health_cloud.file_lock import (
    InterprocessLock,
    SidecarLock,
    secure_atomic_write,
    secure_read_file,
    verify_directory_security,
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


def test_sidecar_lock_reentrancy_same_thread(tmp_path: Path):
    lock_path = tmp_path / "target.lock"
    with SidecarLock(lock_path, exclusive=True):  # noqa: SIM117
        # Nested exclusive lock on same thread
        with SidecarLock(lock_path, exclusive=True):  # noqa: SIM117
            # Nested shared lock on same thread
            with SidecarLock(lock_path, exclusive=False):
                assert lock_path.exists()


def test_sidecar_lock_concurrent_threads(tmp_path: Path):
    lock_path = tmp_path / "target.lock"
    counter = {"val": 0}

    def worker():
        for _ in range(50):
            with SidecarLock(lock_path, exclusive=True):  # noqa: SIM117
                current = counter["val"]
                time.sleep(0.001)
                counter["val"] = current + 1

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(worker) for _ in range(4)]
        for f in futures:
            f.result()

    assert counter["val"] == 200


def _mp_worker(data_path_str: str, lock_path_str: str, iterations: int):
    data_path = Path(data_path_str)
    lock_path = Path(lock_path_str)
    for _ in range(iterations):
        with SidecarLock(lock_path, exclusive=True):  # noqa: SIM117
            if data_path.exists():
                content = data_path.read_text(encoding="utf-8")
                val = int(content) if content.strip() else 0
            else:
                val = 0
            time.sleep(0.002)
            temp_path = data_path.with_name(f".tmp_{os.getpid()}_{time.time()}")
            temp_path.write_text(str(val + 1), encoding="utf-8")
            temp_path.chmod(0o600)
            os.replace(temp_path, data_path)


def test_multiprocessing_contention_and_serialization(tmp_path: Path):
    data_path = tmp_path / "counter.txt"
    lock_path = tmp_path / "counter.txt.lock"
    data_path.write_text("0", encoding="utf-8")
    data_path.chmod(0o600)

    ctx = multiprocessing.get_context("spawn")
    processes = [
        ctx.Process(target=_mp_worker, args=(str(data_path), str(lock_path), 10)) for _ in range(3)
    ]
    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=30)
        assert p.exitcode == 0

    final_val = int(data_path.read_text(encoding="utf-8"))
    assert final_val == 30


def test_security_rejections_symlinks_and_modes(tmp_path: Path):
    # 1. Symlinked parent directory rejection
    real_parent = tmp_path / "real_dir"
    real_parent.mkdir(mode=0o700)
    sym_parent = tmp_path / "sym_dir"
    sym_parent.symlink_to(real_parent)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):  # noqa: SIM117
        verify_directory_security(sym_parent)

    # 2. Overpermissive parent directory (0755) fail-closed
    bad_parent = tmp_path / "bad_perm"
    bad_parent.mkdir(mode=0o755)
    bad_parent.chmod(0o755)
    with pytest.raises(SamsungHealthCloudError, match="permissions"):
        verify_directory_security(bad_parent)

    # 3. Symlinked target file rejection
    real_target = real_parent / "real.json"
    real_target.write_text("{}", encoding="utf-8")
    real_target.chmod(0o600)
    sym_target = real_parent / "sym.json"
    sym_target.symlink_to(real_target)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):  # noqa: SIM117
        secure_read_file(sym_target)

    with pytest.raises(SamsungHealthCloudError, match="symlink"):  # noqa: SIM117
        secure_atomic_write(sym_target, "{}")

    # 4. Symlinked lock file rejection
    sym_lock = real_parent / "sym.json.lock"
    sym_lock.symlink_to(real_target)
    with pytest.raises(SamsungHealthCloudError, match="symlink"):  # noqa: SIM117
        with SidecarLock(sym_lock, exclusive=True):
            pass


def test_windows_locking_branch_monkeypatch(tmp_path: Path, monkeypatch):
    test_file = tmp_path / "win.lock"
    fd = os.open(test_file, os.O_CREAT | os.O_RDWR, 0o600)

    # Mock msvcrt
    class MockMsvcrt:
        LK_LOCK = 1
        LK_UNLCK = 2

        @staticmethod
        def locking(file_fd, mode, nbytes):
            pass

    monkeypatch.setattr("samsung_health_cloud.file_lock.fcntl", None)
    monkeypatch.setattr("samsung_health_cloud.file_lock.msvcrt", MockMsvcrt)

    lock = InterprocessLock(fd, exclusive=True)
    with lock:
        assert lock._locked is True
    assert lock._locked is False
    os.close(fd)
