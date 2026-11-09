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


    @patch.dict("os.environ", {},clear=True)
    @patch("python_client.send_message",return_value="Python reply")
    def test_default_is_python_without_legacy_configuration(self,send):
        from chat_backend import send_chat_message
        self.assertEqual(send_chat_message("s","Question"),"Python reply")
        self.assertEqual(send.call_args.kwargs["chat_url"],"http://127.0.0.1:8000/chat")
