"""One-off integration test for OpenAI + Telegram configuration."""

from __future__ import annotations

import asyncio
import json

from app.config import settings
from app.services.alerts import _send_telegram
from app.services.inference import _llm_inference
from app.data.seed import TRADERS


async def main() -> None:
    print("telegram_configured:", settings.telegram_configured)
    print("has_openai:", settings.has_openai)
    print("has_deepseek:", settings.has_deepseek)
    print("ai_provider:", settings.ai_provider)

    print("\n[Telegram] sending test message...")
    ok = await _send_telegram(
        "<b>HyperPulse test</b>\nConnection check from integration test."
    )
    print("telegram_send_ok:", ok)

    print("\n[OpenAI] running single inference...")
    trader = TRADERS[0]
    result = await _llm_inference(trader, "openai")
    if result is None:
        print("openai_inference: FAILED (fallback would be used)")
    else:
        print(
            "openai_inference:",
            json.dumps(
                {
                    "trader": result.trader_alias,
                    "strategy": result.strategy,
                    "provider": result.provider,
                    "confidence": result.confidence,
                },
                ensure_ascii=False,
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
