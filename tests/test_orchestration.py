"""Unit tests for Agentic AI Orchestrator and Tool Use."""

import unittest

from llm_harness.embedded_client import EmbeddedModelClient
from orchestration.agent import OrchestratorAgent
from orchestration.tools import ToolRegistry


class TestOrchestration(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.agent = OrchestratorAgent(
            llm=EmbeddedModelClient(),
            tool_registry=self.registry,
        )

    def test_tool_registry_tools_present(self):
        tools = self.registry.list_tools()
        tool_names = [t["name"] for t in tools]
        self.assertIn("sql_query", tool_names)
        self.assertIn("get_db_schema", tool_names)
        self.assertIn("semantic_search", tool_names)
        self.assertIn("ingest_document", tool_names)

    def test_sql_tool_safety(self):
        sql_tool = self.registry.get_tool("sql_query")
        self.assertIsNotNone(sql_tool)

        # SELECT allowed
        res = sql_tool.execute(query="SELECT COUNT(*) as total FROM dashboard;")
        self.assertIn("rows", res)
        self.assertEqual(res["rows"][0]["total"], 2999)

        # DROP / DELETE blocked
        res_bad = sql_tool.execute(query="DROP TABLE dashboard;")
        self.assertIn("error", res_bad)

    def test_agent_sql_orchestration_trace(self):
        query = "¿Cuál es el servicio más solicitado y cuál es la edad promedio de los clientes?"
        trace = self.agent.run(query)

        self.assertGreater(len(trace.steps), 1)
        self.assertIn("sql_query", trace.tools_invoked)
        self.assertGreater(len(trace.final_answer), 20)
        self.assertGreater(trace.total_latency_ms, 0)

        # Test dictionary serialization
        d = trace.to_dict()
        self.assertEqual(d["query"], query)
        self.assertIn("steps", d)

    def test_agent_semantic_search_trace(self):
        query = "Busca registros de clientes atendidos por emergencias de plomería o fugas de agua"
        trace = self.agent.run(query)

        self.assertGreater(len(trace.steps), 1)
        self.assertIn("semantic_search", trace.tools_invoked)
        self.assertGreater(len(trace.final_answer), 20)


if __name__ == "__main__":
    unittest.main()
