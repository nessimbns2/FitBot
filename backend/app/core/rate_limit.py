"""
app/core/rate_limit.py
Shared SlowAPI limiter so routers can decorate endpoints without importing main_v2.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
