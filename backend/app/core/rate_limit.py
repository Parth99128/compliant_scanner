import os

from slowapi import Limiter
from slowapi.util import get_remote_address

# Disabled under TESTING=1 (see backend/tests/conftest.py): the whole suite
# shares one TestClient IP, so per-minute buckets would trip on test volume.
# Production always runs with limits on. test_rate_limit.py re-enables the
# limiter explicitly for its own assertions.
limiter = Limiter(key_func=get_remote_address, enabled=os.environ.get("TESTING", "0") != "1")
