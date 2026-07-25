from pathlib import Path

from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./hyperpulse.db"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3100"
    api_host: str = "0.0.0.0"
    api_port: int = 8100

    # Hyperliquid
    hyperliquid_api_url: str = "https://api.hyperliquid.xyz"
    hyperliquid_ws_url: str = "wss://api.hyperliquid.xyz/ws"
    hyperliquid_stats_url: str = "https://stats-data.hyperliquid.xyz/Mainnet"
    collector_enabled: bool = True
    collector_interval_seconds: int = 60
    tracked_trader_limit: int = 100
    whale_fetch_concurrency: int = 20
    # The leaderboard stats payload is tens of MB (all Hyperliquid traders), so
    # it is refreshed on its own slower cadence instead of every collector tick.
    trader_refresh_interval_seconds: int = 900

    # Data source
    use_mock_data: bool = False

    # AI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    langgraph_url: str = ""
    inference_interval_seconds: int = 120
    inference_trader_limit: int = 20
    market_brief_cooldown_seconds: int = 1200
    ai_provider: str = "auto"  # auto | openai | deepseek | heuristic

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    alerts_enabled: bool = True
    alert_min_confidence: float = 70.0
    alert_min_size_usd: float = 500_000.0
    # Global ceiling across all types (hard stop).
    alert_max_per_hour: int = 8
    # Per-type caps — tighter on noisier streams.
    # big_trade fires most often (size-based); consensus least (mood + cooldown).
    alert_limit_big_trade_per_hour: int = 2
    alert_limit_whale_move_per_hour: int = 3
    alert_limit_consensus_per_hour: int = 2
    alert_limit_squeeze_per_hour: int = 1
    alert_limit_style_per_hour: int = 1
    # Max events of one type in a single process_alert_triggers cycle.
    alert_big_trade_per_cycle: int = 1
    alert_whale_move_per_cycle: int = 1

    # Ranking
    ranking_interval_seconds: int = 90

    class Config:
        env_file = (str(BACKEND_DIR / ".env"), str(ROOT_DIR / ".env"))
        extra = "ignore"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_deepseek(self) -> bool:
        return bool(self.deepseek_api_key)


settings = Settings()
