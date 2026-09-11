"""One-shot generic-VLM weight prefetch (run in background, writes vlm-dl.log)."""

from app.services.vlm import _load

model, processor = _load()
print("vlm ready:", type(model).__name__, flush=True)
