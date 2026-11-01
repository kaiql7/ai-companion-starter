from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

import httpx


@dataclass(frozen=True)
class ModelMessage:
    role: str
    content: str


class LLMError(RuntimeError):
    """A provider error that is safe to expose as an upstream failure."""


class LLMClient(ABC):
    provider: str

    @abstractmethod
    def complete(self, messages: Sequence[ModelMessage]) -> str:
        """Return one assistant response for the supplied messages."""
        raise NotImplementedError


class MockLLMClient(LLMClient):
    """Deterministic client used for learning and automated tests."""

    provider = "mock"

    def complete(self, messages: Sequence[ModelMessage]) -> str:
        user_messages = [m.content for m in messages if m.role == "user"]
        latest = user_messages[-1] if user_messages else ""
        excerpt = latest[:80]
        return (
            f"我在听。你刚才说的是“{excerpt}”。"
            "现在是模拟模式，所以这句话不会发送给真实模型。"
            "你可以继续告诉我：这件事最让你困扰的是哪一部分？"
        )


class DeepSeekLLMClient(LLMClient):
    """Minimal direct-HTTP client for DeepSeek's OpenAI-compatible API."""

    provider = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-flash",
        timeout_seconds: float = 40.0,
    ) -> None:
        if not api_key:
            raise ValueError("使用 deepseek 模式时必须设置 DEEPSEEK_API_KEY")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def complete(self, messages: Sequence[ModelMessage]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            "temperature": 0.7,
            "stream": False,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMError("模型服务响应超时，请稍后重试") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise LLMError(f"模型服务返回 HTTP {status}，请检查配置或额度") from exc
        except httpx.HTTPError as exc:
            raise LLMError("无法连接模型服务，请检查网络") from exc

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("模型返回了无法解析的数据") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("模型返回了空内容")
        return content.strip()
