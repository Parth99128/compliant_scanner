"""Test bootstrap: disable API rate limits for the suite run.

Every test module shares one TestClient IP, so slowapi's per-minute buckets
would trip on routine register/login volume (see CI failure: 429s leaking
into test_phase4). Production is unaffected — the limiter reads this flag at
import time and defaults to enabled. test_rate_limit.py turns the limiter
back on explicitly around its own assertions.
"""

import os

os.environ.setdefault("TESTING", "1")
