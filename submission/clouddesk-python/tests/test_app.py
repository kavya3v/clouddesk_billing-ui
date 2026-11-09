from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from client import ChatClientError
APP=str(Path(__file__).resolve().parents[1]/"app.py")

class PythonUiTests(unittest.TestCase):
    def setUp(self):
        env=patch.dict("os.environ",{"CHAT_BACKEND":"python","PYTHON_CHAT_URL":"http://127.0.0.1:8000/chat"})
        env.start(); self.addCleanup(env.stop)

    @patch("python_client.send_message",return_value="Billing reply [faq-1]")
    def test_starter_citations_and_reset(self,send):
        app=AppTest.from_file(APP).run()
        old=app.session_state["conversation_id"]
        app.button(key="starter_invoices").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(send.call_args.kwargs["chat_input"],"Where can I download my invoices?")
        self.assertEqual(app.session_state["messages"][-1]["content"],"Billing reply [faq-1]")
        app.run(); send.assert_called_once()
        app.button(key="new_conversation").click().run()
        self.assertEqual(app.session_state["messages"],[])
        self.assertNotEqual(old,app.session_state["conversation_id"])

    @patch("python_client.send_message",return_value="Typed reply")
    def test_typed_question(self,send):
        app=AppTest.from_file(APP).run()
        app.chat_input[0].set_value("Explain my bill").run()
        self.assertFalse(app.exception)
        self.assertEqual(send.call_args.kwargs["chat_input"],"Explain my bill")
        self.assertEqual(app.session_state["messages"][-1]["content"],"Typed reply")

    @patch("python_client.send_message",side_effect=ChatClientError("Service timed out; no retry"))
    def test_failure_does_not_resubmit(self,send):
        app=AppTest.from_file(APP).run()
        app.chat_input[0].set_value("Question").run()
        self.assertEqual(app.error[0].value,"Service timed out; no retry")
        self.assertEqual(len(app.session_state["messages"]),1)
        app.run(); send.assert_called_once()
