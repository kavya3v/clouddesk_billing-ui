"""Streamlit server client for FastAPI; one request, no retry or fallback."""
import requests
from client import ChatClientError

UNCERTAIN = " A query log or review case may already have been saved. No retry or fallback was attempted."

def send_message(chat_url: str, session_id: str, chat_input: str) -> str:
    if not chat_url:
        raise ChatClientError("Set PYTHON_CHAT_URL to the Python backend's full /chat URL.")
    try:
        response = requests.post(chat_url, json={"sessionId": session_id, "chatInput": chat_input},
                                 timeout=(10, 300), allow_redirects=False)
    except requests.exceptions.Timeout:
        raise ChatClientError("The Python billing backend timed out." + UNCERTAIN) from None
    except requests.exceptions.RequestException:
        raise ChatClientError("Could not complete the Python billing backend request." + UNCERTAIN) from None
    if not 200 <= response.status_code < 300:
        raise ChatClientError(f"The Python billing backend returned HTTP {response.status_code}." + UNCERTAIN)
    try:
        data = response.json()
    except ValueError:
        raise ChatClientError("The Python billing backend returned invalid JSON." + UNCERTAIN) from None
    if not isinstance(data, dict) or not isinstance(data.get("output"), str) or not data["output"].strip():
        raise ChatClientError("The Python billing backend returned no valid output." + UNCERTAIN)
    return data["output"]
