"""Optional generic local VLM reader (CPU, off by default).

Covers the gap Florence-2 leaves: free-form transcription of difficult
panels via an instruction-tuned vision-language model. Same honesty contract
as Florence-2 (see florence.py): text without word confidences, so its
`OcrResult.confidence` is 0.0 and arbitration only prefers it when Tesseract
is empty or weak (<60%). It never overrules a strong Tesseract read.

Gating (torch stays optional, never required):
- `VLM_ENABLED=true` in `.env`, otherwise every function returns None fast.
- torch + transformers import lazily; default `VLM_MODEL` downloads from
  Hugging Face on first use (~0.5 GB) — or run backend/prefetch_vlm.py ahead.
- Slow (~30-60 s/scan on laptop CPU): enable only where accuracy beats latency.

Never raises: every failure mode returns None.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.services.ocr import OcrResult

PROMPT = "Transcribe all visible label text verbatim, top to bottom. Reply with only the transcription."

_model = None
_processor = None


def is_enabled() -> bool:
    try:
        return get_settings().vlm_enabled.lower() == "true"
    except Exception:
        return False


def _load():
    """Lazily load the VLM on CPU. Raises ImportError/RuntimeError on failure."""
    global _model, _processor
    if _model is not None:
        return _model, _processor
    import torch  # lazy: torch stays optional for default installs
    from transformers import (  # type: ignore[import-untyped]
        AutoModelForVision2Seq,
        AutoProcessor,
    )

    model_id = get_settings().vlm_model
    _processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
    _model = AutoModelForVision2Seq.from_pretrained(
        model_id, trust_remote_code=True, torch_dtype=torch.float32
    ).eval()
    return _model, _processor


def run_vlm_ocr(image_bytes: bytes) -> OcrResult | None:
    """VLM transcription read. None when disabled, deps missing, or on any error."""
    if not is_enabled():
        return None
    try:
        import io

        from PIL import Image

        model, processor = _load()
        import torch

        img = Image.open(io.BytesIO(bytes(image_bytes))).convert("RGB")
        try:
            messages = [
                {
                    "role": "user",
                    "content": [{"type": "image"}, {"type": "text", "text": PROMPT}],
                }
            ]
            prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
            inputs = processor(text=prompt, images=[img], return_tensors="pt")
        except Exception:
            inputs = processor(images=[img], text=PROMPT, return_tensors="pt")
        with torch.no_grad():
            try:
                ids = model.generate(**inputs, max_new_tokens=512)
            except Exception:
                ids = model.generate(
                    inputs["input_ids"] if isinstance(inputs, dict) else inputs, max_new_tokens=512
                )
        try:
            text = processor.batch_decode(ids, skip_special_tokens=True)[0].strip()
        except Exception:
            text = ""
        # Strip chat scaffolding some templates echo ("User: ... Assistant: <text>").
        if "Assistant:" in text:
            text = text.split("Assistant:", 1)[1].strip()
        if text.lower().startswith("user:"):
            text = text[5:].strip()
        if not text:
            return None
        return OcrResult(text=text, engine="vlm", confidence=0.0)
    except Exception:
        return None
