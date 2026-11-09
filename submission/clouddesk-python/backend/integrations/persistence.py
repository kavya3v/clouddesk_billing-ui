"""Insert-only persistence using the table definitions supplied by the owner.

execution_id is text NOT NULL. python:<UUID> is deliberately not an n8n ID.
No schema changes, retries, upserts, or assumptions about additional columns.
"""
from uuid import UUID
from backend.config import supabase_settings
from backend.contracts import ChatRequest, GenerationResult
from backend.errors import ConfigurationError, PersistenceError, UpstreamError
from backend.integrations.transport import post_json


def insert_row(table: str, payload: dict, *, client=None) -> int:
    try:
        url, key = supabase_settings()
        rows = post_json(url + "/rest/v1/" + table,
                         {"apikey": key, "Authorization": "Bearer " + key,
                          "Prefer": "return=representation"}, payload, "persistence", client)
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
            or type(rows[0].get("id")) is not int):
            raise PersistenceError()
        return rows[0]["id"]
    except (ConfigurationError, UpstreamError):
        # A timeout may happen after commit. Do not claim the insert failed to commit.
        raise PersistenceError() from None


def log_query(request: ChatRequest, decision: GenerationResult, request_id: UUID,
              all_retrieved: list[dict], *, client=None) -> int:
    return insert_row("support_query_logs", {
        "execution_id": "python:" + str(request_id),
        "question": request.chatInput,
        "decision": decision.decision,
        "answer": decision.answer,
        "reason": decision.reason,
        "sources": decision.sources,
        "retrieved_evidence": all_retrieved,
        "validation_error": decision.validation_error,
        "test_set": "production",
        "test_case_id": None,
        "expected_decision": None,
    }, client=client)


def create_escalation(request: ChatRequest, decision: GenerationResult, request_id: UUID,
                      all_retrieved: list[dict], *, client=None) -> int:
    if decision.decision != "escalate":
        raise ValueError("Only escalation decisions can create a review case.")
    return insert_row("support_escalations", {
        "execution_id": "python:" + str(request_id),
        "question": request.chatInput,
        "reason": decision.reason,
        "customer_message": decision.answer,
        "retrieved_evidence": all_retrieved,
        "status": "open",
    }, client=client)
