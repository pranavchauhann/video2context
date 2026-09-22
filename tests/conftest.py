import shutil
import subprocess

import pytest


@pytest.fixture
def make_video(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Integration fixtures require FFmpeg and ffprobe")

    def make(name="fixture", *, duration=6, audio=False, static=False):
        path = tmp_path / f"{name}.mp4"
        source = "color=c=0x192335:s=320x180:r=5" if static else "testsrc2=s=320x180:r=5"
        args = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", source]
        if audio:
            args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=16000"]
        args += ["-t", str(duration), "-c:v", "mpeg4", "-q:v", "5", "-pix_fmt", "yuv420p"]
        if audio:
            args += ["-c:a", "aac"]
        subprocess.run([*args, str(path)], check=True, capture_output=True, timeout=120)
        return path

    return make
