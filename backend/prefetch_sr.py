"""One-shot ESPCN super-resolution weight prefetch (writes sr-dl.log).

Source: fannymonori/TF-ESPCN (GSoC 2019 with OpenCV — the exact weights the
OpenCV dnn_superres docs reference), export/ESPCN_x2.pb (~86 KB). Skips when
models/ESPCN_x2.pb already exists. The micro-text path in vision.py picks it
up automatically; without it, cubic upscaling is used.
"""

import os
import sys
import urllib.request
from pathlib import Path

URL = "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x2.pb"
DEST = Path(__file__).resolve().parents[1] / "models" / "ESPCN_x2.pb"

if DEST.exists() and DEST.stat().st_size > 50000:
    print(f"present: {DEST} ({DEST.stat().st_size} bytes)", flush=True)
    sys.exit(0)

DEST.parent.mkdir(parents=True, exist_ok=True)
req = urllib.request.Request(URL, headers={"User-Agent": "DrishtiLM-SIH26034/1.0"})
with urllib.request.urlopen(req, timeout=120) as resp, open(DEST, "wb") as fh:
    fh.write(resp.read())
print(f"saved {DEST} ({DEST.stat().st_size} bytes)", flush=True)
if DEST.stat().st_size < 50000:
    os.remove(DEST)
    sys.exit("download too small — not a valid model file")
