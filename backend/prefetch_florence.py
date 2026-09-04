"""One-shot Florence-2 weight prefetch (run in background, writes florence-dl.log)."""

from app.services.florence import _load

model, processor = _load()
print("florence ready:", type(model).__name__, flush=True)
