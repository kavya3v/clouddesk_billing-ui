"""Transport and provisional integration contracts; no RAG policy yet."""
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, StringConstraints

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1)]
Decision = Literal["answer", "escalate"]

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")

class ChatRequest(Contract):
    sessionId: Text
    chatInput: Text

class ChatResponse(Contract):
    output: Text
    decision: Decision
    sources: list[Text]
    request_id: UUID

class HealthResponse(Contract):
    status: Literal["ok"] = "ok"
    rag_available: bool = False

class UnavailableResponse(Contract):
    error: Literal["rag_unavailable"] = "rag_unavailable"
    message: str
    request_id: UUID

class Evidence(Contract):
    chunk_key: Text
    content: Text
    title: str | None = None
    source_type: str | None = None
    semantic_similarity: float | None = None
    hybrid_score: float | None = None

class RagDecision(Contract):
    decision: Decision
    answer: Text
    reason: Text
    sources: list[Text]

class GenerationResult(Contract):
    """Internal outcome, retaining diagnostics for future persistence."""
    question: str
    decision: Decision
    answer: str
    reason: str
    sources: list[str]
    retrieved_evidence: list[Evidence]
    validation_error: str | None = None

class ServiceErrorResponse(Contract):
    error: Literal["configuration_error", "persistence_error"]
    message: str
    request_id: UUID
