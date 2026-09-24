import os
import subprocess
import sys
from dataclasses import replace
from unittest.mock import Mock

import psutil
import pytest

from laya_top.actions import Controller
from laya_top.collector import Collector
from laya_top.models import Identity


def test_protected_self_parent_root_other_user_and_demo(process):
    controller = Controller()
    for pid in controller.protected:
        assert controller.protection(replace(process, identity=Identity(pid, 1)))
    assert controller.protection(replace(process, uid=0))
    assert controller.protection(replace(process, uid=os.getuid() + 100))
    assert controller.protection(replace(process, name="WindowServer"))
    assert Controller(demo=True).protection(process)


def test_pid_reuse_never_sends_signal(process, monkeypatch):
    controller = Controller()
    controller.uid = 501
    process = replace(process, uid=controller.uid)
    live = Mock()
    live.create_time.return_value = process.identity.created + 10
    monkeypatch.setattr(psutil, "Process", Mock(return_value=live))
    result = controller.execute(process, "kill")
    assert not result.ok and "reused" in result.message
    live.kill.assert_not_called()


def test_owner_change_and_exit_never_send_signal(process, monkeypatch):
    controller = Controller()
    controller.uid = 501
    process = replace(process, uid=controller.uid)
    live = Mock()
    live.create_time.return_value = process.identity.created
    live.uids.return_value = Mock(real=os.getuid() + 1, effective=os.getuid() + 1)
    monkeypatch.setattr(psutil, "Process", Mock(return_value=live))
    assert not controller.execute(process, "terminate").ok
    live.terminate.assert_not_called()
    monkeypatch.setattr(psutil, "Process", Mock(side_effect=psutil.NoSuchProcess(process.pid)))
    assert "already exited" in controller.execute(process, "terminate").message


def test_unsupported_action_never_opens_process(process, monkeypatch):
    controller = Controller()
    monkeypatch.setattr(psutil, "Process", Mock(side_effect=AssertionError("must not open")))

    result = controller.execute(process, "unsupported")

    assert not result.ok
    assert result.message == "Unsupported action."


@pytest.mark.skipif(os.getuid() == 0, reason="Controller intentionally forbids root processes")
def test_real_disposable_child_can_pause_resume_and_terminate():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        target = next(p for p in Collector().sample().processes if p.pid == child.pid)
        controller = Controller()
        assert controller.execute(target, "suspend").ok
        assert controller.execute(target, "resume").ok
        assert controller.execute(target, "terminate").ok
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
