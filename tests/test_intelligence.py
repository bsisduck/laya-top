import threading
import time
from dataclasses import replace

from laya_top.intelligence import Intelligence, metadata
from laya_top.tagging import Tag


def test_metadata_excludes_path_and_user(process):
    p = replace(process, executable="/Users/private-person/secret-token/Python.app/bin/python")
    text = metadata(p)
    assert "private-person" not in text
    assert "secret-token" not in text
    assert "tester" not in text
    assert "Python" in text


def test_inference_is_async_cached_and_deduplicated(tmp_path, process):
    (tmp_path / "coreml_config.json").write_text("{}")
    started = threading.Event()
    release = threading.Event()
    calls = []

    class Backend:
        def __init__(self, path):
            started.set()
            release.wait(timeout=3)

        def predict(self, text):
            calls.append(text)
            return Tag("Development", "Laya", "test", 0.9)

    ai = Intelligence(tmp_path, backend_factory=Backend)
    try:
        assert ai.suggest(process) is None
        assert started.wait(timeout=1)
        for _ in range(10):
            assert ai.suggest(process) is None
        assert len(ai.pending) == 1
        release.set()
        deadline = time.monotonic() + 3
        while not ai.cache and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ai.suggest(process).category == "Development"
        assert len(calls) == 1
    finally:
        release.set()
        ai.close()


def test_model_load_failure_degrades_to_rules(tmp_path, process):
    (tmp_path / "coreml_config.json").write_text("{}")

    def fail(path):
        raise RuntimeError("fake load error")

    ai = Intelligence(tmp_path, backend_factory=fail)
    ai.suggest(process)
    deadline = time.monotonic() + 2
    while ai.available and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not ai.available
    assert ai.status == "Laya unavailable"
    ai.close()
