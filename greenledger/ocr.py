"""Optional local OCR for transient uploads using the provisional RapidOCR baseline."""

import hashlib
import importlib.metadata
import importlib.util
import io
import math
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_OCR_PAGES = 3
MAX_PAGE_PIXELS = 20_000_000
PDF_RENDER_SCALE = 2.0  # 144 dpi for a PDF whose canvas unit is one 1/72-inch point.
RAPIDOCR_MODEL_HASHES = {
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx": "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
    "PP-OCRv6_det_small.onnx": "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    "PP-OCRv6_rec_small.onnx": "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
}


class OCRInputError(ValueError):
    """An upload cannot be safely decoded for OCR."""


def get_ocr_runtime_status():
    try:
        import rapidocr  # noqa: F401
        import onnxruntime
        version = importlib.metadata.version("rapidocr")
        runtime_version = importlib.metadata.version("onnxruntime")
        return {
            "available": True,
            "engine": "RapidOCR",
            "version": version,
            "inference_runtime": "ONNX Runtime {} CPU".format(runtime_version),
            "pdf_renderer_available": importlib.util.find_spec("pypdfium2") is not None,
        }
    except Exception as error:
        return {
            "available": False,
            "engine": None,
            "version": None,
            "reason": "{}: {}".format(type(error).__name__, str(error)[:180]),
            "pdf_renderer_available": False,
        }


@lru_cache(maxsize=1)
def _get_rapidocr_engine():
    from rapidocr import RapidOCR
    model_root = ROOT / ".venv-ocr-eval" / "rapidocr_models"
    model_root.mkdir(parents=True, exist_ok=True)
    engine = RapidOCR(params={
        "Global.model_root_dir": str(model_root),
        "Rec.lang_type": "en",
        "EngineConfig.onnxruntime.intra_op_num_threads": 4,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    })
    for filename, expected_hash in RAPIDOCR_MODEL_HASHES.items():
        model_path = model_root / filename
        if not model_path.is_file() or hashlib.sha256(model_path.read_bytes()).hexdigest() != expected_hash:
            raise RuntimeError("RapidOCR model asset is missing or its checksum differs: {}".format(filename))
    return engine


def _images_from_upload(content, suffix):
    if suffix == ".pdf":
        try:
            import pypdfium2 as pdfium
        except ImportError as error:
            raise OCRInputError("PDF OCR needs the optional pypdfium2 renderer in the OCR environment.") from error

        document = None
        images = []
        try:
            document = pdfium.PdfDocument(io.BytesIO(content))
            page_count = len(document)
            if page_count == 0:
                raise OCRInputError("The PDF contains no pages.")
            for page_index in range(min(page_count, MAX_OCR_PAGES)):
                page = document[page_index]
                try:
                    width, height = page.get_size()
                    scale = min(PDF_RENDER_SCALE, math.sqrt(MAX_PAGE_PIXELS / max(1, width * height)))
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil().convert("RGB").copy()
                    finally:
                        bitmap.close()
                    images.append((page_index + 1, image, scale))
                finally:
                    page.close()
        except OCRInputError:
            raise
        except Exception as error:
            raise OCRInputError("The PDF could not be opened or rendered. Check that it is not damaged or password-protected.") from error
        finally:
            if document is not None:
                document.close()
        return images, page_count > MAX_OCR_PAGES

    if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        raise OCRInputError("This file type is not supported by the OCR baseline.")
    try:
        from PIL import Image
        source = Image.open(io.BytesIO(content))
        images = []
        frame_count = getattr(source, "n_frames", 1)
        with source:
            for frame_index in range(min(frame_count, MAX_OCR_PAGES)):
                source.seek(frame_index)
                width, height = source.size
                if width * height > MAX_PAGE_PIXELS:
                    raise OCRInputError("An image page is larger than the 20-megapixel local OCR limit.")
                images.append((frame_index + 1, source.convert("RGB").copy(), 1.0))
        return images, frame_count > MAX_OCR_PAGES
    except OCRInputError:
        raise
    except Exception as error:
        raise OCRInputError("The image could not be decoded. Check that the file is a valid supported image.") from error


def _page_text(result):
    if result is None:
        return ""
    lines = getattr(result, "txts", None)
    if lines is not None:
        return "\n".join(str(line) for line in lines if line is not None)
    if isinstance(result, (list, tuple)):
        return "\n".join(str(row[1]) for row in result if isinstance(row, (list, tuple)) and len(row) > 1)
    return str(result)


def recognize_upload(content, filename):
    """Run the provisional OCR baseline on an in-memory image or first PDF/TIFF pages."""
    if not content:
        return None
    suffix = Path(filename or "").suffix.casefold()
    file_hash = hashlib.sha256(content).hexdigest()
    try:
        status = get_ocr_runtime_status()
        if not status["available"]:
            return {
                "status": "OCR_RUNTIME_UNAVAILABLE",
                "warning": "The OCR runtime is not available. Enter values manually and verify them against the upload.",
                "sha256": file_hash,
                "filename": filename,
                "confidence": None,
                "pages": [],
                "transcription": "",
            }
        images, truncated = _images_from_upload(content, suffix)
        engine = _get_rapidocr_engine()
        import numpy as np
        import time
        page_results = []
        started = time.perf_counter()
        for page_number, image, render_scale in images:
            rgb = np.asarray(image.convert("RGB"))
            bgr = rgb[:, :, ::-1].copy()
            prediction = engine(bgr)
            page_results.append({
                "page": page_number,
                "text": _page_text(prediction),
                "render_scale": render_scale,
            })
        latency = time.perf_counter() - started
        transcript = "\n\n".join(page["text"] for page in page_results)
        return {
            "status": "OCR_COMPLETE" if transcript.strip() else "OCR_EMPTY",
            "warning": "" if transcript.strip() else "OCR returned no readable text. Check the source and enter values manually.",
            "engine": status["engine"],
            "engine_version": status["version"],
            "inference_runtime": status["inference_runtime"],
            "filename": filename,
            "sha256": file_hash,
            "page_count_processed": len(page_results),
            "page_limit": MAX_OCR_PAGES,
            "truncated": truncated,
            "latency_seconds": round(latency, 3),
            "confidence": None,
            "confidence_note": "Not calibrated for field correctness; human verification is required.",
            "pages": page_results,
            "transcription": transcript,
        }
    except OCRInputError as error:
        return {
            "status": "OCR_INPUT_REVIEW",
            "warning": str(error),
            "filename": filename,
            "sha256": file_hash,
            "confidence": None,
            "pages": [],
            "transcription": "",
        }
    except Exception as error:
        return {
            "status": "OCR_FAILED",
            "warning": "OCR could not process this upload ({}). Check it and enter values manually.".format(type(error).__name__),
            "filename": filename,
            "sha256": file_hash,
            "confidence": None,
            "pages": [],
            "transcription": "",
        }
