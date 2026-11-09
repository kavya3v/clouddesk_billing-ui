# CloudDesk Billing RAG - Python assignment submission

This submission runs a Streamlit chat UI against a FastAPI RAG backend. It does
not require an n8n account, URL, credential, or workflow import. The packaged UI
uses Python by default; the working repository's hosted n8n default was not changed.

## Verified results: separate measures

| Measure | Result | Meaning |
| --- | --- | --- |
| Routing/decision agreement | **18/20 (90%)** | Decision matches the expected answer/escalate label |
| Returned-answer support review | **8/8 (100%)** | Each factual claim/instruction in the eight returned answers was supported by its cited retrieved text |
| Answerable cases actually answered | 8/10 (80%) | Two answerable questions escalated after citation validation failed |
| Required escalations matched | 10/10 (100%) | Includes one matching escalation caused by an incomplete-response fallback |

The historical n8n execution 132 baseline was **17/20 (85%)** routing agreement.
Python's single evaluation run improved agreement by five percentage points.
This is not 90% answer accuracy: routing and factual support are separate metrics,
and the eight-answer review does not assess the unanswered cases.

Cases final-06 and final-10 failed supporting-citation validation. Case final-19
matched the required escalation through a **technical/validation fallback**
(`Response incomplete or missing`), not a valid model escalation. The CSV's
technical_fallback flag includes validation fallbacks; three cases are flagged,
including that one matching case. There were no unverified evaluation logs.
Stochastic model outputs may differ in a new run.

Artifacts:

- `evaluation/python_execution_132_comparison.csv`: all 20 Python outcomes,
  questions, expected labels, request IDs, answers, sources, and saved diagnostics.
- `evaluation/python_answer_review.csv`: eight claim-level support verdicts/notes.
- `evaluation/n8n_execution_132_baseline.csv`: historical baseline only.
- `evaluation/python_execution_132_notes.md`: evaluation method and limitations.

## Prerequisites

- Windows PowerShell and **Python 3.15.2** (the interpreter used for verification).
  Run `python --version` to confirm. Use an explicit interpreter path if necessary.
- Internet access to install dependencies and to call Fireworks and Supabase.
- A working Fireworks API key with access to both fixed models below.
- An existing, populated Supabase project with pgvector and the support objects
  below. This package does not bootstrap a new database or modify an existing one.

Required Supabase setup:

1. `public.support_chunks` must already contain the billing FAQ, policy, manual,
   and ticket-example knowledge with document embeddings from
   `nomic-ai/nomic-embed-text-v1.5` (768 dimensions). It needs the `id`, `chunk_key`,
   `title`, `content`, `source_type`, `embedding`, `embedding_model`, and searchable
   `search_text` fields used by the supplied RPC. The search text and embeddings
   must already be populated; this submission implements query-time RAG only.
2. `public.hybrid_search_support(query_text text, query_embedding vector,
   match_count integer default 5)` must already exist and be exposed through
   Supabase REST. Its exact reference definition is in
   `reference/hybrid_search_support.sql`. It returns chunk_key, title, content,
   source_type, semantic_similarity, and hybrid_score. Ranking remains in Supabase.
3. `public.support_query_logs` and `public.support_escalations` must already exist
   with the owner-supplied definitions in `reference/support_tables.sql`.
   The backend needs permission to insert rows and read returned row representations.
   It also needs RPC execution and underlying knowledge-read access. Verify relevant
   grants, RLS, and triggers with the project owner; these policies are not supplied.
4. Use the server-side Supabase service-role key. Never place it in browser code.
   Reference SQL files document prerequisites; **do not execute them against an
   existing project as part of startup**. No schema migration is included.

The complete knowledge dataset and its schema bootstrap are not bundled. A fresh
Supabase project is therefore insufficient without the prerequisite setup. The
historical evaluation CSVs are evidence of prior results, not a replacement for
an operational knowledge database.

## Setup - exact Windows PowerShell commands

Extract `clouddesk-python-submission.zip` into a directory of your choice. Open
PowerShell in its extracted `clouddesk-python` directory (the one containing this
README and app.py). Both terminals below must use that same directory.

```powershell
# Confirm that this is the extracted project root.
Get-Item .\app.py, .\backend\main.py, .\requirements.txt
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
Copy-Item .env.example .env
notepad .env
```

Only copy the template during initial setup; do not overwrite a configured .env.
Fill these three values in `.env`:

```dotenv
FIREWORKS_API_KEY=your-real-fireworks-key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-real-server-only-key
```

Keep these UI settings from the template:

```dotenv
CHAT_BACKEND=python
PYTHON_CHAT_URL=http://127.0.0.1:8000/chat
```

