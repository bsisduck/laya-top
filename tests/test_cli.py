import sys
import types

from laya_top import cli
from laya_top.config import MODEL_REPO, MODEL_REVISION, model_revision_path


def test_model_download_uses_pinned_revision_and_cache_target(tmp_path, monkeypatch, capsys):
    target = tmp_path / "cache/model"
    adjacent = tmp_path / "adjacent/model"
    call = {}

    def snapshot_download(repository, *, revision, local_dir):
        call.update(repository=repository, revision=revision, local_dir=local_dir)
        target.mkdir(parents=True)

    hub = types.ModuleType("huggingface_hub")
    hub.snapshot_download = snapshot_download
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setattr(cli, "discover_model", lambda explicit: adjacent)
    monkeypatch.setattr(cli, "model_dir", lambda: target)
    monkeypatch.setattr(cli, "verify_model_bundle", lambda path: (8, 679_895_257))
    monkeypatch.setattr(sys, "argv", ["laya-top", "model", "download"])

    cli.main()

    assert call == {
        "repository": MODEL_REPO,
        "revision": MODEL_REVISION,
        "local_dir": str(target),
    }
    assert model_revision_path(target).read_text().strip() == MODEL_REVISION
    assert capsys.readouterr().out.strip() == str(target)
