import threading
import time
from dataclasses import replace

import pytest

from laya_top.intelligence import CHOICES, CoreMLBackend, Intelligence, metadata
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


def _backend_with_output(choice, probabilities):
    class Agent:
        shape = {"max_length": 96}

        def prepare(self, candidate, question):
            return ([{"ids": [1, 2, 3]}], None)

        def predict(self, candidate, question):
            return {"answers": {"category": {"choice": choice, "probabilities": probabilities}}}

    backend = CoreMLBackend.__new__(CoreMLBackend)
    backend.agent = Agent()
    return backend


def test_coreml_output_schema_accepts_normalized_argmax():
    probabilities = dict.fromkeys(CHOICES, 0.025)
    probabilities["dev"] = 0.85

    tag = _backend_with_output("dev", probabilities).predict("sample editor")

    assert tag.category == "Development"
    assert tag.source == "Laya"
    assert tag.probability == pytest.approx(0.85)


@pytest.mark.parametrize(
    ("choice", "probabilities"),
    [
        ("dev", {"dev": 1.0}),
        ("dev", dict.fromkeys(CHOICES, 0.2)),
        ("dev", {**dict.fromkeys(CHOICES, 0.025), "dev": float("nan")}),
        ("dev", {**dict.fromkeys(CHOICES, 0.025), "dev": 1.1}),
        ("dev", {**dict.fromkeys(CHOICES, 0.025), "ai": 0.85, "dev": 0.0}),
    ],
)
def test_coreml_output_schema_rejects_invalid_results(choice, probabilities):
    with pytest.raises(ValueError, match="Invalid model output"):
        _backend_with_output(choice, probabilities).predict("sample editor")
