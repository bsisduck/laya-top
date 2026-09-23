"""Bounded local inference. Model outputs have no access to the action controller."""

import importlib.util
import math
import platform
import queue
import threading
import time
from collections import OrderedDict
from pathlib import Path

from .models import Process, clean
from .tagging import Tag, application, subcategory_for_text

CHOICES = {
    "ai": "AI models",
    "dev": "coding",
    "web": "browser",
    "chat": "messaging",
    "media": "audio video",
    "system": "OS services",
    "other": "other software",
}
CATEGORY_MAP = dict(
    zip(
        CHOICES,
        ("AI", "Development", "Browser", "Communication", "Media", "System", "Other"),
        strict=True,
    )
)
QUESTION = {
    "category": {"type": "choice", "instructions": "Classify software.", "criteria": CHOICES}
}


def metadata(process: Process) -> str:
    # Names only. No paths, usernames, arguments, environment, ports or file contents.
    name = clean(process.name, 40)
    app = clean(application(process), 40)
    return name if name == app else f"{name}; app {app}"


class CoreMLBackend:
    def __init__(self, path: Path):
        import laya_coreml

        self.agent = laya_coreml.load(str(path), local_files_only=True)
        # v0.1.0 accepts extreme calibration temperatures; keep suggestions conservative.
        self.agent.temperature = [max(0.5, min(5, float(t))) for t in self.agent.temperature]
        self.agent.temperature_by_options = {
            key: max(0.5, min(5, float(t))) for key, t in self.agent.temperature_by_options.items()
        }

    def predict(self, text: str) -> Tag:
        # Fit using the real tokenizer. Never silently truncate a loaded model's state.
        candidate = text
        while candidate:
            items, _ = self.agent.prepare(candidate, QUESTION)
            if max(len(item["ids"]) for item in items) <= self.agent.shape["max_length"]:
                break
            candidate = candidate[: len(candidate) // 2]
        if not candidate:
            return Tag("Other", "Unknown", "Laya prompt does not fit this model.")
        answer = self.agent.predict(candidate, QUESTION)["answers"]["category"]
        probabilities = answer["probabilities"]
        values = sorted((float(v) for v in probabilities.values()), reverse=True)
        choice = answer["choice"]
        if (
            choice not in CATEGORY_MAP
            or len(values) < 2
            or not all(math.isfinite(v) and 0 <= v <= 1 for v in values)
        ):
            raise ValueError("Invalid model output")
        if values[0] < 0.7 or values[0] - values[1] < 0.15 or choice == "other":
            return Tag("Other", "Unknown", "Laya was inconclusive; choose a category with L.")
        return Tag(
            CATEGORY_MAP[choice],
            "Laya",
            "Local model suggestion based on software names. Verify before relying on it.",
            values[0],
            subcategory_for_text(CATEGORY_MAP[choice], text),
        )


class Intelligence:
    def __init__(self, path: Path | None, enabled: bool = True, backend_factory=CoreMLBackend):
        self.path = path
        self.status = "Rules only"
        self.detail = "Install the laya extra and download a model to enable local suggestions."
        self.cache: OrderedDict[str, Tag] = OrderedDict()
        self.pending: set[str] = set()
        self._queue: queue.Queue[str] = queue.Queue(maxsize=64)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._factory = backend_factory
        self._thread: threading.Thread | None = None
        self.available = False
        if not enabled:
            self.detail = "AI is disabled for this session."
        elif path is None:
            self.detail = "No model found. Run laya-top model download, or pass --model PATH."
        elif not (path / "coreml_config.json").is_file():
            self.detail = f"Model bundle not found at {path}."
        elif backend_factory is CoreMLBackend and (
            platform.system() != "Darwin" or platform.machine() != "arm64"
        ):
            self.detail = "Core ML requires an Apple Silicon Mac. Rules remain available."
        elif backend_factory is CoreMLBackend and importlib.util.find_spec("laya_coreml") is None:
            self.detail = "Install the optional laya extra to enable Core ML."
        else:
            self.available = True
            self.status = "Laya idle"
            self.detail = "Local model loads when an unknown process needs a tag."

    def suggest(self, process: Process) -> Tag | None:
        if not self.available:
            return None
        key = metadata(process)
        with self._lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            if key not in self.pending:
                try:
                    self._queue.put_nowait(key)
                    self.pending.add(key)
                except queue.Full:
                    return None
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True, name="laya-tags")
                self._thread.start()
        return None

    def _run(self):
        self.status = "Laya loading"
        self.detail = "First Core ML initialization may take a minute. Monitoring continues."
        try:
            backend = self._factory(self.path)
            self.status, self.detail = "Laya local", "Name-only suggestions; cached in memory."
        except Exception as error:
            self.status = "Laya unavailable"
            self.detail = f"{type(error).__name__} loading model. Rules remain active; run doctor."
            self.available = False
            return
        while not self._stop.is_set():
            try:
                key = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            started = time.monotonic()
            try:
                tag = backend.predict(key)
            except Exception as error:
                tag = Tag("Other", "Unknown", f"Laya could not classify ({type(error).__name__}).")
            with self._lock:
                self.cache[key] = tag
                self.pending.discard(key)
                while len(self.cache) > 512:
                    self.cache.popitem(last=False)
            # At most two new classifications/second; known software uses no model calls.
            self._stop.wait(max(0, 0.5 - (time.monotonic() - started)))

    def close(self):
        self._stop.set()
