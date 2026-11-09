# CloudDesk Billing Support

A local Streamlit chat interface for the already-published CloudDesk billing
support workflow in n8n Cloud. By default the Streamlit server sends each question to the configured n8n
endpoint. An optional environment switch can route to the separate Python backend;
the UI itself does not implement the RAG pipeline.

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

## Python backend migration

Streamlit uses `client.py` to call n8n by default; Python routing is opt-in. The independent Python backend is
now connected end-to-end, with mocked verification only; no live calls or database
changes were made during migration. The n8n workflow, search SQL, and owner-supplied
table definitions in `reference/` are source references, not migration scripts.

| Files | Responsibility |
| --- | --- |
| `backend/main.py`, `contracts.py` | FastAPI endpoints, typed request/response contracts |
| `backend/config.py`, `errors.py` | Server configuration and sanitized errors |
| `backend/service.py` | Embedding, retrieval, filtering, generation, validation, writes, reply |
| `backend/integrations/embeddings.py` | Workflow-pinned query embedding model and prefix; 768-dimensional vector validation |
| `backend/integrations/retrieval.py`, `evidence.py` | Existing RPC and eligible evidence filtering at similarity >= 0.65 |
| `backend/integrations/generation.py`, `validation.py` | Exact workflow prompt/settings and structured decision checks |
| `backend/integrations/persistence.py` | Insert query logs and open escalation cases |
| `backend/integrations/transport.py` | Bounded HTTP requests without retries or redirects |
| `tests/test_backend.py`, `test_retrieval.py`, `test_generation.py`, `test_persistence.py` | Mocked API, retrieval, generation, and persistence checks |

### Windows PowerShell setup and run

The inspected interpreter is Python 3.15.2. FastAPI 0.162.0, Pydantic 2.14.2,
Uvicorn 0.54.0, and HTTPX 0.28.1 were tested on that interpreter. Dependencies
remain separate from the Streamlit `requirements.txt`.

