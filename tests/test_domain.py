import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from laya_top import config, query
from laya_top.config import (
    MODEL_REPO,
    MODEL_REVISION,
    discover_model,
    load_labels,
    model_revision_path,
    save_label,
    verify_model_bundle,
    write_model_revision,
)
from laya_top.models import Identity, clean
from laya_top.query import matches, order, tree_order
from laya_top.tagging import Tag, application, label_key, rule_tag


def test_rules_app_family_and_override(process):
    chrome = replace(process, name="helper", executable="/Applications/Google Chrome.app/Helper")
    assert application(chrome) == "Google Chrome"
    assert rule_tag(chrome, {}).label == "Browser / Browser"
    assert rule_tag(chrome, {label_key(chrome): "Development"}).source == "You"
    assert rule_tag(replace(process, name="ollama"), {}).label == "AI / Inference"
    virtual_machine = replace(
        process,
        name="com.apple.Virtualization.VirtualMachine",
        executable="/System/Library/Frameworks/Virtualization.framework/VirtualMachine",
    )
    assert rule_tag(virtual_machine, {}).label == "System / Virtual machine"
    assert rule_tag(replace(process, name="not-classified", executable=""), {}).source == "Unknown"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("tag:Development cpu>10 mem>100", True),
        ("-tag:System python", True),
        ("pid:424242", True),
        ("pid:424", False),
        ("mem<100", False),
        ("cpu>1.2.3", False),
        ('app:"python3.12"', True),
        ("source:Laya", False),
        ("state:sleeping", False),
        ("no-match", False),
        ('"python', False),
    ],
)
def test_filters(process, query, expected):
    assert matches(process, rule_tag(process, {}), query) is expected


def test_tree_handles_missing_parents_and_cycles(process):
    a = replace(process, identity=Identity(10, 1), ppid=11)
    b = replace(process, identity=Identity(11, 1), ppid=10)
    c = replace(process, identity=Identity(12, 1), ppid=99)
    result = tree_order([a, b, c])
    assert {p.pid for p, _ in result} == {10, 11, 12}
    assert len(result) == 3
    assert result[0] == (c, 0)


def test_sort_and_control_characters(process):
    high = replace(process, identity=Identity(7, 2), cpu=125)
    assert order([process, high], "cpu")[0] == high
    assert clean("a\x1b[2J\n\x07b") == "a[2Jb"


def test_derived_identity_tag_and_query_values_are_cached():
    identity = Identity(7, 2)
    tag = Tag("Development", "Rule", "test", subcategory="Runtime")

    assert identity.key is identity.key
    assert tag.label is tag.label
    assert query.compile_query("tag:Development") is query.compile_query("tag:Development")


def test_labels_atomic_reset_and_corrupt_config(tmp_path):
    path = tmp_path / "config/labels.json"
    save_label("/bin/tool", "AI", path)
    assert load_labels(path) == {"/bin/tool": "AI"}
    save_label("/bin/tool", None, path)
    assert load_labels(path) == {}
    path.write_text("invalid json")
    assert load_labels(path) == {}
    with pytest.raises(ValueError):
        save_label("x", "not-a-category", path)


def test_concurrent_label_updates_preserve_each_change(tmp_path):
    path = tmp_path / "config/labels.json"
    keys = [f"/bin/tool-{index}" for index in range(24)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda key: save_label(key, "AI", path), keys))

    assert load_labels(path) == dict.fromkeys(keys, "AI")


def _model_fixture(tmp_path, monkeypatch):
    root = tmp_path / "model"
    payload = root / "weights/model.bin"
    payload.parent.mkdir(parents=True)
    payload.write_bytes(b"reviewed model bytes")
    manifest = {
        "format_version": 1,
        "repository": MODEL_REPO,
        "files": {
            "weights/model.bin": {
                "bytes": payload.stat().st_size,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
        },
    }
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    (root / "coreml_config.json").write_bytes(manifest_bytes)
    monkeypatch.setattr(config, "MODEL_MANIFEST_SHA256", hashlib.sha256(manifest_bytes).hexdigest())
    return root, payload


def test_model_bundle_verification_detects_corruption(tmp_path, monkeypatch):
    root, payload = _model_fixture(tmp_path, monkeypatch)
    assert verify_model_bundle(root) == (1, len(b"reviewed model bytes"))

    payload.write_bytes(b"tampered model bytes")
    with pytest.raises(ValueError, match="checksum|size"):
        verify_model_bundle(root)


def test_model_bundle_verification_rejects_unsafe_manifest(tmp_path, monkeypatch):
    root, _ = _model_fixture(tmp_path, monkeypatch)
    manifest_path = root / "coreml_config.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["files"] = {"../escape": {"bytes": 0, "sha256": "0" * 64}}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    manifest_path.write_bytes(manifest_bytes)
    monkeypatch.setattr(config, "MODEL_MANIFEST_SHA256", hashlib.sha256(manifest_bytes).hexdigest())

    with pytest.raises(ValueError, match="unsafe path"):
        verify_model_bundle(root)


def test_cached_model_requires_verified_revision_marker(tmp_path, monkeypatch):
    cache_home = tmp_path / "cache"
    root = cache_home / "laya-top/model"
    root.mkdir(parents=True)
    (root / "coreml_config.json").write_text("{}")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
    monkeypatch.chdir(work)

    assert discover_model() is None
    write_model_revision(root)
    assert model_revision_path(root).read_text().strip() == MODEL_REVISION
    assert discover_model() == root.resolve()


def test_ai_tags_searchable(process):
    tag = Tag("Development", "Laya", "suggestion", subcategory="Runtime")
    assert matches(process, tag, "source:Laya tag:Development sub:Runtime")
    assert matches(process, tag, 'tag:"Development / Runtime"')


def test_blank_query_skips_process_metadata_work(process, monkeypatch):
    monkeypatch.setattr(query, "application", lambda process: (_ for _ in ()).throw(AssertionError))
    assert matches(process, Tag("AI", "Rule", "test"), "")
