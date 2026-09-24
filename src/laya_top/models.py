from dataclasses import dataclass
from functools import cached_property


@dataclass(frozen=True)
class Identity:
    pid: int
    created: float

    @cached_property
    def key(self) -> str:
        return f"{self.pid}:{self.created:.6f}"


@dataclass(frozen=True)
class Process:
    identity: Identity
    ppid: int
    name: str
    executable: str
    user: str
    uid: int | None
    cpu: float
    rss: int
    status: str
    threads: int

    @property
    def pid(self) -> int:
        return self.identity.pid


@dataclass(frozen=True)
class Snapshot:
    processes: tuple[Process, ...]
    timestamp: float
    cpu: float
    memory_used: int
    memory_total: int
    memory_percent: float
    swap_used: int
    swap_total: int
    network_rx: float
    network_tx: float
    disk_read: float
    disk_write: float
    uptime: float
    cores: int


def clean(value: str, limit: int = 160) -> str:
    """Keep untrusted OS names from injecting terminal control characters."""
    return "".join(c for c in value if c.isprintable())[:limit]


def size(value: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(value) < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return "0 B"


def age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds >= 86400:
        return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"
    if seconds >= 3600:
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    return f"{seconds // 60}m {seconds % 60}s"
