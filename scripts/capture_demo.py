"""Export the actual Textual UI with illustrative data; no private process names."""

import asyncio
from pathlib import Path

from laya_top.app import LayaTop


async def main():
    output = Path(__file__).resolve().parents[1] / "artifacts"
    output.mkdir(exist_ok=True)
    app = LayaTop(demo=True, interval=30)
    async with app.run_test(size=(155, 42)) as pilot:
        await pilot.pause(0.5)
        app.save_screenshot("laya-top.svg", path=str(output))
        await pilot.resize_terminal(80, 24)
        await pilot.pause()
        app.save_screenshot("laya-top-small.svg", path=str(output))
    print(output / "laya-top.svg")


asyncio.run(main())
