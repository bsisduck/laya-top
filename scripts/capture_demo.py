"""Export the actual Textual UI with illustrative data; no private process names."""

import asyncio
import os
from pathlib import Path

from laya_top.app import LayaTop


async def main():
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    os.environ.pop("NO_COLOR", None)
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(155, 42)) as pilot:
        await pilot.pause(0.5)
        app._cpu_history.extend([9, 12, 18, 36, 21, 14, 28, 24, 19, 31, 24.8] * 5)
        app._mem_history.extend([48, 49, 51, 49, 52, 51, 52, 53, 53.1] * 6)
        app.update_metrics()
        await pilot.pause()
        app.save_screenshot("laya-top.svg", path=str(output))
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        app.save_screenshot("laya-top-small.svg", path=str(output))
    print(output / "laya-top.svg")


asyncio.run(main())
