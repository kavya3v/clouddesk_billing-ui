"""One-shot live evaluation. Existing attempt journals prohibit accidental reruns."""
import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference/results_execution_132.csv"
OUTPUT = ROOT / "evaluation/python_execution_132_comparison.csv"
JOURNAL = ROOT / "evaluation/python_execution_132_attempts.json"
FIELDS = ["test_case_id", "question", "expected_decision", "actual_decision", "http_status",
          "request_id", "answer", "sources", "validation_error", "technical_fallback"]


def main():
    logging.disable(logging.CRITICAL)
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        cases = list(csv.DictReader(handle))
    assert len(cases) == 20 and len({c["test_case_id"] for c in cases}) == 20, "Expected 20 unique cases"
    assert {c["test_case_id"] for c in cases} == {f"final-{i:02}" for i in range(1, 21)}, "Unexpected case IDs"
    assert all(c["execution_id"] == "132" for c in cases), "Unexpected execution ID"
    assert sum(c["expected_decision"] == "answer" for c in cases) == 10
    assert sum(c["expected_decision"] == "escalate" for c in cases) == 10
    baseline = sum(c["decision"] == c["expected_decision"] for c in cases)
    print(json.dumps({"source_verified": True, "cases": 20, "n8n_agreement": baseline}), flush=True)
    if OUTPUT.exists() or JOURNAL.exists():
        print("Existing evaluation output or attempt journal found. Stopped without submitting requests.")
        return
    settings = dotenv_values(ROOT / ".env")
    names = ("FIREWORKS_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    missing = [n for n in names if not str(settings.get(n) or "").strip()]
    if missing:
        print(json.dumps({"missing_variables": missing})); return
    with httpx.Client(transport=httpx.HTTPTransport(retries=0), trust_env=False, timeout=5) as preflight:
        try:
            response = preflight.get("http://127.0.0.1:8000/health")
            health = response.json()
            if response.status_code != 200 or health.get("status") != "ok" or health.get("rag_available") is not True:
                print(json.dumps({"blocker": "Backend health/configuration check failed", "http_status": response.status_code})); return
        except Exception as error:
            print(json.dumps({"blocker": "Local /health unavailable", "error_type": type(error).__name__})); return
    print(json.dumps({"health_verified": True}), flush=True)
    records = [{field: "" for field in FIELDS} for _ in cases]
    for row, case in zip(records, cases):
        row.update({name: case[name] for name in ("test_case_id", "question", "expected_decision")})
        row.update(validation_error="UNVERIFIED: not attempted", technical_fallback="unknown")
    journal = {"sessionId": "evaluation-132-" + str(uuid4()), "source": SOURCE.name, "attempts": []}
    with JOURNAL.open("x", encoding="utf-8") as handle:
        json.dump(journal, handle, indent=2)

    def save():
        # fsync before requests ensures attempts survive interrupted writes/processes.
        temp = OUTPUT.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader(); writer.writerows(records); handle.flush(); os.fsync(handle.fileno())
        temp.replace(OUTPUT)
        temp = JOURNAL.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            json.dump(journal, handle, ensure_ascii=True, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        temp.replace(JOURNAL)

    secrets = [str(v) for k, v in settings.items() if v and any(t in k.upper() for t in ("KEY", "PASSWORD", "TOKEN", "SECRET"))]
    def clean(value):
        text = str(value)
        for secret in secrets: text = text.replace(secret, "[redacted]")
        return text
    save()
    headers = {"apikey": settings["SUPABASE_SERVICE_ROLE_KEY"].strip(),
               "Authorization": "Bearer " + settings["SUPABASE_SERVICE_ROLE_KEY"].strip()}
    db_url = settings["SUPABASE_URL"].strip().rstrip("/")
    with httpx.Client(transport=httpx.HTTPTransport(retries=0), trust_env=False, timeout=360) as local, httpx.Client(transport=httpx.HTTPTransport(retries=0), timeout=30, follow_redirects=False) as database:
        for case, row in zip(cases, records):
            attempt = {"test_case_id": case["test_case_id"], "started_at": datetime.now(timezone.utc).isoformat(), "state": "attempt_recorded_before_send"}
            journal["attempts"].append(attempt)
            row["validation_error"] = "UNVERIFIED: attempt started"
            save()
            try:
                response = local.post("http://127.0.0.1:8000/chat", json={"sessionId": journal["sessionId"], "chatInput": case["question"]})
                row["http_status"] = response.status_code
                try: body = response.json()
                except ValueError: body = {}
                if not isinstance(body, dict): body = {}
                row["request_id"] = body.get("request_id", "")
                if response.status_code == 200 and body.get("decision") in ("answer", "escalate"):
                    row["actual_decision"] = body["decision"]
                row["answer"] = clean(body.get("output", ""))
                row["sources"] = clean(json.dumps(body.get("sources", []), ensure_ascii=True))
                row["technical_fallback"] = "true" if response.status_code != 200 or "technical issue" in row["answer"].lower() else "unknown"
                attempt["state"] = "response_received"
                attempt["request_id"] = row["request_id"]
                save()
                if row["request_id"]:
                    try:
                        read = database.get(db_url + "/rest/v1/support_query_logs", headers=headers,
                            params={"execution_id": "eq.python:" + row["request_id"], "select": "id,question,decision,answer,reason,validation_error"})
                        logs = read.json() if read.status_code == 200 else None
                        verified = (isinstance(logs, list) and len(logs) == 1 and logs[0].get("question") == case["question"])
                        if verified:
                            log = logs[0]
                            error = log.get("validation_error")
                            row["validation_error"] = clean(error) if error is not None else "null"
                            # Count validation fallbacks as degraded outcomes as well as transport failures.
                            row["technical_fallback"] = "true" if error is not None or "technical issue" in log.get("answer", "").lower() else "false"
                            attempt["verified_log_id"] = log["id"]
                            attempt["saved_reason"] = clean(log.get("reason", ""))
                            attempt["saved_decision_matches"] = log.get("decision") == row["actual_decision"]
                            attempt["saved_answer_matches"] = log.get("answer") == body.get("output")
                        else: row["validation_error"] = "UNVERIFIED: no unique matching query log"
                    except Exception as error:
                        row["validation_error"] = "UNVERIFIED: database read " + type(error).__name__
                else: row["validation_error"] = "UNVERIFIED: response has no request_id"
            except Exception as error:
                row["validation_error"] = "UNVERIFIED: request " + type(error).__name__
                row["technical_fallback"] = "true"
                attempt["state"] = "request_outcome_unknown_no_retry"
            attempt["finished_at"] = datetime.now(timezone.utc).isoformat()
            save()
            print(json.dumps({"case": row["test_case_id"], "http_status": row["http_status"], "decision": row["actual_decision"], "technical_fallback": row["technical_fallback"], "validation_error": row["validation_error"]}), flush=True)
    agreement = sum(r["actual_decision"] == r["expected_decision"] for r in records)
    answerable = sum(r["expected_decision"] == "answer" and r["actual_decision"] == "answer" for r in records)
    escalations = sum(r["expected_decision"] == "escalate" and r["actual_decision"] == "escalate" for r in records)
    summary = {"agreement_out_of_20": agreement, "answerable_answered_out_of_10": answerable,
               "required_escalations_out_of_10": escalations, "n8n_baseline_out_of_20": baseline,
               "technical_fallback_cases": [r["test_case_id"] for r in records if r["technical_fallback"] == "true"],
               "unverified_cases": [r["test_case_id"] for r in records if r["validation_error"].startswith("UNVERIFIED")],
               "misses": [r["test_case_id"] for r in records if r["actual_decision"] != r["expected_decision"]]}
    journal["summary"] = summary; save()
    print(json.dumps(summary), flush=True)

if __name__ == "__main__":
    main()
