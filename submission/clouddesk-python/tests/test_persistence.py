import json
import unittest
from unittest.mock import patch
from uuid import UUID
import httpx
from fastapi.testclient import TestClient
from backend.main import app, get_chat_service
from backend.service import RagChatService

ENV = {"FIREWORKS_API_KEY":"private-fireworks", "SUPABASE_URL":"https://example.supabase.co",
       "SUPABASE_SERVICE_ROLE_KEY":"private-supabase"}
ROWS = [dict(chunk_key="faq-1",content="Billing guide",title="Guide",source_type="faq",semantic_similarity=s,hybrid_score=0.02) for s in (0.8,0.4)]

class PersistenceTests(unittest.TestCase):
    def tearDown(self):
        app.dependency_overrides.clear()

    def run_chat(self, decision="answer", fail=None, upstream=None):
        calls=[]
        def handler(request):
            payload=json.loads(request.content)
            path=request.url.path
            calls.append((path,payload))
            if path.endswith("embeddings"):
                if upstream: return httpx.Response(503,text="private-fireworks")
                return httpx.Response(200,json={"data":[{"embedding":[0.1]*768}]})
            if path.endswith("hybrid_search_support"): return httpx.Response(200,json=ROWS)
            if path.endswith("completions"):
                evidence=json.loads(payload["messages"][1]["content"])["evidence"]
                self.assertEqual(len(evidence),1)
                return httpx.Response(200,json={"choices":[{"finish_reason":"stop","message":{"content":json.dumps(dict(decision=decision,answer="Guide [faq-1]",reason="Evidence",sources=["faq-1"] if decision=="answer" else []))}}]})
            if path.endswith(fail or "NEVER"):
                return httpx.Response(503,text="private-supabase")
            self.assertEqual(request.headers["prefer"],"return=representation")
            return httpx.Response(201,json=[dict(payload,id=1)])
        with patch.dict("os.environ",ENV,clear=True), httpx.Client(transport=httpx.MockTransport(handler)) as upstream_client:
            app.dependency_overrides[get_chat_service]=lambda: RagChatService(client=upstream_client)
            with TestClient(app) as client:
                response=client.post("/chat",json={"sessionId":"s","chatInput":"Invoices?"})
        return response,calls

    def test_answer_logging(self):
        response,calls=self.run_chat()
        self.assertEqual(response.status_code,200)
        body=response.json(); UUID(body["request_id"])
        log=calls[-1][1]
        self.assertTrue(calls[-1][0].endswith("support_query_logs"))
        self.assertEqual(log["execution_id"],"python:"+body["request_id"])
        self.assertEqual(log["retrieved_evidence"],ROWS)
        for key in ("expected_decision","test_case_id","validation_error"): self.assertIsNone(log[key])
        self.assertEqual(log["decision"],"answer")
        self.assertEqual(log["sources"],["faq-1"])

    def test_escalation_logging_and_case(self):
        response,calls=self.run_chat("escalate")
        self.assertEqual(response.status_code,200)
        log,case=calls[-2][1],calls[-1][1]
        self.assertEqual(log["decision"],"escalate")
        self.assertEqual(case["status"],"open")
        self.assertEqual(case["execution_id"],log["execution_id"])
        self.assertEqual(case["retrieved_evidence"],ROWS)
        self.assertEqual(case["customer_message"],response.json()["output"])

    def test_log_failure_returns_error_and_does_not_create_case(self):
        response,calls=self.run_chat("escalate",fail="support_query_logs")
        self.assertEqual(response.status_code,503)
        self.assertEqual(sum(p.endswith("support_query_logs") for p,b in calls),1)
        self.assertFalse(any(p.endswith("support_escalations") for p,b in calls))
        self.assertNotIn("output",response.json())
        self.assertNotIn("private-",response.text)

    def test_case_failure_after_log_success_is_error_without_retry(self):
        response,calls=self.run_chat("escalate",fail="support_escalations")
        self.assertEqual(response.status_code,503)
        self.assertEqual(sum(p.endswith("support_query_logs") for p,b in calls),1)
        self.assertEqual(sum(p.endswith("support_escalations") for p,b in calls),1)
        self.assertEqual(response.json()["error"],"persistence_error")
        self.assertNotIn("private-",response.text)
        UUID(response.json()["request_id"])

    def test_embedding_failure_is_logged_and_escalated(self):
        response,calls=self.run_chat(upstream=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["decision"],"escalate")
        self.assertEqual(calls[-2][1]["reason"],"Query embedding request failed")
        self.assertTrue(calls[-2][1]["validation_error"])
        self.assertEqual(calls[-2][1]["retrieved_evidence"],[])
        self.assertNotIn("private-",response.text)

    @patch.dict("os.environ",ENV,clear=True)
    def test_insert_timeout_and_unconfirmed_response_are_errors(self):
        from backend.integrations.persistence import insert_row
        from backend.errors import PersistenceError
        for mode in ("timeout", "empty", "invalid_json"):
            calls=[]
            def handler(request):
                calls.append(request)
                if mode == "timeout": raise httpx.ReadTimeout("private-supabase",request=request)
                if mode == "empty": return httpx.Response(201,json=[])
                return httpx.Response(201,text="private-supabase")
            with self.subTest(mode=mode), httpx.Client(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(PersistenceError) as caught:
                    insert_row("support_query_logs",{},client=client)
                self.assertNotIn("private-",str(caught.exception))
                self.assertEqual(len(calls),1)

    @patch.dict("os.environ",ENV,clear=True)
    def test_health_configuration_check_does_not_make_network_calls(self):
        with patch("httpx.Client.post",side_effect=AssertionError("No network")):
            with TestClient(app) as client:
                self.assertEqual(client.get("/health").json(),{"status":"ok","rag_available":True})
