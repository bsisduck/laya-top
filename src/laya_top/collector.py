import os
import time

import psutil

from .models import Identity, Process, Snapshot, clean


class Collector:
    def __init__(self) -> None:
        self._previous: dict[Identity, float] = {}
        self._time: float | None = None
        self._network = None
        self._disk = None
        self._cpu = None

    def sample(self) -> Snapshot:
        now, wall = time.monotonic(), time.time()
        elapsed = now - self._time if self._time is not None else 0
        counters: dict[Identity, float] = {}
        processes: list[Process] = []
        # Fresh objects avoid process_iter's cached creation time after PID reuse.
        for pid in psutil.pids():
            try:
                p = psutil.Process(pid)
                with p.oneshot():
                    identity = Identity(pid, p.create_time())
                    times = p.cpu_times()
                    total = times.user + times.system
                    counters[identity] = total
                    previous = self._previous.get(identity, total)
                    cpu = max(0, (total - previous) / elapsed * 100) if elapsed else 0
                    try:
                        executable = clean(p.exe(), 1024)
                    except (psutil.AccessDenied, psutil.ZombieProcess):
                        executable = ""
                    try:
                        uid = p.uids().real
                        user = clean(p.username(), 80)
                    except (AttributeError, psutil.AccessDenied):
                        uid, user = None, "?"
                    processes.append(
                        Process(
                            identity,
                            p.ppid(),
                            clean(p.name(), 120),
                            executable,
                            user,
                            uid,
                            cpu,
                            p.memory_info().rss,
                            p.status(),
                            p.num_threads(),
                        )
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        memory, swap = psutil.virtual_memory(), psutil.swap_memory()
        network, disk = psutil.net_io_counters(), psutil.disk_io_counters()

        def rate(current, previous, field):
            if current is None or previous is None or not elapsed:
                return 0.0
            return max(0, getattr(current, field) - getattr(previous, field)) / elapsed

        cpu_times = psutil.cpu_times()
        cpu = 0.0
        if self._cpu is not None:
            # Guest time is already included in Linux user/nice counters.
            fields = [f for f in cpu_times._fields if f not in ("guest", "guest_nice")]
            total = sum(getattr(cpu_times, f) - getattr(self._cpu, f) for f in fields)
            idle = sum(
                getattr(cpu_times, f, 0) - getattr(self._cpu, f, 0) for f in ("idle", "iowait")
            )
            cpu = max(0, min(100, (total - idle) / total * 100)) if total > 0 else 0
        snapshot = Snapshot(
            tuple(processes),
            wall,
            cpu,
            memory.total - memory.available,
            memory.total,
            memory.percent,
            swap.used,
            swap.total,
            rate(network, self._network, "bytes_recv"),
            rate(network, self._network, "bytes_sent"),
            rate(disk, self._disk, "read_bytes"),
            rate(disk, self._disk, "write_bytes"),
            wall - psutil.boot_time(),
            psutil.cpu_count() or 1,
        )
        self._previous, self._time = counters, now
        self._network, self._disk, self._cpu = network, disk, cpu_times
        return snapshot


class DemoCollector:
    """Deterministic illustrative data. Never used for real process actions."""

    def sample(self) -> Snapshot:
        now = time.time()
        specs = [
            (4101, 1, "ollama", "/usr/local/bin/ollama", 134.2, 6840, "running"),
            (
                4102,
                1,
                "Code",
                "/Applications/Visual Studio Code.app/Contents/MacOS/Code",
                18.4,
                830,
                "sleeping",
            ),
            (4103, 4102, "node", "/usr/local/bin/node", 8.1, 260, "running"),
            (
                4104,
                1,
                "Google Chrome",
                "/Applications/Google Chrome.app/Contents/MacOS/Chrome",
                12.6,
                1240,
                "sleeping",
            ),
            (
                4105,
                4104,
                "Chrome Helper",
                "/Applications/Google Chrome.app/Contents/Helper",
                4.2,
                410,
                "sleeping",
            ),
            (
                4106,
                1,
                "Slack",
                "/Applications/Slack.app/Contents/MacOS/Slack",
                1.3,
                520,
                "sleeping",
            ),
            (4107, 1, "postgres", "/usr/local/bin/postgres", 2.4, 140, "sleeping"),
            (
                4108,
                1,
                "Spotify",
                "/Applications/Spotify.app/Contents/MacOS/Spotify",
                0.8,
                240,
                "sleeping",
            ),
            (4109, 4102, "python3.12", "/usr/local/bin/python3.12", 0.2, 88, "sleeping"),
            (4110, 1, "sync-agent", "/usr/local/bin/sync-agent", 0.0, 24, "sleeping"),
            (4111, 1, "WindowServer", "/System/Library/WindowServer", 7.1, 360, "running"),
            (4112, 4102, "zsh", "/bin/zsh", 0.0, 12, "sleeping"),
        ]
        processes = tuple(
            Process(
                Identity(pid, 1700000000.0 + pid),
                parent,
                name,
                exe,
                "demo",
                os.getuid(),
                cpu,
                mem * 1024**2,
                status,
                8,
            )
            for pid, parent, name, exe, cpu, mem, status in specs
        )
        return Snapshot(
            processes,
            now,
            24.8,
            17 * 1024**3,
            32 * 1024**3,
            53.1,
            256 * 1024**2,
            2 * 1024**3,
            48200,
            9800,
            230000,
            42000,
            124000,
            12,
        )
