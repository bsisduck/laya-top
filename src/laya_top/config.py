import json
import os
import tempfile
from pathlib import Path

CATEGORIES = ("AI", "Development", "Browser", "Communication", "Media", "System", "Other")
MODEL_REPO = "aac6fef/laya-multilingual-coreml-ane"


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "laya-top"


def model_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "laya-top/model"


def discover_model(explicit: str | None = None) -> Path | None:
    if explicit or os.environ.get("LAYA_TOP_MODEL"):
        return Path(explicit or os.environ["LAYA_TOP_MODEL"]).expanduser().resolve()
    for path in (
        model_dir(),
        Path.cwd() / "models/snake",
        Path.cwd().parent / "laya-coreml/models/snake",
    ):
        if (path / "coreml_config.json").is_file():
            return path.resolve()
    return None


def load_labels(path: Path | None = None) -> dict[str, str]:
    path = path or config_dir() / "labels.json"
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items() if isinstance(k, str) and v in CATEGORIES}
    except (OSError, ValueError, TypeError):
        return {}


def save_label(key: str, category: str | None, path: Path | None = None) -> None:
    if category is not None and category not in CATEGORIES:
        raise ValueError("Unknown category")
    path = path or config_dir() / "labels.json"
    labels = load_labels(path)
    if category is None:
        labels.pop(key, None)
    else:
        labels[key] = category
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".labels-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(labels, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
