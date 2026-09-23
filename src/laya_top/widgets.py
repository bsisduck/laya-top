from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class PercentHistory(Static):
    """A fixed 0–100% scale, so a flat 10% history never looks fully busy."""

    data: reactive[tuple[float, ...]] = reactive(())

    def render(self) -> Text:
        width = max(1, self.size.width)
        samples = [0.0] * max(0, 60 - len(self.data)) + list(self.data)[-60:]
        bars = "▁▂▃▄▅▆▇█"
        output = []
        for index in range(width):
            start = min(59, int(index * 60 / width))
            end = min(60, max(start + 1, int((index + 1) * 60 / width)))
            value = min(100, max(0, max(samples[start:end])))
            output.append(bars[min(7, int(value / 100 * 7))])
        return Text("\n" + "".join(output))
