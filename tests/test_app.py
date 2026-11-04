from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from client import ChatClientError


APP = str(Path(__file__).resolve().parents[1] / "app.py")


class BillingChatTests(unittest.TestCase):
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
