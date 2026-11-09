"""Query embedding behavior from reference/n8nworkflow.json."""
import math
import os
from backend.errors import ConfigurationError, InvalidVector, UpstreamError
from backend.integrations.transport import post_json

MODEL = "nomic-ai/nomic-embed-text-v1.5"
PREFIX = "search_query: "
# Workflow requests the model default, with no dimensions override.
DIMENSIONS = 768

def validate_vector(vector):
    if (not isinstance(vector, list) or len(vector) != DIMENSIONS
        or any(type(x) not in (int, float) or not math.isfinite(x) for x in vector)
        or not any(x != 0 for x in vector)):
        raise InvalidVector("Expected a finite, non-zero 768-dimensional numeric vector.")
    return vector

def generate_query_embedding(question: str, *, client=None) -> list[float]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must be a non-empty string.")
    key = os.environ.get("FIREWORKS_API_KEY", "").strip()
    if not key:
        raise ConfigurationError("FIREWORKS_API_KEY is required.")
    data = post_json("https://api.fireworks.ai/inference/v1/embeddings",
                     {"Authorization": "Bearer " + key},
                     {"model": MODEL, "input": PREFIX + question}, "embedding", client)
    try:
        vector = data["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError):
        raise UpstreamError("embedding", "invalid_response") from None
    return validate_vector(vector)
