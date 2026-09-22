import shutil
import subprocess
from pathlib import Path

from video2context.domain.models import OCRResult
from video2context.errors import ProviderError


class TesseractProvider:
    name = "tesseract"

    def __init__(self, language: str = "eng"):
        if not shutil.which("tesseract"):
            raise ProviderError("Local OCR unavailable. Install Tesseract to enable OCR.")
        self.language = language
        self.model = f"tesseract:{language}"

    def extract(self, image: Path) -> OCRResult:
        try:
            result = subprocess.run(
                ["tesseract", str(image), "stdout", "-l", self.language],
                capture_output=True,
                check=True,
                timeout=60,
            )
            return OCRResult(result.stdout.decode("utf-8", errors="replace").strip())
        except (OSError, subprocess.SubprocessError) as exc:
            raise ProviderError("Tesseract failed; check installation and language data.") from exc
