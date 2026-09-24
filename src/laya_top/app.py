import asyncio
import os
from collections import defaultdict, deque
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Footer, Header, Input, Select, Static

from .actions import ACTIONS, Controller
from .collector import Collector, DemoCollector
from .config import load_labels, save_label
from .intelligence import Intelligence
from .layout import table_columns
from .models import Process, Snapshot, age, size
from .query import compile_query, order, tree_order
from .screens import HELP, ConfirmScreen, DetailScreen, LabelScreen, description
from .tagging import COLORS, Tag, label_key, rule_tag
from .widgets import PercentHistory, ProcessTable


class LayaTop(App):
    TITLE = "LAYA TOP"
    SUB_TITLE = "Know what is running."
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "search", "Search"),
        Binding("enter", "inspect", "Inspect", show=False),
        Binding("t", "tree", "Tree"),
        Binding("g", "groups", "Groups"),
        Binding("k", "control('terminate')", "Stop"),
        Binding("K", "control('kill')", "Force kill", show=False),
        Binding("p", "control('suspend')", "Pause", show=False),
        Binding("r", "control('resume')", "Resume", show=False),
        Binding("l", "label", "Label"),
        Binding("m", "mine", "Mine", show=False),
        Binding("c", "sort_by('cpu')", "CPU sort", show=False),
        Binding("M", "sort_by('memory')", "Memory sort", show=False),
        Binding("s", "sort", "Sort", show=False),
        Binding("f", "pin", "Pin", show=False),
        Binding("space", "freeze", "Freeze", show=False),
        Binding("a", "history", "History", show=False),
        Binding("question_mark", "help", "Help"),
        Binding("escape", "escape", "Clear", show=False),
    ]

    def __init__(
        self,
        model: Path | None = None,
        no_ai=False,
        demo=False,
        interval=2,
        collector=None,
        controller=None,
    ):
        super().__init__()
        self.demo, self.interval = demo, interval
        self.collector = collector or (DemoCollector() if demo else Collector())
        self.controller = controller or Controller(demo)
        self.ai = Intelligence(model, enabled=not no_ai and not demo)
        self.overrides = {} if demo else load_labels()
        self.snapshot: Snapshot | None = None
        self.tags: dict[str, Tag] = {}
        self._tag_inputs: dict[str, tuple[str, str]] = {}
        self.visible_processes: dict[str, Process] = {}
        self.selected: str | None = None
        self.pins: set[str] = set()
        self.mode, self.sort_column, self.reverse = "processes", "cpu", False
        self.mine, self.frozen = False, False
        self._sampling = False
        self._table_columns: tuple[tuple[str, str, int], ...] = ()
        self._rendered_mode = ""
        self._rendered_keys: list[str] = []
        self._rendered_cells: dict[str, dict[str, object]] = {}
        self._rendering = False
        self._selection_lost = False
        self._cpu_history: deque[float] = deque(maxlen=60)
        self._mem_history: deque[float] = deque(maxlen=60)
        self.audit: deque[str] = deque(maxlen=100)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="metrics"):
            with Vertical(classes="metric"):
                yield Static("CPU", classes="eyebrow")
                yield Static("Collecting…", id="cpu-value", classes="metric-value")
                yield PercentHistory(id="cpu-graph")
            with Vertical(classes="metric"):
                yield Static("MEMORY", classes="eyebrow")
                yield Static("Collecting…", id="mem-value", classes="metric-value")
                yield PercentHistory(id="mem-graph")
            with Vertical(classes="metric", id="io-metric"):
                yield Static("I/O  ·  PER SECOND", classes="eyebrow")
                yield Static("Collecting…", id="io-value")
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Search  /  tag:AI  cpu>5  -tag:System", id="search")
            yield Select(
                [
                    (label, key)
                    for key, label in (
                        ("cpu", "CPU ↓"),
                        ("memory", "Memory ↓"),
                        ("name", "Name A–Z"),
                        ("pid", "PID ↑"),
                        ("age", "Oldest first"),
                    )
                ],
                value="cpu",
                allow_blank=False,
                id="sort",
            )
        with Horizontal(id="viewbar"):
            yield Button("Processes", id="processes-view", classes="view-button")
            yield Button("Tree", id="tree-view", classes="view-button")
            yield Button("Categories", id="groups-view", classes="view-button")
            yield Button("All users", id="mine", classes="view-button")
            yield Static("", id="mode-note")
        yield Static("Sampling your machine…", id="summary")
        with Horizontal(id="workspace"):
            yield ProcessTable(
                id="processes", cursor_type="row", zebra_stripes=True, show_row_labels=False
            )
            with VerticalScroll(id="inspector"):
                yield Static("Select a process to inspect it.", id="details")
        yield Static("", id="intelligence")
        yield Footer()

    def on_mount(self):
        self.theme = "textual-dark"
        self.query_one("#processes", DataTable).focus()
        self.resize_layout(self.size)
        self.set_interval(self.interval, self.tick)
        self.tick()

    def on_resize(self, event):
        self.resize_layout(event.size)

    def resize_layout(self, size):
        self.set_class(size.width < 145, "compact")
        self.set_class(size.width < 85, "narrow")
        self.set_class(size.height < 30, "short")
        self.set_class(size.height < 20, "flat")
        self.set_class(size.width < 65, "slim")

    @on(ProcessTable.ViewportResized)
    def table_resized(self):
        # Measure after the table itself resizes, not the earlier App event.
        self.render_table(resizing=True)

    def tick(self):
        if not self._sampling and not self.frozen:
            self._sampling = True
            self.run_worker(self.collect_sample(), group="sampling", exit_on_error=False)

    async def collect_sample(self):
        try:
            snapshot = await asyncio.to_thread(self.collector.sample)
            if self.frozen:
                return
            self.snapshot = snapshot
            self._cpu_history.append(snapshot.cpu)
            self._mem_history.append(snapshot.memory_percent)
            previous_tags = self.tags
            previous_inputs = self._tag_inputs
            self.tags = {}
            self._tag_inputs = {}
            for process in sorted(snapshot.processes, key=lambda p: (-p.cpu, -p.rss)):
                key = process.identity.key
                inputs = (process.name, process.executable)
                tag = previous_tags.get(key)
                if tag is None or previous_inputs.get(key) != inputs:
                    tag = rule_tag(process, self.overrides)
                if tag.source == "Unknown" and self.ai.available:
                    tag = self.ai.suggest(process) or tag
                self.tags[key] = tag
                self._tag_inputs[key] = inputs
            active_keys = {p.identity.key for p in snapshot.processes}
            self.pins.intersection_update(active_keys)
            self.update_metrics()
            if len(self.screen_stack) == 1:
                self.render_table()
        except Exception as error:
            self.notify(f"Sampling failed: {type(error).__name__}. Retrying.", severity="warning")
        finally:
            self._sampling = False

    def update_metrics(self):
        s = self.snapshot
        if not s:
            return
        self.query_one("#cpu-value", Static).update(f"{s.cpu:.1f}%   ·   {s.cores} cores")
        self.query_one("#mem-value", Static).update(
            f"{size(s.memory_used)} / {size(s.memory_total)}"
        )
        self.query_one("#cpu-graph", PercentHistory).data = tuple(self._cpu_history)
        self.query_one("#mem-graph", PercentHistory).data = tuple(self._mem_history)
        self.query_one("#io-value", Static).update(
            f"NET  ↓ {size(s.network_rx)}   ↑ {size(s.network_tx)}\n"
            f"DISK ↓ {size(s.disk_read)}   ↑ {size(s.disk_write)}"
        )
        mode = "DEMO · illustrative data · controls disabled" if self.demo else self.ai.status
        detail = self.ai.detail if not self.demo else "Try /, T, G, L and Enter."
        self.query_one("#intelligence", Static).update(
            Text(
                f"● {mode}   ·   {detail}",
                style="#9eb0c7",
            )
        )

    def filtered(self) -> list[Process]:
        if not self.snapshot:
            return []
        query = self.query_one("#search", Input).value
        matches = compile_query(query)
        processes = [
            p
            for p in self.snapshot.processes
            if (not self.mine or p.uid == os.getuid()) and matches(p, self.tags[p.identity.key])
        ]
        processes = order(processes, self.sort_column, self.reverse)
        processes.sort(key=lambda p: p.identity.key not in self.pins)
        return processes

    def render_table(self, *, resizing=False):
        if not self.snapshot or (len(self.screen_stack) != 1 and not resizing):
            return
        table = self.query_one("#processes", DataTable)
        # Reserve a scrollbar even before rows are populated, so sampling cannot
        # push the last column off screen when a vertical scrollbar appears.
        width = table.content_size.width - table.styles.scrollbar_size_vertical
        columns = table_columns(width, self.mode == "groups", table.cell_padding)
        changed_columns = columns != self._table_columns
        if resizing and not changed_columns:
            return
        previous = self.selected
        scroll_y, scroll_x = table.scroll_y, table.scroll_x
        processes = self.filtered()
        self.visible_processes = {p.identity.key: p for p in processes}
        self._rendering = True
        rows = tree_order(processes) if self.mode == "tree" else [(p, 0) for p in processes]
        keys = [] if self.mode == "groups" else [process.identity.key for process, _ in rows]
        incremental = (
            self.mode != "groups"
            and self._rendered_mode == self.mode
            and not changed_columns
            and "pid" in table.columns
            and set(keys) == set(self._rendered_keys)
        )
        with self.batch_update(), table.prevent(DataTable.RowHighlighted):
            if not incremental:
                table.clear(columns=changed_columns)
                if changed_columns:
                    for key, label, width in columns:
                        table.add_column(label, width=width, key=key)
                    self._table_columns = columns
                self._rendered_cells = {}
            if self.mode == "groups":
                keys = []
                groups = defaultdict(list)
                for process in processes:
                    groups[self.tags[process.identity.key].label].append(process)
                for label, members in sorted(
                    groups.items(), key=lambda item: -sum(p.cpu for p in item[1])
                ):
                    key = "group:" + label
                    keys.append(key)
                    top = max(members, key=lambda p: p.cpu)
                    top_tag = self.tags[top.identity.key]
                    values = {
                        "category": Text(label, style=COLORS[top_tag.category]),
                        "count": str(len(members)),
                        "cpu": f"{sum(p.cpu for p in members):.1f}",
                        "memory": size(sum(p.rss for p in members)),
                        "name": Text(top.name, overflow="ellipsis", no_wrap=True),
                    }
                    table.add_row(*(values[c[0]] for c in columns), key=key)
            else:
                signatures = {}
                for process, depth in rows:
                    key = process.identity.key
                    signature = self.process_signature(process, depth)
                    signatures[key] = signature
                    if incremental:
                        previous_cells = self._rendered_cells.get(key, {})
                        for column, _, _ in columns:
                            if previous_cells.get(column) != signature[column]:
                                table.update_cell(
                                    key,
                                    column,
                                    self.process_cell(column, signature[column]),
                                    update_width=False,
                                )
                    else:
                        table.add_row(
                            *(self.process_cell(c[0], signature[c[0]]) for c in columns),
                            key=key,
                        )
                if incremental and keys != self._rendered_keys:
                    rank = {str(process.pid): index for index, (process, _) in enumerate(rows)}
                    table.sort("pid", key=lambda pid: rank[str(pid)])
                self._rendered_cells = signatures
            self._rendered_mode = self.mode
            self._rendered_keys = keys
            if previous in keys:
                table.move_cursor(row=keys.index(previous), animate=False, scroll=False)
                self.selected = previous
                table.show_cursor = True
            else:
                # Never silently transfer an action target to a replacement row.
                self.selected = None
                table.show_cursor = False
                if previous:
                    self._selection_lost = True
            if not previous and keys and not self._selection_lost:
                table.show_cursor = True
                table.move_cursor(row=0, animate=False, scroll=False)
                self.selected = keys[0]
            table.scroll_to(
                x=0 if changed_columns else scroll_x, y=scroll_y, animate=False, force=True
            )
        self._rendering = False
        marker = "  FROZEN" if self.frozen else ""
        self.query_one("#summary", Static).update(
            f" {len(processes)} / {len(self.snapshot.processes)} processes  ·  "
            f"up {age(self.snapshot.uptime)}  ·  swap {size(self.snapshot.swap_used)}  ·  "
            f"sort {self.sort_column}{' reversed' if self.reverse else ''}{marker}"
        )
        self.query_one("#mode-note", Static).update(
            "Enter opens a category" if self.mode == "groups" else "~ Laya suggestion   ★ pinned"
        )
        for name in ("processes", "tree", "groups"):
            self.query_one(f"#{name}-view", Button).set_class(self.mode == name, "active-view")
        self.update_inspector()

    def process_signature(self, process: Process, depth: int) -> dict[str, object]:
        key = process.identity.key
        tag = self.tags[key]
        prefix = "★ " if key in self.pins else ""
        prefix += "  " * depth + ("└ " if depth else "")
        name = prefix + process.name
        category = tag.label + (" ~" if tag.source == "Laya" else "")
        cpu = f"{process.cpu:.1f}"
        cpu_style = "bold #f4c97b" if process.cpu > 50 else "#c9d7e8"
        memory = size(process.rss)
        return {
            "pid": str(process.pid),
            "name": name,
            "category": (category, tag.category),
            "cpu": (cpu, cpu_style),
            "memory": memory,
            "user": process.user,
            "state": process.status,
            "source": tag.source,
        }

    @staticmethod
    def process_cell(column: str, value: object) -> object:
        if column == "name":
            return Text(str(value), overflow="ellipsis", no_wrap=True)
        if column == "category":
            label, category = value
            return Text(label, style=COLORS[category])
        if column == "cpu":
            cpu, style = value
            return Text(cpu, style=style)
        if column == "user":
            return Text(str(value))
        return value

    def selected_process(self) -> Process | None:
        return self.visible_processes.get(self.selected or "")

    def update_inspector(self):
        process = self.selected_process()
        if process and self.snapshot:
            text = description(
                process,
                self.tags[process.identity.key],
                self.snapshot.timestamp,
                self.controller.protection(process),
            )
        elif self.mode == "groups":
            text = Text(
                "CATEGORY OVERVIEW\n\nSelect a category and press Enter to see its processes."
                "\n\nCPU adds all members. RSS totals can count shared pages more than once."
                "\n\nGroups cannot be stopped as a unit.",
                style="#9eb0c7",
            )
        else:
            text = Text(
                "No process selected.\n\nUse the arrow keys or click a row."
                "\n\nIf a process exits, its action target is cleared.",
                style="#9eb0c7",
            )
        self.query_one("#details", Static).update(text)

    @on(DataTable.RowHighlighted, "#processes")
    def highlighted(self, event: DataTable.RowHighlighted):
        if self._rendering:
            return
        key = str(event.row_key.value)
        self.selected = key
        self._selection_lost = False
        self.update_inspector()

    @on(DataTable.RowSelected, "#processes")
    def row_selected(self, event: DataTable.RowSelected):
        self.selected = str(event.row_key.value)
        self._selection_lost = False
        self.action_inspect()

    def on_key(self, event):
        if (
            event.key in ("up", "down", "pageup", "pagedown", "home", "end")
            and isinstance(self.focused, DataTable)
            and self.selected is None
        ):
            table = self.query_one("#processes", DataTable)
            if table.row_count:
                table.show_cursor = True
                row = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
                self.selected = str(row.value)

    @on(Input.Changed, "#search")
    def search_changed(self):
        self.selected = None
        self._selection_lost = False
        self.render_table()

    @on(Input.Submitted, "#search")
    def search_submitted(self):
        self.query_one("#processes", DataTable).focus()

    @on(Select.Changed, "#sort")
    def sort_changed(self, event: Select.Changed):
        if event.value is not Select.BLANK:
            self.sort_column, self.reverse = str(event.value), False
            self.render_table()

    @on(DataTable.HeaderSelected, "#processes")
    def header_selected(self, event: DataTable.HeaderSelected):
        if self.mode == "groups":
            return
        column = event.column_key.value
        if column in ("pid", "name", "cpu", "memory"):
            if self.sort_column == column:
                self.reverse = not self.reverse
                self.render_table()
            else:
                self.action_sort_by(column)

    @on(Button.Pressed)
    def button_pressed(self, event: Button.Pressed):
        if event.button.id == "mine":
            self.action_mine()
        elif event.button.id in ("processes-view", "tree-view", "groups-view"):
            self.mode = event.button.id.removesuffix("-view")
            self.selected = None
            self._selection_lost = False
            self.render_table()
            self.query_one("#processes", DataTable).focus()

    def action_search(self):
        self.query_one("#search", Input).focus()

    def action_escape(self):
        search = self.query_one("#search", Input)
        if search.has_focus:
            self.query_one("#processes", DataTable).focus()
        else:
            search.value = ""

    def action_tree(self):
        if self.mode == "groups":
            self.selected, self._selection_lost = None, False
        self.mode = "processes" if self.mode == "tree" else "tree"
        self.render_table()

    def action_groups(self):
        self.mode = "processes" if self.mode == "groups" else "groups"
        self.selected = None
        self._selection_lost = False
        self.render_table()

    def action_mine(self):
        self.mine = not self.mine
        self.query_one("#mine", Button).label = "My processes" if self.mine else "All users"
        self.selected = None
        self._selection_lost = False
        self.render_table()

    def action_sort_by(self, column: str):
        self.query_one("#sort", Select).value = column
        self.sort_column, self.reverse = column, False
        self.render_table()

    def action_sort(self):
        columns = ["cpu", "memory", "name", "pid", "age"]
        self.action_sort_by(columns[(columns.index(self.sort_column) + 1) % len(columns)])

    def action_pin(self):
        if process := self.selected_process():
            key = process.identity.key
            self.pins.symmetric_difference_update({key})
            self.render_table()

    def action_freeze(self):
        self.frozen = not self.frozen
        self.render_table()
        if not self.frozen:
            self.tick()

    def action_inspect(self):
        if self.mode == "groups" and self.selected:
            category = self.selected.removeprefix("group:")
            self.mode = "processes"
            self.query_one("#search", Input).value = f'tag:"{category}"'
            self.selected = None
            self._selection_lost = False
            self.render_table()
        elif (process := self.selected_process()) and self.snapshot:
            self.push_screen(
                DetailScreen(
                    description(
                        process,
                        self.tags[process.identity.key],
                        self.snapshot.timestamp,
                        self.controller.protection(process),
                    )
                )
            )

    def action_control(self, action: str):
        process = self.selected_process()
        if process is None:
            self.notify("Select an individual process first.")
            return
        if reason := self.controller.protection(process):
            self.notify(reason, severity="warning")
            return

        def confirmed(yes: bool):
            if yes:
                self.run_worker(self.execute_action(process, action), exit_on_error=False)

        self.push_screen(ConfirmScreen(process, action), confirmed)

    async def execute_action(self, process: Process, action: str):
        result = await asyncio.to_thread(self.controller.execute, process, action)
        self.audit.appendleft(f"PID {process.pid} · {ACTIONS[action]} · {result.message}")
        self.notify(result.message, severity="information" if result.ok else "warning")
        self.tick()

    def action_label(self):
        if not (process := self.selected_process()):
            self.notify("Select an individual process first.")
            return

        def saved(category: str | None):
            if category is None:
                return
            key = label_key(process)
            try:
                if not self.demo:
                    save_label(key, None if category == "reset" else category)
                if category == "reset":
                    self.overrides.pop(key, None)
                else:
                    self.overrides[key] = category
                if self.snapshot:
                    for item in self.snapshot.processes:
                        if label_key(item) == key:
                            self.tags[item.identity.key] = rule_tag(item, self.overrides)
                self.render_table()
                self.notify("Demo label updated." if self.demo else "Category saved.")
            except OSError:
                self.notify(
                    "Could not save the category. Check config directory permissions.",
                    severity="error",
                )

        self.push_screen(LabelScreen(process, self.tags[process.identity.key].category), saved)

    def action_history(self):
        self.push_screen(
            DetailScreen(
                Text(
                    "SESSION ACTION HISTORY\n\n"
                    + ("\n\n".join(self.audit) or "No process actions this session.")
                )
            )
        )

    def action_help(self):
        self.push_screen(DetailScreen(Text(HELP)))

    def on_unmount(self):
        self.ai.close()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Modal controls own the keyboard until dismissed.
        return len(self.screen_stack) == 1
