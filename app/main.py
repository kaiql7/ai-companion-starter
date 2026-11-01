from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Database
from app.llm import DeepSeekLLMClient, LLMClient, LLMError, MockLLMClient
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    HealthResponse,
    MessageOut,
)
from app.services import ChatService, ConversationNotFound


STATIC_DIR = Path(__file__).resolve().parent / "static"


def get_db(request: Request) -> Generator[Session, None, None]:
    database: Database = request.app.state.database
    with database.session_factory() as session:
        yield session


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "deepseek":
        return DeepSeekLLMClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
    return MockLLMClient()


def create_app(
    *,
    database_url: str | None = None,
    llm_client: LLMClient | None = None,
) -> FastAPI:
    settings = Settings.from_env()
    database = Database(database_url or settings.database_url)
    llm = llm_client or build_llm(settings)
    service = ChatService(llm=llm, history_limit=settings.history_limit)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        database.create_all()
        yield
        database.engine.dispose()

    app = FastAPI(
        title="AI 智能伴侣 Starter",
        version="1.0.0",
        description="用于学习 FastAPI、DeepSeek、SQLAlchemy 和 MySQL 的最小项目。",
        lifespan=lifespan,
    )
    app.state.database = database
    app.state.chat_service = service
    app.state.llm_mode = llm.provider
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", llm_mode=llm.provider)

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(
        payload: ChatRequest,
        db: Session = Depends(get_db),
        request: Request = None,
    ) -> ChatResponse:
        chat_service: ChatService = request.app.state.chat_service
        try:
            result = chat_service.chat(db, payload)
        except ConversationNotFound as exc:
            raise HTTPException(status_code=404, detail="对话不存在") from exc
        except LLMError as exc:
            db.rollback()
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return ChatResponse(
            conversation_id=result.conversation_id,
            reply=result.reply,
            provider=result.provider,
            safety_triggered=result.safety_triggered,
        )

    @app.get(
        "/api/conversations/{conversation_id}",
        response_model=ConversationHistory,
    )
    def conversation_history(
        conversation_id: int,
        db: Session = Depends(get_db),
        request: Request = None,
    ) -> ConversationHistory:
        chat_service: ChatService = request.app.state.chat_service
        try:
            conversation = chat_service.get_history(db, conversation_id)
        except ConversationNotFound as exc:
            raise HTTPException(status_code=404, detail="对话不存在") from exc

        return ConversationHistory(
            conversation_id=conversation.id,
            title=conversation.title,
            messages=[MessageOut.model_validate(item) for item in conversation.messages],
        )

    @app.delete("/api/conversations/{conversation_id}", status_code=204)
    def delete_conversation(
        conversation_id: int,
        db: Session = Depends(get_db),
        request: Request = None,
    ) -> None:
        chat_service: ChatService = request.app.state.chat_service
        try:
            chat_service.delete_conversation(db, conversation_id)
        except ConversationNotFound as exc:
            raise HTTPException(status_code=404, detail="对话不存在") from exc

    return app


app = create_app()
