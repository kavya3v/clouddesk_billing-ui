"""Eligibility from Prepare Evidence; retain all SQL return fields and order."""
import math
from pydantic import ValidationError
from backend.contracts import Evidence

MIN_SIMILARITY = 0.65

def filter_evidence(rows: list[dict]) -> list[Evidence]:
    evidence = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("chunk_key") or not row.get("content"):
            continue
        score = row.get("semantic_similarity")
        if score is None or score == "":
            continue
        try:
            score = float(score)
        except (TypeError, ValueError, OverflowError):
            continue
        if not math.isfinite(score) or score < MIN_SIMILARITY:
            continue
        try:
            evidence.append(Evidence.model_validate({**row, "semantic_similarity": score}))
        except ValidationError:
            continue
    return evidence
