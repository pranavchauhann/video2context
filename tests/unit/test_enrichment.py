from pathlib import Path

from video2context.cache import Cache
from video2context.domain.models import FrameRef, OCRResult
from video2context.enrichment import enrich_frames
from video2context.errors import ProviderAuthError, ProviderError


def make_frames(root: Path, count: int) -> list[FrameRef]:
    (root / "frames").mkdir(exist_ok=True)
    frames = []
    for i in range(count):
        path = root / "frames" / f"{i:09d}.jpg"
        path.write_bytes(bytes([i]))
        frames.append(FrameRef(f"f_{i + 1:06d}", float(i), f"frames/{path.name}"))
    return frames


def test_failures_are_summarized_not_repeated_per_frame(tmp_path):
    class Flaky:
        name = "flaky"
        model = "v1"

        def extract(self, image):
            if image.name.endswith("0.jpg"):
                return OCRResult("text")
            raise ProviderError("Tesseract failed; check installation and language data.")

    frames = make_frames(tmp_path, 4)
    warnings = []
    result = enrich_frames(
        frames, tmp_path, Cache(tmp_path / "cache"), Flaky(), "ocr", {}, 2, warnings.append
    )
    assert set(result) == {"f_000001"}
    assert len(warnings) == 1
    assert "3 of 4 frames" in warnings[0]
    assert "Tesseract failed" in warnings[0]


def test_rejected_credentials_stop_further_requests(tmp_path):
    calls = []

    class Unauthorized:
        name = "vision"
        model = "v1"

        def describe(self, image, context):
            calls.append(image)
            raise ProviderAuthError("Remote provider rejected the API key (HTTP 401).")

    frames = make_frames(tmp_path, 10)
    warnings = []
    result = enrich_frames(
        frames,
        tmp_path,
        Cache(tmp_path / "cache"),
        Unauthorized(),
        "vision",
        {},
        1,
        warnings.append,
    )
    assert result == {}
    assert len(calls) == 1
    assert any("rejected the API key" in w for w in warnings)
    assert any("skipped" in w for w in warnings)


def test_unexpected_exceptions_never_leak(tmp_path):
    class Leaky:
        name = "leaky"
        model = "v1"

        def extract(self, image):
            raise RuntimeError("authorization=SECRET")

    frames = make_frames(tmp_path, 2)
    warnings = []
    enrich_frames(
        frames, tmp_path, Cache(tmp_path / "cache"), Leaky(), "ocr", {}, 1, warnings.append
    )
    assert warnings and all("SECRET" not in w for w in warnings)


def test_cache_directory_is_created_lazily(tmp_path):
    cache = Cache(tmp_path / "cache")
    assert not cache.root.exists()
    source = tmp_path / "source"
    source.write_bytes(b"x")
    cache.get_or_compute(source, {}, lambda: 1)
    assert cache.root.is_dir()
