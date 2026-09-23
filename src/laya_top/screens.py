from datetime import datetime

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from .actions import ACTIONS
from .config import CATEGORIES
from .models import Process, age, size
from .tagging import Tag, application


def description(process: Process, tag: Tag, timestamp: float, protection: str | None) -> Text:
    output = Text()
    output.append(f"{process.name}\n", style="bold #67d9ff")
    output.append(f"PID {process.pid}  ·  parent {process.ppid}\n\n", style="#9eb0c7")
    rows = [
        ("Application", application(process)),
        ("Category", tag.label),
        ("Tagged by", tag.source),
        ("Owner", process.user),
        ("State", process.status),
        ("CPU", f"{process.cpu:.1f}%"),
        ("Memory (RSS)", size(process.rss)),
        ("Threads", str(process.threads)),
        ("Running", age(timestamp - process.identity.created)),
        ("Started", datetime.fromtimestamp(process.identity.created).strftime("%Y-%m-%d %H:%M")),
    ]
    for label, value in rows:
        output.append(f"{label:<14}", style="#8497af")
        output.append(f"{value}\n")
    output.append("\nWHY THIS TAG\n", style="bold #f4c97b")
    output.append(tag.reason + "\n")
    if tag.probability is not None:
        output.append(f"Model probability: {tag.probability:.0%}; not measured accuracy.\n")
    output.append("\nEXECUTABLE\n", style="bold #f4c97b")
    output.append((process.executable or "Unavailable: OS access restricted") + "\n")
    if protection:
        output.append("\nPROTECTED\n", style="bold #f4c97b")
        output.append(protection)
    else:
        output.append("\nK stop  ·  P pause  ·  R resume\n", style="#9eb0c7")
    return output


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, process: Process, action: str):
        super().__init__()
        self.target, self.operation = process, action

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog"):
            yield Label(ACTIONS[self.operation], classes="dialog-title")
            yield Static(Text(f"{self.target.name}\nPID {self.target.pid} · {self.target.user}"))
            messages = {
                "terminate": "Send SIGTERM to this process only. It can clean up before exiting.",
                "kill": "SIGKILL stops this process immediately. Unsaved work may be lost.",
                "suspend": "Pause this process. Its work pauses; any locks it holds remain held.",
                "resume": "Resume this process if it is paused.",
            }
            yield Static(messages[self.operation], classes="dialog-note")
            if self.operation == "kill":
                yield Input(
                    placeholder=f"Type {self.target.pid} to enable force kill", id="confirm-pid"
                )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button(
                    ACTIONS[self.operation],
                    id="confirm",
                    variant="error",
                    disabled=self.operation == "kill",
                )

    def on_mount(self):
        self.query_one("#cancel", Button).focus()

    @on(Input.Changed, "#confirm-pid")
    def check_pid(self, event: Input.Changed):
        self.query_one("#confirm", Button).disabled = event.value != str(self.target.pid)

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed):
        self.dismiss(event.button.id == "confirm")

    def action_cancel(self):
        self.dismiss(False)


class DetailScreen(ModalScreen):
    BINDINGS = [("escape", "dismiss", "Close"), ("enter", "dismiss", "Close")]

    def __init__(self, text: Text):
        super().__init__()
        self.text = text

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog detail-dialog"):
            yield Static(self.text)
            yield Button("Close", id="close")

    @on(Button.Pressed)
    def close(self):
        self.dismiss()


class LabelScreen(ModalScreen[str | None]):
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, process: Process, current: str):
        super().__init__()
        self.target, self.current = process, current

    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="dialog"):
            yield Label("Set a category", classes="dialog-title")
            yield Static(
                Text(f"{self.target.name}\nApplies to this executable in future sessions.")
            )
            yield Select(
                [(c, c) for c in CATEGORIES], value=self.current, allow_blank=False, id="category"
            )
            with Horizontal(classes="dialog-buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Reset", id="reset")
                yield Button("Save", id="save", variant="primary")

    @on(Button.Pressed)
    def pressed(self, event: Button.Pressed):
        if event.button.id == "save":
            self.dismiss(str(self.query_one(Select).value))
        elif event.button.id == "reset":
            self.dismiss("reset")
        else:
            self.dismiss(None)

    def action_cancel(self):
        self.dismiss(None)


HELP = """LAYA TOP  /  KEYBOARD GUIDE

↑ ↓ / PageUp PageDown   Navigate processes
/                      Focus search
Escape                 Leave search / clear filters / cancel dialog
Enter                  Inspect process / open category
T                      Toggle parent-child tree
G                      Toggle category overview
M                      Toggle processes owned by you
C / Shift+M            Sort by CPU / memory
S                      Cycle sorting; click headers to reverse
F                      Pin/unpin selected process to the top
L                      Save a category for this executable
Space                  Freeze / resume the displayed snapshot
K                      Stop selected process (SIGTERM)
Shift+K                Force kill (requires typing the PID)
P / R                  Pause / resume selected process
A                      Show action history for this session
?                      This guide
Q                      Quit

SEARCH EXAMPLES
tag:AI                 One category
app:chrome             Application family
user:alice state:running
cpu>5 mem>100          CPU %, memory in MiB
-tag:System python     Exclude system, match Python
source:Laya            Model suggestions only
pid:1234               Exact process ID

Terms are combined with AND. Quote values containing spaces.
CPU 100% means one logical core. RSS can include shared memory.
Graphs show the last 60 samples. First CPU sample is a baseline.
~ marks an AI suggestion. Categories never grant permission to stop.
No automatic stopping, privilege escalation or cloud inference.
"""
