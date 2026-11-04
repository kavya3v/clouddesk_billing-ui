import json
import unittest
from unittest.mock import Mock, patch

import requests

from client import (
    CONNECT_TIMEOUT_SECONDS,
    READ_TIMEOUT_SECONDS,
    ChatClientError,
    send_message,
)


class SendMessageTests(unittest.TestCase):
    @patch("client.requests.post")
    def test_observed_execution_acknowledgement_reports_response_mode_mismatch(self, post):
        response = requests.Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json; charset=utf-8"
        response._content = json.dumps({
            "executionStarted": True,
            "executionId": "142",
            "resumeToken": "test-only-token",
        }).encode()
        post.return_value = response

        with self.assertRaises(ChatClientError) as caught:
            send_message("https://n8n.example/chat", "session", "Question")

        message = str(caught.exception)
        self.assertIn("acknowledged", message)
        self.assertIn("When Last Node Finishes", message)
        self.assertIn("output", message)
        self.assertNotIn("test-only-token", message)
        post.assert_called_once()

    @patch("client.requests.post")
    def test_sends_expected_payload_and_returns_dict_output(self, post):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = {
            "output": "Your invoice is ready [faq-invoices-001]."
        }
        post.return_value = response

        answer = send_message(
            "https://n8n.example/webhook/chat",
            "conversation-uuid",
            "Where is my invoice?",
            ("support", "secret"),
        )

        self.assertEqual(answer, "Your invoice is ready [faq-invoices-001].")
        post.assert_called_once_with(
            "https://n8n.example/webhook/chat",
            json={
                "action": "sendMessage",
                "sessionId": "conversation-uuid",
                "chatInput": "Where is my invoice?",
            },
            auth=("support", "secret"),
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            allow_redirects=False,
        )

    @patch("client.requests.post")
    def test_accepts_single_item_list_response(self, post):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = [{"output": "Billing reply"}]
        post.return_value = response

        self.assertEqual(
            send_message("https://n8n.example/chat", "session", "Question"),
            "Billing reply",
        )
        post.assert_called_once()

    @patch("client.requests.post")
    def test_reports_authentication_failure(self, post):
        response = Mock()
        response.status_code = 401
        response.ok = False
        post.return_value = response

        with self.assertRaisesRegex(ChatClientError, "Authentication"):
            send_message("https://n8n.example/chat", "session", "Question")
        post.assert_called_once()

    @patch("client.requests.post")
    def test_reports_timeout_without_retry(self, post):
        post.side_effect = requests.exceptions.ReadTimeout("too slow")

        with self.assertRaisesRegex(ChatClientError, "timed out"):
            send_message("https://n8n.example/chat", "session", "Question")

        post.assert_called_once_with(
            "https://n8n.example/chat",
            json={
                "action": "sendMessage",
                "sessionId": "session",
                "chatInput": "Question",
            },
            auth=None,
            timeout=(10, 90),
            allow_redirects=False,
        )

    @patch("client.requests.post")
    def test_reports_unexpected_response(self, post):
        response = Mock()
        response.status_code = 200
        response.ok = True
        response.json.return_value = {"message": "not output"}
        post.return_value = response

        with self.assertRaisesRegex(ChatClientError, "unexpected response"):
            send_message("https://n8n.example/chat", "session", "Question")

    @patch("client.requests.post")
    def test_reports_connection_error_without_retry(self, post):
        post.side_effect = requests.exceptions.ConnectionError("offline")

        with self.assertRaisesRegex(ChatClientError, "Could not connect"):
            send_message("https://n8n.example/chat", "session", "Question")

        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
