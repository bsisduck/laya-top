import fcntl
import hashlib
import json
import os
import tempfile
import threading
from hmac import compare_digest
from pathlib import Path

CATEGORIES = ("AI", "Development", "Browser", "Communication", "Media", "System", "Other")
MODEL_REPO = "aac6fef/laya-multilingual-coreml-ane"
MODEL_REVISION = "39d6a9b3d0f67f06da74fbade6121ea134cbdb21"
MODEL_MANIFEST_SHA256 = "a6120d85c392a96828d5ae2729f1cedc147cb28ee3cdae55afee74c063cd4cc0"
_LABEL_THREAD_LOCK = threading.Lock()


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "laya-top"


def model_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "laya-top/model"


def model_revision_path(path: Path) -> Path:
    return path / ".laya-top-revision"


def write_model_revision(path: Path) -> None:
    """Atomically mark a fully verified model cache revision."""
    marker = model_revision_path(path)
    fd, temporary = tempfile.mkstemp(dir=path, prefix=".revision-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(MODEL_REVISION + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, marker)
        directory_fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def discover_model(explicit: str | None = None) -> Path | None:
    if explicit or os.environ.get("LAYA_TOP_MODEL"):
        return Path(explicit or os.environ["LAYA_TOP_MODEL"]).expanduser().resolve()
    cached = model_dir()
    if (cached / "coreml_config.json").is_file():
        try:
            if model_revision_path(cached).read_text().strip() == MODEL_REVISION:
                return cached.resolve()
        except OSError:
            pass
    for path in (Path.cwd() / "models/snake", Path.cwd().parent / "laya-coreml/models/snake"):
        if (path / "coreml_config.json").is_file():
            return path.resolve()
    return None


def verify_model_bundle(path: Path) -> tuple[int, int]:
    """Verify the pinned bundle's manifest, paths, sizes, and SHA-256 hashes."""
    root = path.resolve()
    config_path = root / "coreml_config.json"
    try:
        if config_path.stat().st_size > 1024**2:
            raise ValueError("Model manifest is unexpectedly large")
        manifest = config_path.read_bytes()
        if not compare_digest(hashlib.sha256(manifest).hexdigest(), MODEL_MANIFEST_SHA256):
            raise ValueError("Model manifest checksum does not match the reviewed bundle")
        config = json.loads(manifest)
    except (OSError, ValueError, TypeError) as error:
        raise ValueError("Model manifest is missing or invalid") from error
    if not isinstance(config, dict) or config.get("format_version") != 1:
        raise ValueError("Unsupported model manifest format")
    if config.get("repository") != MODEL_REPO:
        raise ValueError("Model manifest names an unexpected repository")
    files = config.get("files")
    if not isinstance(files, dict) or not 1 <= len(files) <= 256:
        raise ValueError("Model manifest has an invalid file list")

    total = 0
    for relative, expected in files.items():
        if not isinstance(relative, str) or not isinstance(expected, dict):
            raise ValueError("Model manifest has an invalid file entry")
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError("Model manifest contains an unsafe path")
        candidate = (root / relative_path).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError(f"Model file is missing: {relative}")
        expected_size = expected.get("bytes")
        expected_hash = expected.get("sha256")
        try:
            decoded_hash = bytes.fromhex(expected_hash) if isinstance(expected_hash, str) else b""
        except ValueError:
            decoded_hash = b""
        if (
            not isinstance(expected_size, int)
            or expected_size < 0
            or len(decoded_hash) != hashlib.sha256().digest_size
        ):
            raise ValueError("Model manifest has invalid integrity metadata")
        if candidate.stat().st_size != expected_size:
            raise ValueError(f"Model file size does not match: {relative}")
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024**2), b""):
                digest.update(chunk)
        if not compare_digest(digest.hexdigest(), expected_hash.casefold()):
            raise ValueError(f"Model file checksum does not match: {relative}")
        total += expected_size
    return len(files), total


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
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    with _LABEL_THREAD_LOCK, lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        labels = load_labels(path)
        if category is None:
            labels.pop(key, None)
        else:
            labels[key] = category
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".labels-", suffix=".json")
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(labels, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            Path(temporary).unlink(missing_ok=True)
