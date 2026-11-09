import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app, get_chat_service
from backend.contracts import ChatResponse


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()

    @patch.dict("os.environ", {}, clear=True)
    def test_health_reports_rag_unavailable(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "rag_available": False})

    @patch.dict("os.environ", {}, clear=True)
    def test_unconfigured_chat_is_503_with_request_id(self):
        response = self.client.post("/chat", json={"sessionId": "s", "chatInput": "Help"})
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["error"], "configuration_error")
        UUID(body["request_id"])
        self.assertNotIn("output", body)
        self.assertNotIn("decision", body)

    def test_invalid_requests_never_call_service(self):
        service = Mock()
        app.dependency_overrides[get_chat_service] = lambda: service
        for body in ({}, {"sessionId": "s"}, {"sessionId": "", "chatInput": "x"},
                     {"sessionId": "s", "chatInput": "  "},
                     {"sessionId": 3, "chatInput": "x"},
                     {"sessionId": "s", "chatInput": "x", "extra": True}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/chat", json=body).status_code, 422)
        service.chat.assert_not_called()

    def test_mocked_response_contract_for_both_decisions(self):
        service = Mock()
        app.dependency_overrides[get_chat_service] = lambda: service
        for decision in ("answer", "escalate"):
            service.chat.side_effect = lambda request, request_id: ChatResponse(
                output="Mocked test reply", decision=decision,
                sources=["test-source"] if decision == "answer" else [], request_id=request_id)
            response = self.client.post("/chat", json={"sessionId": "s", "chatInput": "Help"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(set(response.json()), {"output", "decision", "sources", "request_id"})
            self.assertEqual(response.json()["decision"], decision)
            UUID(response.json()["request_id"])
        self.assertNotEqual(service.chat.call_args_list[0].args[1], service.chat.call_args_list[1].args[1])

    def test_response_rejects_invalid_decision_or_fields(self):
        for changes in ({"decision": "success"}, {"output": " "}, {"sources": "source"}):
            data = dict(output="Reply", decision="escalate", sources=[],
                        request_id="00000000-0000-0000-0000-000000000001")
            data.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ChatResponse(**data)

