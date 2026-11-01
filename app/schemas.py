from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=4000)
    conversation_id: int | None = Field(default=None, ge=1)


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    provider: str
    safety_triggered: bool = False


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime


class ConversationHistory(BaseModel):
    conversation_id: int
    title: str
    messages: list[MessageOut]


class HealthResponse(BaseModel):
    status: str
    llm_mode: str
