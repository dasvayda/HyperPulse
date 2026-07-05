"""One-off script to exercise FastAPI lifespan bootstrap and surface errors."""
from __future__ import annotations

import asyncio
import logging
import traceback

logging.basicConfig(level=logging.INFO)

from app.main import app, lifespan  # noqa: E402


async def main() -> None:
    try:
        async with lifespan(app):
            print("LIFESPAN_OK")
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
