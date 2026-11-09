# Python comparison with n8n execution 132

Source: `reference/results_execution_132.csv`, verified as 20 unique cases,
final-01 through final-20, all execution_id 132. Questions and expected decisions
were copied verbatim. Local /health passed before chat submissions.

Exactly 20 requests were sent, one per case, without retries. Every attempt was
journaled and flushed before sending. The runner refuses to run if either output
or attempt journal already exists. All requests returned HTTP 200; each request ID
was unique and its query log was read back using python:<request_id>. Saved
questions, decisions, and answers matched; no log verification was missing.

Decision agreement: 18/20 (90%). Answerable cases answered: 8/10 (80%).
Required escalations matched: 10/10 (100%). n8n baseline: 17/20 (85%).
Python improved by one agreement, or five percentage points, in this single run.
These are decision-agreement figures, not an independent correctness evaluation
of answer text; stochastic model output can vary between runs.

The technical_fallback CSV flag conservatively includes response-validation
fallbacks as well as upstream technical failures. Flagged cases:

- final-06: Answer lacks supporting citations (answerable case missed).
- final-10: Answer lacks supporting citations (answerable case missed).
- final-19: Response incomplete or missing (expected escalation matched, but
  achieved through fallback rather than a valid model escalation).

Thus 17 decisions matched without a flagged fallback; the reported 18/20
includes the fallback match on final-19. No unverified logs were treated as
having no validation error. CSV `validation_error` value `null` means the verified
query-log value was null; verification failures would start with UNVERIFIED.

No prompts, thresholds, database schema, or hosted deployment were changed.
The evaluation created real query logs and applicable review cases as authorized.
