# CloudDesk Billing Support

A local Streamlit chat interface for the already-published CloudDesk billing
support workflow in n8n Cloud. The Python server sends each question directly to
the configured endpoint; this app does not implement retrieval, embeddings,
LLM calls, or escalation logic.

See the [application flow guide](docs/application-flow.md) for a diagram,
the request/response contract, and an explanation of each step.

## Requirements

- Python 3.10 or newer
- Streamlit 1.66 or newer (installed by `requirements.txt`)
- The published n8n chat workflow and its exact chat endpoint URL

## Windows PowerShell setup

From this directory:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `N8N_CHAT_URL` to the exact endpoint URL shown for the
published n8n workflow. If the endpoint uses HTTP Basic Auth, set both
`N8N_BASIC_USER` and `N8N_BASIC_PASSWORD`; otherwise leave both empty. These
values are read by Python on the server and are never placed in browser code.

Run the app on the local machine only:

```powershell
streamlit run app.py --server.address 127.0.0.1
```

Open the local URL printed by Streamlit (normally `http://127.0.0.1:8501`).

The billing chat uses a light navy-and-teal theme, local invoice artwork, and
invoice/payment/subscription starter questions. Both starter questions and typed
questions use the same billing client. Styling lives in `.streamlit/config.toml`
and `assets/chat.css`; the illustration is `assets/billing.svg`. Restart Streamlit
after updating dependencies or creating the theme configuration, then refresh
the browser.

## n8n workflow requirements

Configure the published workflow as follows:

- Customer Chat mode: **Embedded Chat**
- Response mode: **When Last Node Finishes**
- The chat branch ends with **Format UI Response**
- That node returns a String field named `output`, using:
  `{{ $json.answer ?? $json.customer_message }}`
- The workflow is published

### Execution acknowledgement instead of an answer

The live endpoint was observed returning HTTP 200 with
`Content-Type: application/json; charset=utf-8` and this structure (token redacted):

```json
{"executionStarted": true, "executionId": "142", "resumeToken": "[redacted]"}
```

This acknowledges execution; it contains no answer to extract. n8n uses this
response for its response-node chat flow, while this client expects the finished
answer in the POST response. See the
[n8n webhook implementation](https://github.com/n8n-io/n8n/blob/master/packages/cli/src/webhooks/webhook-helpers.ts).

For this synchronous client, set the Chat Trigger to **Embedded Chat** and
**When Last Node Finishes**, and ensure every answering branch ends with a
non-empty String field named `output` as described above. If the workflow relies
on Chat response nodes, adapt those branches to return the final output rather
than waiting for another chat message. Publish the changes and verify the
production Chat URL matches `N8N_CHAT_URL`. A successful response must contain
`{"output": "the actual answer"}` (or a single-item array of that object).

The client reports this mismatch explicitly; it does not invent an answer,
retry the workflow, or treat execution acknowledgement as completion. Raw-body
diagnostic prints were removed after diagnosis because the response includes
a resume token. Restart Streamlit after changing the imported client module.

The client sends one POST to the exact configured endpoint for each submitted
question, with `action`, a conversation UUID in `sessionId`, and the user text
in `chatInput`. It uses a 10-second connect timeout and a 90-second read
timeout, and does not retry. A failed request is not reported as a created
review case.

The displayed transcript is for the user's convenience only: the backend
currently answers each question independently. Answers are displayed as
returned, including source citation IDs such as `[faq-invoices-001]`. Some
account-specific requests may require human review. Users are reminded not to
enter card numbers or passwords.

## Tests

Tests use mocked HTTP responses and do not call the live workflow:

```powershell
python -m unittest discover -s tests -v
```
