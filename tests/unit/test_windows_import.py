import sys


def test_windows_import_simulation(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    # Simulate missing fcntl on Windows
    monkeypatch.setitem(sys.modules, "fcntl", None)

    # Import modules under simulated Windows
    import importlib

    import samsung_health_cloud.cli
    import samsung_health_cloud.client
    import samsung_health_cloud.exporter
    import samsung_health_cloud.file_lock

    importlib.reload(samsung_health_cloud.file_lock)
    importlib.reload(samsung_health_cloud.exporter)
    importlib.reload(samsung_health_cloud.cli)

    assert samsung_health_cloud.file_lock.fcntl is None
