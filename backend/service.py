"""Full pipeline; reply only after all required insert confirmations."""
from typing import Protocol
from uuid import UUID
from backend.config import require_pipeline_settings
from backend.contracts import ChatRequest, ChatResponse
from backend.errors import InvalidVector, UpstreamError
from backend.integrations.embeddings import generate_query_embedding
from backend.integrations.retrieval import hybrid_search
from backend.integrations.evidence import filter_evidence
from backend.integrations.generation import generate_answer
from backend.integrations.validation import safe_escalation
from backend.integrations.persistence import log_query, create_escalation

class ChatService(Protocol):
    def chat(self, request: ChatRequest, request_id: UUID) -> ChatResponse: ...

class RagChatService:
    def __init__(self, *, client=None):
        self.client = client

    def chat(self, request: ChatRequest, request_id: UUID) -> ChatResponse:
        require_pipeline_settings()
        question = request.chatInput
        # Raw RPC rows and eligible model context have separate lifetimes.
        all_retrieved = []
        eligible = []
        stage = "embedding"
        try:
            vector = generate_query_embedding(question, client=self.client)
            stage = "retrieval"
            all_retrieved = hybrid_search(question, vector, client=self.client)
            eligible = filter_evidence(all_retrieved)
        except (UpstreamError, InvalidVector) as error:
            code = str(error) if isinstance(error, UpstreamError) else "embedding: invalid_vector"
            reason = "Query embedding request failed" if stage == "embedding" else "Support search request failed."
            result = safe_escalation(question, [], reason,
                "I can\u2019t verify an answer right now because of a technical issue. Human review is needed.", code)
        else:
            result = generate_answer(question, eligible, client=self.client)
        log_query(request, result, request_id, all_retrieved, client=self.client)
        if result.decision == "escalate":
            create_escalation(request, result, request_id, all_retrieved, client=self.client)
        return ChatResponse(output=result.answer, decision=result.decision,
                            sources=result.sources, request_id=request_id)