The key must be the raw key, without a Bearer prefix. Do not commit or submit
`.env`. Required secrets are server-side; Streamlit sends only sessionId/chatInput
to FastAPI. The backend adds authorization for its upstream requests.

**Terminal 1 - start FastAPI:**

```powershell
.\.venv\Scripts\python.exe -m backend
```

The local launcher explicitly reads `.env` from this extracted project root and
overrides stale inherited settings in its own process. Restart it after editing
credentials. It listens on `127.0.0.1:8000`; stop any previous server occupying
that port before launching. API schemas are at `http://127.0.0.1:8000/docs`.

**Terminal 2 - preflight and start Streamlit:**

```powershell
# Open this terminal in the same extracted clouddesk-python directory.
$env:CHAT_BACKEND = 'python'
$env:PYTHON_CHAT_URL = 'http://127.0.0.1:8000/chat'
Invoke-RestMethod http://127.0.0.1:8000/health
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

Open `http://127.0.0.1:8501`. Health should show status ok and rag_available true;
this verifies local configuration presence, not live upstream connectivity or
permissions. Streamlit reads only this project's `.env` and preserves explicit
terminal settings. No n8n variables are needed. Stop each service with Ctrl+C.
This is a local demo configuration, with no end-user API authentication; no hosted
deployment is performed or changed.

## Two-question live demo

These are manual demo steps, not automatically executed during startup or tests.
Each submission invokes real models and inserts audit records. Submit once; do
not retry after a timeout before inspecting the database.

1. Click **New conversation**. Ask exactly:
   `Where can I download my invoices?`
   Expected: a supported answer pointing to Settings > Billing > Invoices with
   source citations, an answer log, and no escalation case.
2. Ask exactly:
   `My card was charged twice. Please refund the duplicate charge.`
   Expected: a safe human-review escalation, a query log, and an open review case.
   The system must not claim that it refunded or changed the account.

The UI shows output and preserves citations. API replies contain output, decision
(answer/escalate only), sources, and a server-generated request_id. For correlation,
look up `execution_id = python:<request_id>` in the log/case tables. The UI does not
currently show request_id; use the API response when doing a separate API demo.
Do not also submit through the API unless you intend an additional real request.

## Pipeline and failure behavior

FastAPI validates input, generates the query embedding with the exact
`search_query: ` prefix, invokes the existing hybrid RPC with match_count 5, filters
eligible evidence at **semantic_similarity >= 0.65**, generates a decision, validates
it, logs the query, and creates an open case for escalations. Only then does it
return a successful reply. All retrieved evidence is retained in the log separately
from eligible generation context.

Embedding model: `nomic-ai/nomic-embed-text-v1.5`, full default 768 dimensions.
Generation model: `accounts/fireworks/models/deepseek-v4p1-flash`, exact verified
system prompt, max_tokens 700, stream false. `reference/generation_contract.json`
is a data-only test fixture containing that prompt and settings, not a workflow
export. No prompt or threshold tuning was performed for this package.

Empty evidence skips generation and escalates safely. Malformed/incomplete or
unsupported-citation responses become safe fallback results with internal
validation_error. Source IDs/citation syntax are checked, but those checks alone
do not prove factual support; that is why the separate eight-answer review exists.

The backend performs no automatic insert retries. Python UI failures/timeouts do
not trigger fallback to any other backend. HTTP 503 persistence errors include a
request_id without credentials/raw provider errors. Two inserts are not atomic:
a log may exist if case creation fails, and a timeout may leave commit state unknown.
The schema has no unique correlation constraint, so manual retries may create
additional records. Normal chat test_case_id/expected_decision are actual nulls.
`sessionId` does not add conversational memory and is not stored in a nonexistent
session column. No refund or account operation is implemented.

## Run tests without live calls

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Tests use mocked transports/services; they do not use real upstream credentials,
submit chat requests to a running backend, or insert database rows. UI tests exercise
Python routing, citations, typed input, starter/reset behavior, and no resubmission
on rerun. Legacy transport tests are excluded from this Python-only package; the
original repository suite was separately run before packaging. A known HTTPX
TestClient deprecation warning and Streamlit bare-context warnings may appear.

## Package contents

`app.py`, `chat_backend.py`, `python_client.py`, `client.py` (shared error type only),
`backend/`, `assets/`, `.streamlit/config.toml`, `requirements.txt`, `tests/`,
`.env.example`, data-only `reference/` files, and `evaluation/` CSVs/notes.
No actual keys, `.env`, virtual environment, logs, n8n workflow export, or deployment
configuration are included.
