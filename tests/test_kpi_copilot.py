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

    def test_get_dashboard_chart_metrics(self):
        metrics = self.copilot.get_dashboard_chart_metrics()
        self.assertIn("summary", metrics)
        self.assertIn("categories", metrics)
        self.assertIn("gender", metrics)
        self.assertIn("top_services", metrics)
        self.assertIn("timeline", metrics)
        self.assertEqual(metrics["summary"]["total_records"], 2999)
        self.assertEqual(len(metrics["categories"]), 7)
        self.assertEqual(len(metrics["gender"]), 2)
        self.assertEqual(len(metrics["top_services"]), 6)
        self.assertEqual(len(metrics["timeline"]), 12)

    def test_analyze_charts(self):
        analysis = self.copilot.analyze_charts(focus="global")
        self.assertIn("analysis", analysis)
        self.assertEqual(analysis["focus"], "global")
        self.assertTrue(len(analysis["analysis"]) > 20)


if __name__ == "__main__":
    unittest.main()

