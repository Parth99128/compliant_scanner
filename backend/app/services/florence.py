"""Optional Florence-2 VLM second-opinion OCR (local, CPU, off by default).

Florence-2 (Microsoft, MIT license) is a lightweight vision-language model
that reads label text via prompted generation ("<OCR>"). It complements
Tesseract: Tesseract wins on clean flat text; Florence-2 often recovers
stylized/low-contrast brand panels where Tesseract returns nothing.

Gating (delegation: torch stays optional, never required):
- `FLORENCE_ENABLED=true` in `.env`, otherwise every function returns None fast.
- torch + transformers are imported lazily inside `_load()` so a default
  install never pays import cost and never downloads weights.
- First enabled call downloads `FLORENCE_MODEL` (~1.5 GB for base) from
  Hugging Face and caches it; subsequent calls reuse the singleton.

Honesty note: Florence-2 emits text without word confidences, so its
`OcrResult.confidence` is 0.0 and arbitration (see `ocr.py`) only prefers it
when Tesseract is empty or weak (<60%). It never overrules a strong
Tesseract read.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.ocr import OcrResult

_model = None
_processor = None


def is_enabled() -> bool:
    try:
        return get_settings().florence_enabled.lower() == "true"
    except Exception:
        return False


def _load():
    """Lazily load Florence-2 on CPU. Raises ImportError/RuntimeError on failure."""
    global _model, _processor
    if _model is not None:
        return _model, _processor
    import torch  # lazy: torch stays optional for default installs
    from transformers import AutoModelForCausalLM, AutoProcessor

    settings = get_settings()
    model_id = settings.florence_model
    _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    _model = AutoModelForCausalLM.from_pretrained(
        model_id, trust_remote_code=True, torch_dtype=torch.float32
    ).eval()
    return _model, _processor


def run_florence_ocr(image_bytes: bytes) -> OcrResult | None:
    """Florence-2 '<OCR>' read. None when disabled, deps missing, or on any error."""
    if not is_enabled():
        return None
    try:
        import io

        from PIL import Image

        model, processor = _load()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = processor(text="<OCR>", images=img, return_tensors="pt")
        import torch

        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=1024, num_beams=1)
        text = processor.batch_decode(generated, skip_special_tokens=False)[0]
        parsed = processor.post_process_generation(text, task="<OCR>", image_size=(img.width, img.height))
        raw = parsed.get("<OCR>", "")
        cleaned = " ".join(raw.replace("\r", "\n").split())
        if not cleaned:
            return None
        # No word confidences from generative OCR -> 0.0 (see module docstring).
        return OcrResult(text=cleaned[:8000], engine="florence-2", confidence=0.0)
    except Exception:
        return None