```powershell
python --version
python -m venv .venv-backend
.\.venv-backend\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv-backend\Scripts\python.exe -m pip check

# Set actual values only in the server terminal or secret manager.
$env:FIREWORKS_API_KEY = "your-fireworks-key"
$env:SUPABASE_URL = "https://your-project.supabase.co"
$env:SUPABASE_SERVICE_ROLE_KEY = "your-server-only-key"
.\.venv-backend\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

For local development, `python -m backend` loads the project-root `.env` with
explicit override of inherited settings, then starts on 127.0.0.1:8000. Use
`python -m backend --env-file PATH` to select a different file. Restart after
saving credentials. Direct Uvicorn startup continues to use environment variables
and does not automatically load `.env`. Importing the backend does
not load credentials or perform requests. Keep keys server-side. Model names in
`.env.example` are documentary: code uses the exact reference models, not overrides.

`GET /health` reports `status: ok` and whether required configuration is present
as `rag_available`. This is not a live upstream or database permission check.
`POST /chat` accepts non-empty `sessionId` and `chatInput` strings. It returns
`output`, `decision` (`answer` or `escalate`), `sources`, and a server-generated
UUID `request_id` only after required writes are confirmed. Missing configuration
returns HTTP 503 `configuration_error`; unconfirmed inserts return HTTP 503
`persistence_error`, with a generic message and the request ID. Neither error
returns an answer or claims a case was saved. Invalid requests return HTTP 422.
Local schemas are available at `/docs` and `/openapi.json`.

Calling `/chat` with real credentials now performs live inference and inserts.
It remains separate from Streamlit; do not treat local mocked testing as production
verification. The local backend has no end-user authentication and binds to loopback
in the run command above.

### Preserved workflow behavior

- Embeddings: `nomic-ai/nomic-embed-text-v1.5`, exact `search_query: ` prefix,
  no dimensions override. The workflow measures vector length; Python enforces the
  model's default 768 dimensions, finite numeric entries, and a non-zero vector.
- Retrieval: existing `hybrid_search_support` with `query_text`, JSON-string
  `query_embedding`, and `match_count: 5`. No SQL/ranking/schema changes.
- Generation: exact reference prompt and `accounts/fireworks/models/deepseek-v4p1-flash`,
  `max_tokens: 700`, `stream: false`. Only eligible evidence reaches the model,
  with the same five-field projection as n8n. Empty eligible evidence skips generation.
- Validation: completed JSON response, required fields, allowed decisions, retrieved
  source IDs, bracketed citations for every listed source, finite cited similarity
  >= 0.65. Extra model fields are ignored, as in n8n. These checks do not establish
  semantic entailment or independently detect all prohibited-action claims; the
  exact prompt forbids claiming refunds, account actions, or completed tickets.
- Embedding, retrieval, generation, and validation failures produce safe escalation
  outcomes with internal reasons and sanitized diagnostics, followed by required writes.

### Persistence mapping and limitations

`reference/support_tables.sql` records the table definitions supplied by the owner.
Both `execution_id` columns are required text. Both inserts store `python:<request_id>`
to correlate them without presenting Python UUIDs as n8n execution IDs. There is no
invented request-ID column. Normal chat uses `test_set: production`, actual nulls for
`test_case_id` and `expected_decision`, and leaves evaluation columns at their defaults.
`sessionId` is accepted but not stored because neither table establishes a session
column; it does not introduce conversation memory.

Query logs include question, decision, answer, reason, sources, all raw retrieved
rows (including hybrid_score and ineligible results), and validation_error. Eligible
evidence stays separate as generation context. Escalations store question, reason,
customer_message, the same all-retrieved rows, and explicit `status: open`. This
retains more audit evidence than n8n's filtered-evidence logging. The existing JSONB
columns hold arrays; no additional columns or database changes are needed.

Inserts request returned row representations and confirm a row ID. The log is
inserted first, then an escalation case when required. HTTP 200 is returned only
after both required confirmations. Inserts have no automatic retries or upserts.
The shared transport uses 10-second connect and 90-second other-operation timeouts.

The two writes are **not atomic**. A case-creation failure may leave the log saved;
a timeout or malformed acknowledgement may leave commit state unknown. The supplied
schema has no uniqueness constraint on execution_id, so user retries can create
additional records. The backend reports an error instead of promising rollback or
retry safety. Database grants, RLS policies, and triggers were not supplied or tested
live. Credentials and raw upstream error bodies are not logged or returned.

### Tests

```powershell
# Backend-only tests
.\.venv-backend\Scripts\python.exe -m unittest discover -s tests -p "test_backend.py" -v
# Full suite, including unchanged Streamlit tests
.\.venv-backend\Scripts\python.exe -m pip install -r requirements.txt
.\.venv-backend\Scripts\python.exe -m unittest discover -s tests -v
```

All external calls in tests use mocks. Starlette currently emits an HTTPX test-client
deprecation warning; the tests still execute. No live API verification is implied.


## Select the chat backend locally

`CHAT_BACKEND` defaults to `n8n` when absent. `CHAT_BACKEND=python` uses
`PYTHON_CHAT_URL`, which must be the full FastAPI `/chat` URL, not just its origin.
Unknown backend names produce a configuration error. Python mode ignores n8n
credentials, including partially configured Basic Auth. Neither client retries,
and Python errors never trigger n8n fallback. Output is displayed unchanged,
including source citations. Python errors omit raw upstream bodies and warn that
a log or review case may already have been saved. Do not blindly resubmit after
a timeout; inspect the database first. Python's client timeouts are 10 seconds
for connection and 300 seconds for reads; these are not a cancellation guarantee.

Use two PowerShell terminals. The commands below use this project's existing
`.venv`; install both UI and backend dependencies once if needed.

**Terminal 1: start FastAPI with the saved local credentials**

```powershell
Set-Location 'C:\Users\kavya\Desktop\RAG_first\clouddesk_billing-ui'
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r backend/requirements.txt
.\.venv\Scripts\python.exe -m backend
```

The launcher explicitly loads the project-root `.env`, overriding inherited
settings for its process. Keep Fireworks/Supabase credentials there, server-side.
Stop an existing server on port 8000 with Ctrl+C before starting another.

**Terminal 2: start Streamlit in Python mode**

```powershell
Set-Location 'C:\Users\kavya\Desktop\RAG_first\clouddesk_billing-ui'
$env:CHAT_BACKEND = 'python'
$env:PYTHON_CHAT_URL = 'http://127.0.0.1:8000/chat'
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Open `http://127.0.0.1:8501`. Streamlit loads `.env` without overriding existing
process variables, so the terminal's selection takes precedence. No credentials
are sent to the browser. Submitting a question in Python mode makes real model
calls and database inserts when the backend is configured.

**Switch back to n8n**: press Ctrl+C in Terminal 2, then run:

```powershell
$env:CHAT_BACKEND = 'n8n'
Remove-Item Env:PYTHON_CHAT_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Keep the existing `N8N_CHAT_URL` and optional Basic Auth settings in `.env`.
Terminal 1 can be stopped separately with Ctrl+C. To keep n8n as the persistent
local default, leave `CHAT_BACKEND` unset or set it to `n8n` in `.env`.
The hosted app and deployment configuration have not been changed. An unset
hosted `CHAT_BACKEND` continues using n8n; local loopback URLs are for local use.


## Submission and repository artifacts

The Python-only assignment package is in `submission/clouddesk-python/` with its
ZIP alongside it. Follow that package's README for a demo without n8n configuration.
The main repository retains the n8n default for the existing hosted UI.

Raw `reference/n8nworkflow.json` is kept local and excluded from Git. The sanitized
`reference/generation_contract.json` fixture preserves the verified exact model,
system prompt, and generation settings for clone-safe regression tests. SQL
reference files and historical evaluation CSVs are included without credentials.
