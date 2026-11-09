import json
import unittest
from unittest.mock import patch, Mock
import httpx
from backend.contracts import Evidence
from backend.integrations.generation import generate_answer, SYSTEM_PROMPT, MODEL
from backend.integrations.validation import validate_response

E = Evidence(chunk_key="faq-1",content="Invoice guide",title="Invoices",source_type="faq",semantic_similarity=0.65,hybrid_score=0.03)
def response(**overrides):
    result = dict(decision="answer",answer="See Billing. [faq-1]",reason="Supported",sources=["faq-1"])
    result.update(overrides)
    return {"choices":[{"finish_reason":"stop","message":{"content":json.dumps(result)}}]}

class GenerationTests(unittest.TestCase):
    def test_valid_answer(self):
        result = validate_response(response(), [E], question="Invoices?")
        self.assertEqual(result.decision,"answer")
        self.assertEqual(result.reason,"Supported")
        self.assertIsNone(result.validation_error)
        self.assertEqual(result.retrieved_evidence,[E])

    def test_valid_escalation_is_normalized(self):
        result = validate_response(response(decision="escalate",answer="A draft message",sources=[]),[E])
        self.assertEqual(result.decision,"escalate")
        self.assertEqual(result.answer,"I can\u2019t resolve this from the available information. Human review is needed.")
        self.assertEqual(result.sources,[])
        self.assertIsNone(result.validation_error)

    def test_invalid_fields_and_citations(self):
        for fields in [dict(sources=["unknown"]),dict(sources=[]),dict(answer="Missing citation"),
                       dict(reason=" "),dict(decision="refund"),dict(sources="faq-1"),dict(answer=3)]:
            with self.subTest(fields=fields):
                result=validate_response(response(**fields),[E])
                self.assertEqual(result.decision,"escalate")
                self.assertTrue(result.validation_error)
                self.assertEqual(result.sources,[])

    def test_threshold_enforced_by_validator(self):
        result=validate_response(response(),[E.model_copy(update={"semantic_similarity":0.649})])
        self.assertEqual(result.validation_error,"Cited evidence is below the retrieval threshold")

    def test_malformed_and_incomplete(self):
        for body in [{},None,{"choices":[]},{"choices":[{"finish_reason":"length"}]},
                     {"choices":[{"finish_reason":"stop","message":{"content":"not json"}}]},
                     {"choices":[{"finish_reason":"stop","message":{"content":"{}"}}]}]:
            with self.subTest(body=body):
                result=validate_response(body,[E])
                self.assertEqual(result.decision,"escalate")
                self.assertTrue(result.validation_error)

    def test_empty_evidence_skips_generation(self):
        client=Mock()
        for evidence in [[],[E.model_copy(update={"semantic_similarity":0.1})]]:
            result=generate_answer("Invoices?",evidence,client=client)
            self.assertEqual(result.decision,"escalate")
            self.assertEqual(result.sources,[])
        client.post.assert_not_called()

    @patch.dict("os.environ",{"FIREWORKS_API_KEY":"test-secret"},clear=True)
    def test_exact_payload_and_only_eligible_evidence(self):
        def handler(request):
            body=json.loads(request.content)
            self.assertEqual(body["model"],MODEL)
            self.assertEqual(body["messages"][0],{"role":"system","content":SYSTEM_PROMPT})
            self.assertEqual(body["max_tokens"],700)
            self.assertIs(body["stream"],False)
            self.assertEqual(set(body),{"model","messages","max_tokens","stream"})
            evidence=json.loads(body["messages"][1]["content"])["evidence"]
            self.assertEqual(len(evidence),1)
            self.assertNotIn("hybrid_score",evidence[0])
            return httpx.Response(200,json=response())
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result=generate_answer("Invoices?",[E,E.model_copy(update={"semantic_similarity":0.2})],client=client)
        self.assertEqual(result.decision,"answer")

    @patch.dict("os.environ",{"FIREWORKS_API_KEY":"test-secret"},clear=True)
    def test_api_failures_fall_back_without_secrets(self):
        for mode in ["http","timeout","connection","json"]:
            def handler(request):
                if mode=="timeout": raise httpx.ReadTimeout("test-secret",request=request)
                if mode=="connection": raise httpx.ConnectError("test-secret",request=request)
                if mode=="json": return httpx.Response(200,text="test-secret")
                return httpx.Response(503,text="test-secret")
            with self.subTest(mode=mode), httpx.Client(transport=httpx.MockTransport(handler)) as client:
                result=generate_answer("Invoices?",[E],client=client)
                self.assertEqual(result.decision,"escalate")
                self.assertEqual(result.reason,"Support answer generation request failed.")
                self.assertNotIn("test-secret",result.model_dump_json())

    @patch.dict("os.environ",{},clear=True)
    def test_missing_key_is_explicit_fallback(self):
        client=Mock()
        result=generate_answer("Invoices?",[E],client=client)
        self.assertEqual(result.decision,"escalate")
        self.assertEqual(result.validation_error,"generation: missing_configuration")
        client.post.assert_not_called()

    def test_generation_constants_match_reference(self):
        from pathlib import Path
        contract=json.loads((Path(__file__).resolve().parents[1]/"reference/generation_contract.json").read_text())
        self.assertEqual(SYSTEM_PROMPT,contract["system_prompt"])
        self.assertEqual(MODEL,contract["model"])
        self.assertEqual(contract["max_tokens"],700)
        self.assertIs(contract["stream"],False)
