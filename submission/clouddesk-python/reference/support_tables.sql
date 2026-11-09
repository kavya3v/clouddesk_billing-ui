-- Supplied by the project owner. Reference only; never executed by the backend.
create table public.support_query_logs (
  id bigint generated always as identity not null,
  execution_id text not null,
  question text not null,
  decision text not null,
  answer text not null,
  reason text not null,
  sources jsonb not null default '[]'::jsonb,
  retrieved_evidence jsonb not null default '[]'::jsonb,
  validation_error text null,
  test_set text not null default 'development'::text,
  test_case_id text null,
  expected_decision text null,
  answer_correct boolean null,
  resolved_first_contact boolean null,
  created_at timestamp with time zone not null default now(),
  constraint support_query_logs_pkey primary key (id),
  constraint support_query_logs_decision_check check (decision = any (array['answer'::text, 'escalate'::text])),
  constraint support_query_logs_expected_decision_check check (expected_decision = any (array['answer'::text, 'escalate'::text]))
) TABLESPACE pg_default;

create table public.support_escalations (
  id bigint generated always as identity not null,
  execution_id text not null,
  question text not null,
  reason text not null,
  customer_message text not null,
  retrieved_evidence jsonb not null default '[]'::jsonb,
  status text not null default 'open'::text,
  created_at timestamp with time zone not null default now(),
  constraint support_escalations_pkey primary key (id),
  constraint support_escalations_status_check check (status = any (array['open'::text, 'in_review'::text, 'resolved'::text]))
) TABLESPACE pg_default;
