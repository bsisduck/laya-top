#!/usr/bin/env python3
"""Measure collector and unchanged-table refresh costs on the current machine."""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from dataclasses import replace

import psutil
from textual.widgets import DataTable

from laya_top.app import LayaTop
from laya_top.benchmarking import duration, summary
from laya_top.collector import Collector
from laya_top.models import Identity


def benchmark_collector(iterations: int) -> dict[str, object]:
    collector = Collector()
    snapshot, cold = duration(collector.sample)
    # Process CPU usage is delta-based, and production refreshes have an interval.
    time.sleep(0.2)
    samples = []
    for _ in range(iterations):
        _, elapsed = duration(collector.sample)
        samples.append(elapsed)
    return {
        "processes": len(snapshot.processes),
        "cold_ms": round(cold * 1000, 3),
        "warm": summary(samples),
    }


async def benchmark_render(rows: int, iterations: int) -> dict[str, object]:
    app = LayaTop(demo=True, interval=300)
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause(0.3)
        assert app.snapshot is not None
        source_processes = app.snapshot.processes
        source_tags = app.tags
        expanded = []
        tags = {}
        tag_inputs = {}
        for index in range(rows):
            original = source_processes[index % len(source_processes)]
            process = replace(
                original,
                identity=Identity(10_000 + index, original.identity.created + index),
            )
            expanded.append(process)
            tags[process.identity.key] = source_tags[original.identity.key]
            tag_inputs[process.identity.key] = (process.name, process.executable)
        app.snapshot = replace(app.snapshot, processes=tuple(expanded))
        app.tags = tags
        app._tag_inputs = tag_inputs
        app.render_table()
        await pilot.pause()

        samples = []
        for _ in range(iterations):
            _, elapsed = duration(app.render_table)
            samples.append(elapsed)
        return {
            "rows": app.query_one(DataTable).row_count,
            "unchanged": summary(samples),
        }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--iterations", type=int, default=20)
    result.add_argument("--rows", type=int, default=1_000)
    result.add_argument(
        "--skip-live", action="store_true", help="Skip process collection; benchmark rendering only"
    )
    return result


async def main() -> None:
    args = parser().parse_args()
    if args.iterations < 1 or args.rows < 1:
        raise SystemExit("--iterations and --rows must be positive")
    report: dict[str, object] = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "psutil": psutil.__version__,
        "iterations": args.iterations,
    }
    if not args.skip_live:
        try:
            report["collector"] = benchmark_collector(args.iterations)
        except (OSError, RuntimeError) as error:
            report["collector_error"] = (
                f"{type(error).__name__}: run from a normal terminal with process visibility"
            )
    report["render"] = await benchmark_render(args.rows, args.iterations)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
