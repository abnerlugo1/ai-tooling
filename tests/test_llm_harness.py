"""Unit tests for the LLM architecture comparison harness."""

import unittest

from llm_harness.api_client import APIModelClient
from llm_harness.comparator import LLMComparator
from llm_harness.embedded_client import EmbeddedModelClient
from llm_harness.models import ArchitectureType, LLMRequest


class TestLLMHarness(unittest.TestCase):
    def setUp(self):
        self.api_client = APIModelClient(force_simulation=True)
        self.embedded_client = EmbeddedModelClient()
        self.comparator = LLMComparator(self.api_client, self.embedded_client)

    def test_api_client_generation(self):
        req = LLMRequest(prompt="Test API prompt")
        res = self.api_client.generate(req)

        self.assertEqual(res.architecture, ArchitectureType.API)
        self.assertGreater(res.metrics.total_latency_ms, 0)
        self.assertGreater(res.metrics.estimated_cost_usd, 0)
        self.assertEqual(res.metrics.network_calls_count, 1)
        self.assertFalse(res.metrics.privacy_airgapped)
        self.assertIn("API-Based Architecture Response", res.text)

    def test_embedded_client_generation(self):
        req = LLMRequest(prompt="Test embedded prompt")
        res = self.embedded_client.generate(req)

        self.assertEqual(res.architecture, ArchitectureType.EMBEDDED)
        self.assertGreater(res.metrics.total_latency_ms, 0)
        self.assertEqual(res.metrics.estimated_cost_usd, 0.0)
        self.assertEqual(res.metrics.network_calls_count, 0)
        self.assertTrue(res.metrics.privacy_airgapped)
        self.assertIn("Embedded Architecture Response", res.text)

    def test_comparator_analysis(self):
        req = LLMRequest(prompt="Compare architectures", context_chunks=["Chunk 1", "Chunk 2"])
        comparison = self.comparator.compare(req)

        self.assertEqual(comparison.api_response.architecture, ArchitectureType.API)
        self.assertEqual(comparison.embedded_response.architecture, ArchitectureType.EMBEDDED)
        self.assertIsNotNone(comparison.winner_latency)
        self.assertEqual(comparison.winner_cost, ArchitectureType.EMBEDDED)
        self.assertGreater(len(comparison.summary), 20)

    def test_context_chunks_grounding(self):
        req = LLMRequest(prompt="Explain RAG", context_chunks=["AWS Bedrock Knowledge Bases provide RAG."])
        res = self.api_client.generate(req)
        self.assertIn("Contextual Ingestion Grounding", res.text)


if __name__ == "__main__":
    unittest.main()
