"""Port of Validate Decision. Checks citations/shape, not semantic entailment."""
import json
import math
from backend.contracts import Evidence, GenerationResult


def safe_escalation(question, evidence, reason, answer, validation_error=None):
    return GenerationResult(question=question, decision="escalate", answer=answer,
                            reason=reason, sources=[], retrieved_evidence=evidence,
                            validation_error=validation_error)


def validate_response(raw_response, evidence: list[Evidence], *, question: str = "") -> GenerationResult:
    error = None
    try:
        choices = raw_response.get("choices") if isinstance(raw_response, dict) else None
        choice = choices[0] if isinstance(choices, list) and choices else None
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise ValueError("Response incomplete or missing")
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        try:
            if not isinstance(content, str):
                raise ValueError()
            result = json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        except (ValueError, TypeError):
            raise ValueError("Invalid response JSON") from None
        allowed = {item.chunk_key for item in evidence}
        if (not isinstance(result, dict)
            or result.get("decision") not in ("answer", "escalate")
            or not isinstance(result.get("answer"), str) or not result["answer"].strip()
            or not isinstance(result.get("reason"), str) or not result["reason"].strip()
            or not isinstance(result.get("sources"), list)
            or not all(isinstance(source, str) and source in allowed for source in result["sources"])):
            raise ValueError("Invalid response fields or source IDs")
        if result["decision"] == "answer":
            if not result["sources"] or not all(f"[{source}]" in result["answer"] for source in result["sources"]):
                raise ValueError("Answer lacks supporting citations")
            cited = [item for item in evidence if item.chunk_key in result["sources"]]
            if any(type(item.semantic_similarity) not in (int, float)
                   or not math.isfinite(item.semantic_similarity) or item.semantic_similarity < 0.65 for item in cited):
                raise ValueError("Cited evidence is below the retrieval threshold")
        else:
            result["sources"] = []
            result["answer"] = "I can\u2019t resolve this from the available information. Human review is needed."
        return GenerationResult(question=question, decision=result["decision"], answer=result["answer"],
                                reason=result["reason"], sources=result["sources"],
                                retrieved_evidence=evidence, validation_error=None)
    except ValueError as exc:
        error = str(exc)
    return safe_escalation(question, evidence, "Response validation failed: " + error,
                           "I can\u2019t provide a verified answer right now. Human review is needed.", error)
