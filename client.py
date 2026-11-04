"""HTTP client for the published CloudDesk billing-support workflow."""

from typing import Optional, Tuple

import requests


CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 90


class ChatClientError(Exception):
    """A user-displayable error communicating with the n8n workflow."""


def send_message(
    chat_url: str,
    session_id: str,
    chat_input: str,
    basic_auth: Optional[Tuple[str, str]] = None,
) -> str:
    """Send one question and return the workflow's output string.

    Requests are deliberately not retried because a workflow call may create a
    human-review case.
    """
    if not chat_url:
        raise ChatClientError(
            "The chat endpoint is not configured. Set N8N_CHAT_URL in .env."
        )

    payload = {
        "action": "sendMessage",
        "sessionId": session_id,
        "chatInput": chat_input,
    }

    try:
        response = requests.post(
            chat_url,
            json=payload,
            auth=basic_auth,
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            allow_redirects=False,
        )
    except requests.exceptions.Timeout as exc:
        raise ChatClientError(
            "The request timed out while contacting the billing-support service. "
            "No response was received; please try again later."
        ) from exc
    except requests.exceptions.ConnectionError as exc:
        raise ChatClientError(
            "Could not connect to the billing-support service. Check the endpoint "
            "and your network connection, then try again."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise ChatClientError(
            "The billing-support request failed before a response was received."
        ) from exc

    if response.status_code in (401, 403):
        raise ChatClientError(
            "Authentication with the billing-support service failed. Check "
            "N8N_BASIC_USER and N8N_BASIC_PASSWORD."
        )
    if not 200 <= response.status_code < 300:
        raise ChatClientError(
            "The billing-support service returned an HTTP "
            f"{response.status_code} error."
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise ChatClientError(
            "The billing-support service returned an unexpected response."
        ) from exc

    if isinstance(data, list) and len(data) == 1:
        data = data[0]

    if isinstance(data, dict) and data.get("executionStarted") is True:
        raise ChatClientError(
            "The billing-support service acknowledged workflow execution but "
            "did not return an answer. This client requires a completed JSON "
            "response with a non-empty output string. In n8n, configure the "
            "Chat Trigger for Embedded Chat and When Last Node Finishes, "
            "ensure the final node returns output, then publish the workflow."
        )

    if (
        not isinstance(data, dict)
        or not isinstance(data.get("output"), str)
        or not data["output"].strip()
    ):
        raise ChatClientError(
            "The billing-support service returned an unexpected response. "
            "Expected a non-empty output string."
        )

    return data["output"]
