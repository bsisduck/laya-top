import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import PurePath

from .models import Process

COLORS = {
    "AI": "#b8a0ff",
    "Development": "#67d9ff",
    "Browser": "#f4c97b",
    "Communication": "#f5a2ce",
    "Media": "#94d8a8",
    "System": "#98a9bf",
    "Other": "#a9b4c7",
}
RULES = (
    ("AI", r"(?i)(ollama|llama|lm studio|mlx|laya|vllm|comfyui|stable.?diffusion|codex|claude)"),
    (
        "Browser",
        r"(?i)(chrome|chromium|firefox|safari|brave|webkit|arc helper|^arc$|"
        r"msedge|microsoft edge)",
    ),
    (
        "Communication",
        r"(?i)(slack|discord|telegram|whatsapp|zoom|microsoft teams|^mail$|^messages$)",
    ),
    ("Media", r"(?i)(spotify|vlc|music|photos|obs|ffmpeg|audacity|quicktime)"),
    (
        "Development",
        r"(?i)(visual studio|^code$|cursor|xcode|intellij|pycharm|docker|podman|"
        r"containerd|postgres|redis|mysql|mongo|clickhouse|rustc|cargo|webpack|vite|"
        r"^node$|^bun$|^deno$|^go$|"
        r"^python[\d.]*$|^ruby[\d.]*$|^java$|^git$|^make$|^code$|^uv$)",
    ),
    (
        "System",
        r"(?i)(^launchd$|^systemd|kernel_task|windowserver|windowmanager|loginwindow|^sshd$|"
        r"^zsh$|^bash$|^sh$|^fish$|^cron$|^dbus|^syslog|^mds|^mdworker|^finder$|^dock$)",
    ),
)
COMPILED = [(category, re.compile(pattern)) for category, pattern in RULES]
SUBCATEGORY_RULES = {
    "AI": (
        ("Generative media", r"(?i)(comfyui|stable.?diffusion)"),
        ("Inference", r"(?i)(ollama|llama|lm studio|mlx|vllm)"),
        ("Assistant", r"(?i)(codex|claude|laya)"),
    ),
    "Development": (
        ("Editor", r"(?i)(visual studio|^code$|cursor|xcode|intellij|pycharm)"),
        ("Container", r"(?i)(docker|podman|containerd)"),
        ("Database", r"(?i)(postgres|redis|mysql|mongo|clickhouse)"),
        ("Build tool", r"(?i)(rustc|cargo|webpack|vite|^git$|^make$|^uv$)"),
        ("Runtime", r"(?i)(^node$|^bun$|^deno$|^go$|^python[\d.]*$|^ruby[\d.]*$|^java$)"),
    ),
    "Browser": (
        ("Renderer", r"(?i)(renderer|webcontent)"),
        ("Extension", r"(?i)(extension|plugin)"),
        ("Browser", r"(?i)(chrome|chromium|firefox|safari|brave|webkit|arc|msedge)"),
    ),
    "Communication": (
        ("Meetings", r"(?i)(zoom|microsoft teams)"),
        ("Mail", r"(?i)(^mail$)"),
        ("Chat", r"(?i)(slack|discord|telegram|whatsapp|messages)"),
    ),
    "Media": (
        ("Video", r"(?i)(vlc|obs|ffmpeg|quicktime)"),
        ("Photos", r"(?i)(photos)"),
        ("Audio", r"(?i)(spotify|music|audacity)"),
    ),
    "System": (
        ("Virtual machine", r"(?i)(virtualization\.virtualmachine|virtualmachine|qemu)"),
        ("Kernel", r"(?i)(kernel_task)"),
        ("Desktop", r"(?i)(windowserver|windowmanager|loginwindow|finder|dock)"),
        ("Shell", r"(?i)(^zsh$|^bash$|^sh$|^fish$)"),
        ("Service", r"(?i)(launchd|systemd|sshd|cron|dbus|syslog|mds|mdworker)"),
    ),
}
COMPILED_SUBCATEGORIES = {
    category: tuple((subcategory, re.compile(pattern)) for subcategory, pattern in rules)
    for category, rules in SUBCATEGORY_RULES.items()
}


@dataclass(frozen=True)
class Tag:
    category: str
    source: str
    reason: str
    probability: float | None = None
    subcategory: str = "General"

    @cached_property
    def label(self) -> str:
        return (
            self.category
            if self.subcategory == "General"
            else f"{self.category} / {self.subcategory}"
        )


def application(process: Process) -> str:
    return _application(process.name, process.executable)


@lru_cache(maxsize=4096)
def _application(name: str, executable: str) -> str:
    for component in PurePath(executable).parts:
        if component.endswith(".app"):
            return component[:-4]
    return name


def label_key(process: Process) -> str:
    return process.executable or f"name:{process.name}"


def subcategory_for(category: str, process: Process) -> str:
    app = application(process)
    return subcategory_for_text(category, process.name, app)


def subcategory_for_text(category: str, *values: str) -> str:
    for subcategory, pattern in COMPILED_SUBCATEGORIES.get(category, ()):
        if any(pattern.search(value) for value in values):
            return subcategory
    return "General"


def rule_tag(process: Process, overrides: dict[str, str]) -> Tag:
    if category := overrides.get(label_key(process)):
        return Tag(
            category,
            "You",
            "Your saved category for this executable.",
            subcategory=subcategory_for(category, process),
        )
    app = application(process)
    for category, pattern in COMPILED:
        if pattern.search(process.name) or pattern.search(app):
            return Tag(
                category,
                "Rule",
                f"Known software rule: {app}.",
                subcategory=subcategory_for(category, process),
            )
    if process.executable.startswith(("/System/", "/usr/libexec/", "/usr/lib/systemd/")):
        subcategory = subcategory_for("System", process)
        return Tag(
            "System",
            "Rule",
            "Executable is in a system service directory.",
            subcategory="Service" if subcategory == "General" else subcategory,
        )
    return Tag("Other", "Unknown", "No matching rule. Set a category with L, or enable Laya.")
