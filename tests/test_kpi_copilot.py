"""Unit tests for the dedicated KPI Copilot for dashboard.db."""

import unittest
from pathlib import Path

from llm_harness.api_client import APIModelClient
from orchestration.kpi_copilot import KPICopilot


class TestKPICopilot(unittest.TestCase):
    def setUp(self):
        # Force simulation to test deterministic logic without requiring live network calls
        self.simulated_llm = APIModelClient(force_simulation=True)
        self.copilot = KPICopilot(llm=self.simulated_llm)

    def test_kpi_scope_guardrail_allows_kpi_queries(self):
        self.assertTrue(self.copilot._is_kpi_related("¿Cuál es la edad promedio por categoría?"))
        self.assertTrue(self.copilot._is_kpi_related("Top 5 servicios más solicitados"))
        self.assertTrue(self.copilot._is_kpi_related("Porcentaje de clientes mujeres vs hombres"))
        self.assertTrue(self.copilot._is_kpi_related("¿Cuántas solicitudes de Asistencia vial existen?"))

    def test_kpi_scope_guardrail_blocks_out_of_scope_queries(self):
        self.assertFalse(self.copilot._is_kpi_related("¿Cuál es la capital de Francia?"))
        self.assertFalse(self.copilot._is_kpi_related("Escribe un poema sobre el sol"))
        self.assertFalse(self.copilot._is_kpi_related("¿Cómo programar en Rust?"))

    def test_guardrail_rejection_response(self):
        res = self.copilot.ask_kpi("Explica la fotosíntesis")
        self.assertFalse(res["is_kpi_query"])
        self.assertIsNone(res["sql"])
        self.assertEqual(res["total_rows"], 0)
        self.assertIn("Consulta fuera de alcance", res["analysis"])

    def test_sql_execution_safety(self):
        # SELECT is executed
        res = self.copilot._execute_sql("SELECT COUNT(*) as total FROM dashboard;")
        self.assertEqual(res["rows"][0]["total"], 2999)

        # DROP is blocked
        res_bad = self.copilot._execute_sql("DROP TABLE dashboard;")
        self.assertIn("error", res_bad)


if __name__ == "__main__":
    unittest.main()
