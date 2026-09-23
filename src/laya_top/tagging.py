import re
from dataclasses import dataclass
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
    ("Browser", r"(?i)(chrome|chromium|firefox|safari|brave|webkit|arc helper|^arc$|msedge)"),
    (
        "Communication",
        r"(?i)(slack|discord|telegram|whatsapp|zoom|microsoft teams|^mail$|^messages$)",
    ),
    ("Media", r"(?i)(spotify|vlc|music|photos|obs|ffmpeg|audacity|quicktime)"),
    (
        "Development",
        r"(?i)(visual studio|xcode|intellij|pycharm|docker|podman|postgres|redis|"
        r"mysql|rustc|cargo|webpack|vite|^node$|^bun$|^deno$|^go$|"
        r"^python[\d.]*$|^ruby[\d.]*$|^java$|^git$|^make$|^code$|^uv$)",
    ),
    (
        "System",
        r"(?i)(^launchd$|^systemd|kernel_task|windowserver|loginwindow|^sshd$|"
        r"^zsh$|^bash$|^sh$|^fish$|^cron$|^dbus|^syslog|^mds|^mdworker|^finder$|^dock$)",
    ),
)
COMPILED = [(category, re.compile(pattern)) for category, pattern in RULES]


@dataclass(frozen=True)
class Tag:
    category: str
    source: str
    reason: str
    probability: float | None = None


def application(process: Process) -> str:
    for component in PurePath(process.executable).parts:
        if component.endswith(".app"):
            return component[:-4]
    return process.name


def label_key(process: Process) -> str:
    return process.executable or f"name:{process.name}"


def rule_tag(process: Process, overrides: dict[str, str]) -> Tag:
    if category := overrides.get(label_key(process)):
        return Tag(category, "You", "Your saved category for this executable.")
    app = application(process)
    for category, pattern in COMPILED:
        if pattern.search(process.name) or pattern.search(app):
            return Tag(category, "Rule", f"Known software rule: {app}.")
    if process.executable.startswith(("/System/", "/usr/libexec/", "/usr/lib/systemd/")):
        return Tag("System", "Rule", "Executable is in a system service directory.")
    return Tag("Other", "Unknown", "No matching rule. Set a category with L, or enable Laya.")
