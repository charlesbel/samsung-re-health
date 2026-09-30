from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .client import SamsungHealthClient, SamsungHealthLocalClient
from .config import HealthConfig
from .credentials import (
    MasterCredentials,
    load_master_credentials,
    resolve_master_state_path,
)
from .exceptions import (
    AuthenticationError,
    DataError,
    NetworkError,
    RateLimitError,
    SamsungHealthCloudError,
    SamsungHealthError,
    SchemaError,
    StateError,
    UsageError,
)
from .models import DeviceProfile, ManifestInfo

try:
    __version__ = version("samsung-re-health")
except PackageNotFoundError:
    try:
        __version__ = version("samsung-health-cloud")
    except PackageNotFoundError:
        __version__ = "0.7.2"

__all__ = [
    "AuthenticationError",
    "DataError",
    "DeviceProfile",
    "HealthConfig",
    "ManifestInfo",
    "MasterCredentials",
    "NetworkError",
    "RateLimitError",
    "SamsungHealthClient",
    "SamsungHealthCloudError",
    "SamsungHealthError",
    "SamsungHealthLocalClient",
    "SchemaError",
    "StateError",
    "UsageError",
    "__version__",
    "load_master_credentials",
    "resolve_master_state_path",
]
