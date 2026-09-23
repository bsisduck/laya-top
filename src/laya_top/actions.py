import os
from dataclasses import dataclass

import psutil

from .models import Process

ACTIONS = {
    "terminate": "Stop gracefully",
    "kill": "Force kill",
    "suspend": "Pause process",
    "resume": "Resume process",
}
CRITICAL = {"kernel_task", "launchd", "systemd", "WindowServer", "loginwindow"}


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str


class Controller:
    def __init__(self, demo: bool = False):
        self.demo = demo
        self.uid = os.getuid()
        self.protected = {0, 1, os.getpid()}
        self.protection_error = False
        if demo:
            return
        try:
            self.protected.update(p.pid for p in psutil.Process().parents())
        except (psutil.Error, OSError):
            self.protection_error = True

    def protection(self, process: Process) -> str | None:
        if self.demo:
            return "Demo mode: process controls are disabled."
        if self.protection_error:
            return "Cannot verify the ancestor chain. Process controls are disabled."
        if process.pid in self.protected:
            return "This process is laya-top, its ancestor, or an essential OS process."
        if process.name in CRITICAL:
            return "This process is protected because it maintains the operating system session."
        if process.uid is None or process.uid != self.uid or process.uid == 0:
            return "Only non-root processes owned by your current user can be controlled."
        return None

    def execute(self, target: Process, action: str) -> ActionResult:
        if action not in ACTIONS:
            return ActionResult(False, "Unsupported action.")
        if reason := self.protection(target):
            return ActionResult(False, reason)
        try:
            live = psutil.Process(target.pid)
            if abs(live.create_time() - target.identity.created) > 0.000001:
                return ActionResult(
                    False, "PID was reused. The replacement process was not touched."
                )
            if live.uids().real != self.uid or live.uids().effective != self.uid:
                return ActionResult(False, "Process ownership changed. Action refused.")
            if live.name() in CRITICAL:
                return ActionResult(False, "Process is now protected. Action refused.")
            # psutil signal methods perform their own last-moment PID reuse check.
            getattr(live, action)()
            return ActionResult(True, f"{ACTIONS[action]} requested for PID {target.pid}.")
        except psutil.NoSuchProcess:
            return ActionResult(False, "Process already exited. No signal sent.")
        except psutil.AccessDenied:
            return ActionResult(False, "The operating system denied this action.")
        except (psutil.Error, OSError) as error:
            return ActionResult(False, f"Action failed: {type(error).__name__}.")
