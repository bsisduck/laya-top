from collections import namedtuple

import psutil

from laya_top.collector import Collector


def test_static_process_metadata_is_cached_between_samples(monkeypatch):
    CpuTimes = namedtuple("CpuTimes", "user system")
    Memory = namedtuple("Memory", "rss")
    Uids = namedtuple("Uids", "real")
    VirtualMemory = namedtuple("VirtualMemory", "total available percent")
    SwapMemory = namedtuple("SwapMemory", "used total")
    Network = namedtuple("Network", "bytes_recv bytes_sent")
    Disk = namedtuple("Disk", "read_bytes write_bytes")

    class Process:
        pid = 42

        def __init__(self):
            self.calls = {name: 0 for name in ("ppid", "name", "exe", "uids", "username", "status")}

        def oneshot(self):
            return _NullContext()

        def create_time(self):
            return 1000.0

        def cpu_times(self):
            return CpuTimes(1.0, 0.5)

        def memory_info(self):
            return Memory(1024)

        def status(self):
            return self._static("status", "running")

        def num_threads(self):
            return 2

        def _static(self, name, value):
            self.calls[name] += 1
            return value

        def ppid(self):
            return self._static("ppid", 1)

        def name(self):
            return self._static("name", "worker")

        def exe(self):
            return self._static("exe", "/bin/worker")

        def uids(self):
            return self._static("uids", Uids(501))

        def username(self):
            return self._static("username", "tester")

    process = Process()
    monkeypatch.setattr(psutil, "process_iter", lambda: iter((process,)))
    monkeypatch.setattr(psutil, "virtual_memory", lambda: VirtualMemory(100, 40, 60))
    monkeypatch.setattr(psutil, "swap_memory", lambda: SwapMemory(5, 20))
    monkeypatch.setattr(psutil, "net_io_counters", lambda: Network(10, 20))
    monkeypatch.setattr(psutil, "disk_io_counters", lambda: Disk(30, 40))
    monkeypatch.setattr(psutil, "cpu_times", lambda: CpuTimes(10, 90))
    monkeypatch.setattr(psutil, "boot_time", lambda: 500.0)
    monkeypatch.setattr(psutil, "cpu_count", lambda: 12)
    collector = Collector()
    first = collector.sample()
    second = collector.sample()

    assert first.processes[0].name == "worker"
    assert second.processes[0].identity == first.processes[0].identity
    assert process.calls == {name: 1 for name in process.calls}


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False
