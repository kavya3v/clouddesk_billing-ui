"""ASGI entry point. No external calls or credential reads at import time."""
from uuid import uuid4
from typing import Annotated
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from backend.config import require_pipeline_settings
from backend.contracts import ChatRequest, ChatResponse, HealthResponse, ServiceErrorResponse
from backend.errors import ConfigurationError, PersistenceError
from backend.service import ChatService, RagChatService

app = FastAPI(title="CloudDesk Python backend", version="0.2.0")

def get_chat_service() -> ChatService:
    return RagChatService()

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        require_pipeline_settings()
    except ConfigurationError:
        return HealthResponse(rag_available=False)
    return HealthResponse(rag_available=True)

@app.post("/chat", response_model=ChatResponse,
          responses={503: {"model": ServiceErrorResponse}})
def chat(request: ChatRequest, service: Annotated[ChatService, Depends(get_chat_service)]):
    request_id = uuid4()
    try:
        return service.chat(request, request_id)
    except ConfigurationError:
        error = ServiceErrorResponse(error="configuration_error",
            message="The billing service is not configured.", request_id=request_id)
    except PersistenceError:
        error = ServiceErrorResponse(error="persistence_error",
            message="Required database writes could not be confirmed. A response cannot be provided.",
            request_id=request_id)
    return JSONResponse(status_code=503, content=error.model_dump(mode="json"))
