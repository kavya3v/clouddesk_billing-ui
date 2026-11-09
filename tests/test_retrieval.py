import json
import unittest
from unittest.mock import Mock, patch
import httpx
from backend.integrations.embeddings import generate_query_embedding
from backend.integrations.retrieval import hybrid_search, retrieve_evidence
from backend.integrations.evidence import filter_evidence
from backend.errors import ConfigurationError, UpstreamError, InvalidVector

VECTOR = [0.1] * 768
ROW = dict(chunk_key="faq-1", title="Invoices", content="Billing guide", source_type="faq",
           semantic_similarity=0.65, hybrid_score=0.031)
ENV = dict(FIREWORKS_API_KEY="test-fireworks-secret", SUPABASE_URL="https://example.supabase.co",
           SUPABASE_SERVICE_ROLE_KEY="test-supabase-secret")

class RetrievalTests(unittest.TestCase):
    def client(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler))

    @patch.dict("os.environ", ENV, clear=True)
    def test_successful_embedding_and_retrieval(self):
        calls = []
        def handler(request):
            calls.append(request)
            body = json.loads(request.content)
            if len(calls) == 1:
                self.assertEqual(body, {"model": "nomic-ai/nomic-embed-text-v1.5", "input": "search_query: Invoices?"})
                return httpx.Response(200, json={"data": [{"embedding": VECTOR}]})
            self.assertEqual(request.url.path, "/rest/v1/rpc/hybrid_search_support")
            self.assertEqual(body, {"query_text": "Invoices?", "query_embedding": json.dumps(VECTOR), "match_count": 5})
            self.assertEqual(request.headers["apikey"], ENV["SUPABASE_SERVICE_ROLE_KEY"])
            return httpx.Response(200, json=[ROW])
        with self.client(handler) as client:
            rows = retrieve_evidence("Invoices?", client=client)
        self.assertEqual(rows[0].model_dump(), ROW)
        self.assertEqual(len(calls), 2)

    def test_threshold_and_invalid_scores(self):
        rows = [dict(ROW, semantic_similarity=s) for s in [0.6499, 0.65, "0.8", None, "", "bad", float("nan"), float("inf")]]
        rows += [dict(ROW, content=""), dict(ROW, chunk_key=None)]
        self.assertEqual([r.semantic_similarity for r in filter_evidence(rows)], [0.65, 0.8])

    @patch.dict("os.environ", ENV, clear=True)
    def test_empty_results(self):
        with self.client(lambda r: httpx.Response(200, json=[])) as client:
            self.assertEqual(hybrid_search("x", VECTOR, client=client), [])
        self.assertEqual(filter_evidence([]), [])
        self.assertEqual(filter_evidence([dict(ROW, semantic_similarity=0.2)]), [])

    @patch.dict("os.environ", ENV, clear=True)
    def test_invalid_vectors_before_rpc(self):
        client = Mock()
        for vector in [[], [0.1], [0.0]*768, [True]*768, ["0.1"]*768, [float("nan")]*768, [float("inf")]*768]:
            with self.subTest(vector_type=type(vector[0]) if vector else None), self.assertRaises(InvalidVector):
                hybrid_search("x", vector, client=client)
        client.post.assert_not_called()

    @patch.dict("os.environ", ENV, clear=True)
    def test_invalid_embedding_response(self):
        for body in [{}, {"data": []}, {"data": [{"embedding": [0.1]}]}]:
            with self.client(lambda r: httpx.Response(200, json=body)) as client:
                with self.assertRaises((UpstreamError, InvalidVector)):
                    generate_query_embedding("x", client=client)

    @patch.dict("os.environ", ENV, clear=True)
    def test_upstream_failures_are_sanitized(self):
        for stage in ["embedding", "retrieval"]:
            for failure in ["http", "timeout", "connection", "json"]:
                def handler(request):
                    if failure == "timeout": raise httpx.ReadTimeout("test-fireworks-secret", request=request)
                    if failure == "connection": raise httpx.ConnectError("test-supabase-secret", request=request)
                    if failure == "json": return httpx.Response(200, text="not json")
                    return httpx.Response(401, text="test-fireworks-secret")
                with self.subTest(stage=stage, failure=failure), self.client(handler) as client:
                    with self.assertRaises(UpstreamError) as caught:
                        if stage == "embedding": generate_query_embedding("x", client=client)
                        else: hybrid_search("x", VECTOR, client=client)
                    self.assertNotIn("secret", str(caught.exception))
                    self.assertEqual(caught.exception.stage, stage)

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_configuration_never_calls_upstream(self):
        client = Mock()
        for function,args in [(generate_query_embedding,("x",)),(hybrid_search,("x",VECTOR))]:
            with self.assertRaises(ConfigurationError): function(*args, client=client)
        client.post.assert_not_called()

    @patch.dict("os.environ", ENV, clear=True)
    def test_malformed_rpc_response(self):
        with self.client(lambda r: httpx.Response(200, json={"error":"bad"})) as client:
            with self.assertRaises(UpstreamError): hybrid_search("x", VECTOR, client=client)
