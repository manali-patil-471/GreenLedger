"""Download and checksum-check the pinned English Tesseract model for OCR evaluation."""

import hashlib
import os
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = (
    "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/"
    "87416418657359cb625c412a48b6e1d6d41c29bd/eng.traineddata"
)
MODEL_SHA256 = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"
MODEL_PATH = ROOT / ".venv-ocr-eval" / "tessdata" / "eng.traineddata"


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MODEL_PATH.is_file():
        actual_hash = file_sha256(MODEL_PATH)
        if actual_hash == MODEL_SHA256:
            print("Verified existing Tesseract English model: {}".format(MODEL_PATH))
            return 0
        raise SystemExit("Existing model has an unexpected SHA256; refusing to overwrite it.")

    temporary_path = MODEL_PATH.with_suffix(".traineddata.download")
    digest = hashlib.sha256()
    try:
        with urlopen(MODEL_URL, timeout=60) as response, temporary_path.open("wb") as destination:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                destination.write(chunk)
        actual_hash = digest.hexdigest()
        if actual_hash != MODEL_SHA256:
            raise SystemExit("Downloaded model SHA256 mismatch: {}".format(actual_hash))
        os.replace(str(temporary_path), str(MODEL_PATH))
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    print("Downloaded and verified Tesseract English model: {}".format(MODEL_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
