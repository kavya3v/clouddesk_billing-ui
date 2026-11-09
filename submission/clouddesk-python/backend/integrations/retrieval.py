"""Call the existing RPC; never execute SQL or alter Supabase schema."""
import json
import os
from urllib.parse import urlsplit
from backend.contracts import Evidence
from backend.errors import ConfigurationError, UpstreamError
from backend.integrations.embeddings import generate_query_embedding, validate_vector
from backend.integrations.evidence import filter_evidence
from backend.integrations.transport import post_json

def hybrid_search(question: str, embedding: list[float], *, client=None) -> list[dict]:
    validate_vector(embedding)
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must be a non-empty string.")
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    parts = urlsplit(url)
    if not url or not key:
        raise ConfigurationError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.")
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment or parts.path:
        raise ConfigurationError("SUPABASE_URL must be an HTTPS project origin.")
    rows = post_json(url + "/rest/v1/rpc/hybrid_search_support",
                     {"apikey": key, "Authorization": "Bearer " + key},
                     {"query_text": question, "query_embedding": json.dumps(embedding), "match_count": 5},
                     "retrieval", client)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise UpstreamError("retrieval", "invalid_response")
    return rows

def retrieve_evidence(question: str, *, client=None) -> list[Evidence]:
    vector = generate_query_embedding(question, client=client)
    return filter_evidence(hybrid_search(question, vector, client=client))
