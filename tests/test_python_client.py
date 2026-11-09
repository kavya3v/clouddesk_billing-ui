import unittest
from unittest.mock import patch, Mock
import requests
from client import ChatClientError
from python_client import send_message

class PythonClientTests(unittest.TestCase):
    @patch("python_client.requests.post")
    def test_output_and_exact_payload(self,post):
        post.return_value=Mock(status_code=200)
        post.return_value.json.return_value={"output":"Reply [faq-1]","decision":"answer","sources":["faq-1"],"request_id":"test"}
        self.assertEqual(send_message("http://127.0.0.1:8000/chat","s","Question"),"Reply [faq-1]")
        self.assertEqual(post.call_args.kwargs["json"],{"sessionId":"s","chatInput":"Question"})
        self.assertFalse(post.call_args.kwargs["allow_redirects"])
        post.assert_called_once()

    @patch("python_client.requests.post")
    def test_errors_are_clear_and_not_retried(self,post):
        for failure in (requests.exceptions.ReadTimeout("secret"),requests.exceptions.ConnectionError("secret"),None):
            post.reset_mock(); post.side_effect=failure
            post.return_value=Mock(status_code=503,text="secret")
            with self.assertRaises(ChatClientError) as caught: send_message("http://localhost:8000/chat","s","Question")
            self.assertNotIn("secret",str(caught.exception))
            self.assertIn("may already",str(caught.exception))
            post.assert_called_once()

    @patch("python_client.requests.post")
    def test_invalid_output_and_missing_url(self,post):
        with self.assertRaises(ChatClientError): send_message("","s","Question")
        post.assert_not_called()
        post.return_value=Mock(status_code=200)
        for data in ({},{"output":" "},["wrong"]):
            post.return_value.json.return_value=data
            with self.assertRaises(ChatClientError): send_message("http://localhost/chat","s","Question")

    @patch.dict("os.environ", {"N8N_CHAT_URL":"https://n8n.example/chat"},clear=True)
    @patch("client.send_message",return_value="n8n answer")
    @patch("python_client.send_message")
    def test_unset_switch_defaults_to_n8n(self,python,n8n):
        from chat_backend import send_chat_message
        self.assertEqual(send_chat_message("s","Question"),"n8n answer")
        n8n.assert_called_once()
        python.assert_not_called()

    @patch.dict("os.environ", {"CHAT_BACKEND":"unknown"},clear=True)
    @patch("client.send_message")
    @patch("python_client.send_message")
    def test_unknown_backend_calls_neither_service(self,python,n8n):
        from chat_backend import send_chat_message
        with self.assertRaises(ChatClientError): send_chat_message("s","Question")
        n8n.assert_not_called(); python.assert_not_called()
