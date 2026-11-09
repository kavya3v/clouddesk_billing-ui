"""Python-only routing for the assignment submission."""
import os
import python_client
from client import ChatClientError

def send_chat_message(session_id: str, chat_input: str) -> str:
    if os.getenv("CHAT_BACKEND", "python").strip().lower() != "python":
        raise ChatClientError("This submission requires CHAT_BACKEND=python.")
    return python_client.send_message(chat_url=os.getenv("PYTHON_CHAT_URL", "http://127.0.0.1:8000/chat").strip(),
                                      session_id=session_id, chat_input=chat_input)
