"""Vercel Python function entrypoint.

Vercel treats files under api/ as serverless functions.  This shim exposes the FastAPI app
defined in backend/ so that /api/* requests (routed here by vercel.json) hit the real routes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.main import app  # noqa: E402, F401
