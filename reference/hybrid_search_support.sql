-- Reference: existing Supabase hybrid_search_support function.
-- Pending the actual definition; this file intentionally contains no executable SQL.
-- Paste the complete CREATE OR REPLACE FUNCTION definition from Supabase here,
-- including its schema, argument types/defaults, return columns, and function body.
-- Include relevant referenced table/index definitions separately if needed.
-- Do not include credentials or service-role keys.
-- The Python migration must preserve the supplied function's behavior rather
-- than infer its ranking, filtering, or similarity calculations.
CREATE OR REPLACE FUNCTION public.hybrid_search_support(query_text text, query_embedding vector, match_count integer DEFAULT 5)
 RETURNS TABLE(chunk_key text, title text, content text, source_type text, semantic_similarity double precision, hybrid_score double precision)
 LANGUAGE sql
 STABLE
 SET search_path TO 'public', 'extensions'
AS $function$
  with keyword_results as (
    select
      s.id,
      row_number() over (
        order by ts_rank_cd(
          s.search_text,
          websearch_to_tsquery('english', query_text)
        ) desc, s.id
      ) as rank
    from public.support_chunks s
    where s.search_text @@
      websearch_to_tsquery('english', query_text)
    order by rank
    limit 20
  ),
  semantic_results as (
    select
      s.id,
      row_number() over (
        order by s.embedding <=> query_embedding, s.id
      ) as rank
    from public.support_chunks s
    where s.embedding_model = 'nomic-ai/nomic-embed-text-v1.5'
    order by s.embedding <=> query_embedding, s.id
    limit 20
  ),
  fused as (
    select
      coalesce(k.id, v.id) as id,
      coalesce(1.0 / (60 + k.rank), 0.0) +
      coalesce(1.0 / (60 + v.rank), 0.0) as score
    from keyword_results k
    full outer join semantic_results v on k.id = v.id
  )
  select
    s.chunk_key,
    s.title,
    s.content,
    s.source_type,
    (1 - (s.embedding <=> query_embedding))::double precision,
    f.score::double precision
  from fused f
  join public.support_chunks s on s.id = f.id
  order by f.score desc, s.id
  limit greatest(1, least(coalesce(match_count, 5), 20));
$function$

