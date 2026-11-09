from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from client import ChatClientError


APP = str(Path(__file__).resolve().parents[1] / "app.py")


class BillingChatTests(unittest.TestCase):
    def setUp(self):
        # Never let a developer's local backend choice or .env leak into these tests.
        self.env = patch.dict("os.environ", {"CHAT_BACKEND":"n8n", "N8N_BASIC_USER":"", "N8N_BASIC_PASSWORD":""})
        self.env.start()
        self.addCleanup(self.env.stop)

    @patch("client.send_message", return_value="Download from Billing. [faq-invoices-001]")
    def test_starter_submits_question_and_reset_clears_history(self, send):
        app = AppTest.from_file(APP, default_timeout=15).run()
        self.assertFalse(app.exception)
        old_session = app.session_state["conversation_id"]
        app.button(key="starter_invoices").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(send.call_args.kwargs["chat_input"], "Where can I download my invoices?")
        self.assertEqual(len(app.chat_message), 2)
        self.assertIn("[faq-invoices-001]", app.session_state["messages"][1]["content"])
        app.run()
        send.assert_called_once()
        app.button(key="new_conversation").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["messages"], [])
        self.assertNotEqual(app.session_state["conversation_id"], old_session)

    @patch("client.send_message", return_value="Your billing reply")
    def test_typed_question_uses_existing_client(self, send):
        app = AppTest.from_file(APP, default_timeout=15).run()
        app.chat_input[0].set_value("Explain my bill").run()
        self.assertFalse(app.exception)
        self.assertEqual(send.call_args.kwargs["chat_input"], "Explain my bill")
        self.assertEqual(app.session_state["messages"][-1]["content"], "Your billing reply")

    @patch("client.send_message", side_effect=ChatClientError("Service unavailable"))
    def test_service_error_shows_one_assistant_message(self, send):
        app = AppTest.from_file(APP, default_timeout=15).run()
        app.chat_input[0].set_value("Explain my bill").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.chat_message), 2)
        self.assertEqual(app.error[0].value, "Service unavailable")
        send.assert_called_once()

    @patch.dict("os.environ", {"CHAT_BACKEND":"python", "PYTHON_CHAT_URL":"http://localhost:8000/chat", "N8N_BASIC_USER":"unused"})
    @patch("client.send_message")
    @patch("python_client.send_message",return_value="Python reply [faq-1]")
    def test_python_selection_preserves_citations(self,python,n8n):
        app=AppTest.from_file(APP).run()
        app.button(key="starter_invoices").click().run()
        self.assertFalse(app.exception)
        python.assert_called_once()
        n8n.assert_not_called()
        self.assertEqual(python.call_args.kwargs["chat_url"],"http://localhost:8000/chat")
        self.assertEqual(app.session_state["messages"][-1]["content"],"Python reply [faq-1]")

    @patch.dict("os.environ", {"CHAT_BACKEND":"python"})
    @patch("client.send_message")
    @patch("python_client.send_message",side_effect=ChatClientError("Python timed out; no retry"))
    def test_python_error_no_fallback_or_rerun_retry(self,python,n8n):
        app=AppTest.from_file(APP).run()
        app.chat_input[0].set_value("Question").run()
        self.assertEqual(app.error[0].value,"Python timed out; no retry")
        self.assertEqual(len(app.session_state["messages"]),1)
        app.run()
        python.assert_called_once()
        n8n.assert_not_called()
