import json

import pytest

from video2context.cache import Cache
from video2context.errors import OutputError
from video2context.export.package import MARKER, atomic_package


def test_cache_content_model_and_context_invalidation(tmp_path):
    source = tmp_path / "image"
    source.write_bytes(b"first")
    cache = Cache(tmp_path / "cache")
    calls = []

    def compute():
        calls.append(1)
        return {"value": len(calls)}

    assert cache.get_or_compute(source, {"model": "a"}, compute)["value"] == 1
    assert cache.get_or_compute(source, {"model": "a"}, compute)["value"] == 1
    source.write_bytes(b"second")
    assert cache.get_or_compute(source, {"model": "a"}, compute)["value"] == 2
    assert cache.get_or_compute(source, {"model": "b"}, compute)["value"] == 3
    assert cache.hits == 1


def test_corrupt_cache_recomputed(tmp_path):
    source = tmp_path / "image"
    source.write_bytes(b"test")
    cache = Cache(tmp_path / "cache")
    cache.get_or_compute(source, {}, lambda: "ok")
    next(cache.root.glob("*.json")).write_text("broken")
    assert cache.get_or_compute(source, {}, lambda: "repaired") == "repaired"
    assert json.loads(next(cache.root.glob("*.json")).read_text())["result"] == "repaired"


def test_failed_export_never_publishes(tmp_path):
    target = tmp_path / "output"
    with pytest.raises(RuntimeError), atomic_package(target, False) as root:
        (root / "context.md").write_text("incomplete")
        raise RuntimeError("interrupted")
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_overwrite_protection_and_failure_preserves_previous(tmp_path):
    target = tmp_path / "output"
    target.mkdir()
    with pytest.raises(OutputError), atomic_package(target, True):
        pass
    (target / MARKER).write_text("1")
    (target / "context.md").write_text("old")
    with pytest.raises(RuntimeError), atomic_package(target, True) as root:
        (root / "context.md").write_text("new")
        raise RuntimeError()
    assert (target / "context.md").read_text() == "old"
    with atomic_package(target, True) as root:
        (root / "context.md").write_text("new")
    assert (target / "context.md").read_text() == "new"


def test_concurrent_export_lock_and_symlink(tmp_path):
    target = tmp_path / "output"
    with (
        atomic_package(target, False),
        pytest.raises(OutputError, match="locked"),
        atomic_package(target, False),
    ):
        pass
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(OutputError, match="symlink"), atomic_package(link, True):
        pass


def test_output_created_during_processing_is_not_overwritten(tmp_path):
    target = tmp_path / "output"
    with pytest.raises(OutputError), atomic_package(target, False) as root:
        (root / "context.md").write_text("new")
        target.mkdir()
        (target / "important.txt").write_text("keep me")
    assert (target / "important.txt").read_text() == "keep me"


def test_staging_failure_cleans_lock(tmp_path, monkeypatch):
    import tempfile

    def fail(**kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(tempfile, "mkdtemp", fail)
    with pytest.raises(OSError), atomic_package(tmp_path / "output", False):
        pass
    assert not list(tmp_path.iterdir())
