import shutil
import subprocess
from pathlib import Path

from video2context.domain.models import OCRResult
from video2context.errors import ProviderError


def installed_languages(executable: str = "tesseract") -> list[str]:
    try:
        result = subprocess.run(
            [executable, "--list-langs"], capture_output=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return []
    # The header line is followed by one language code per line.
    lines = (result.stdout + result.stderr).decode("utf-8", errors="replace").splitlines()
    return [line.strip() for line in lines[1:] if line.strip() and " " not in line.strip()]


class TesseractProvider:
    name = "tesseract"

    def __init__(self, language: str = "eng"):
        if not shutil.which("tesseract"):
            raise ProviderError(
                "Local OCR unavailable: Tesseract is not installed (macOS: brew install "
                "tesseract; Ubuntu: sudo apt install tesseract-ocr). Use --no-ocr to skip."
            )
        languages = installed_languages()
        missing = [code for code in language.split("+") if languages and code not in languages]
        if missing:
            raise ProviderError(
                f"Tesseract language data missing for {'+'.join(missing)!r}; installed: "
                f"{', '.join(languages) or 'none'}. Set ocr_language to an installed code."
            )
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
