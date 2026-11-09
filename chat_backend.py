"""Environment-based routing; defaults to the existing n8n client."""
import os
import client
import python_client
from client import ChatClientError


def send_chat_message(session_id: str, chat_input: str) -> str:
    backend = os.getenv("CHAT_BACKEND", "n8n").strip().lower()
    if backend == "python":
        return python_client.send_message(chat_url=os.getenv("PYTHON_CHAT_URL", "").strip(),
                                          session_id=session_id, chat_input=chat_input)
    if backend != "n8n":
        raise ChatClientError("CHAT_BACKEND must be n8n or python.")
    user = os.getenv("N8N_BASIC_USER")
    password = os.getenv("N8N_BASIC_PASSWORD")
    if bool(user) != bool(password):
        raise ChatClientError("Basic Auth is only partially configured. Set both N8N_BASIC_USER and N8N_BASIC_PASSWORD, or leave both empty.")
    return client.send_message(chat_url=os.getenv("N8N_CHAT_URL", "").strip(),
                               session_id=session_id, chat_input=chat_input,
                               basic_auth=(user, password) if user else None)
