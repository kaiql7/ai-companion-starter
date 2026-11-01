from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Runtime configuration collected from environment variables."""

    llm_mode: str
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    database_url: str
    history_limit: int

    @classmethod
    def from_env(cls) -> "Settings":
        mode = os.getenv("LLM_MODE", "mock").strip().lower()
        if mode not in {"mock", "deepseek"}:
            raise ValueError("LLM_MODE 只能是 mock 或 deepseek")

        history_limit = int(os.getenv("HISTORY_LIMIT", "20"))
        if history_limit < 1 or history_limit > 100:
            raise ValueError("HISTORY_LIMIT 必须在 1 到 100 之间")

        return cls(
            llm_mode=mode,
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_base_url=os.getenv(
                "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
            ).strip(),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip(),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./companion.db").strip(),
            history_limit=history_limit,
        )
