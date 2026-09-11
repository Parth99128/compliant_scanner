"""One-shot TrOCR weight prefetch (run in background, writes trocr-dl.log)."""

from app.services.trocr import _load

model, processor = _load()
print("trocr ready:", type(model).__name__, flush=True)
