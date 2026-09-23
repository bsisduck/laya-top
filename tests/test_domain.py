from dataclasses import replace

import pytest

from laya_top import query
from laya_top.config import load_labels, save_label
from laya_top.models import Identity, clean
from laya_top.query import matches, order, tree_order
from laya_top.tagging import Tag, application, label_key, rule_tag


def test_rules_app_family_and_override(process):
    chrome = replace(process, name="helper", executable="/Applications/Google Chrome.app/Helper")
    assert application(chrome) == "Google Chrome"
    assert rule_tag(chrome, {}).category == "Browser"
    assert rule_tag(chrome, {label_key(chrome): "Development"}).source == "You"
    assert rule_tag(replace(process, name="ollama"), {}).category == "AI"
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


def test_ai_tags_searchable(process):
    assert matches(process, Tag("AI", "Laya", "suggestion"), "source:Laya tag:AI")


def test_blank_query_skips_process_metadata_work(process, monkeypatch):
    monkeypatch.setattr(query, "application", lambda process: (_ for _ in ()).throw(AssertionError))
    assert matches(process, Tag("AI", "Rule", "test"), "")
