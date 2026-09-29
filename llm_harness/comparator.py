"""Comparator engine for evaluating API-based vs Embedded LLM architectures."""

from __future__ import annotations

from typing import Optional

from llm_harness.api_client import APIModelClient
from llm_harness.embedded_client import EmbeddedModelClient
from llm_harness.models import ArchitectureType, BenchmarkComparison, LLMRequest


class LLMComparator:
    """Executes side-by-side comparative benchmarking between API and Embedded models."""

    def __init__(
        self,
        api_client: Optional[APIModelClient] = None,
        embedded_client: Optional[EmbeddedModelClient] = None,
    ) -> None:
        self.api_client = api_client or APIModelClient()
        self.embedded_client = embedded_client or EmbeddedModelClient()

    def compare(self, request: LLMRequest) -> BenchmarkComparison:
        """Executes the prompt on both architectures and analyzes trade-offs."""
        # 1. Run API-based inference
        api_res = self.api_client.generate(request)

        # 2. Run Embedded in-process inference
        embedded_res = self.embedded_client.generate(request)

        # 3. Analyze differentials
        latency_delta = api_res.metrics.total_latency_ms - embedded_res.metrics.total_latency_ms
        cost_delta = api_res.metrics.estimated_cost_usd - embedded_res.metrics.estimated_cost_usd

        winner_latency = (
            ArchitectureType.EMBEDDED
            if embedded_res.metrics.total_latency_ms < api_res.metrics.total_latency_ms
            else ArchitectureType.API
        )

        winner_cost = (
            ArchitectureType.EMBEDDED
            if embedded_res.metrics.estimated_cost_usd <= api_res.metrics.estimated_cost_usd
            else ArchitectureType.API
        )

        # Generate contextual summary
        summary = (
            f"Comparativa completada:\n"
            f"- Latencia: {winner_latency.value} fue más veloz por {abs(latency_delta):.1f} ms "
            f"(TTFT: Local {embedded_res.metrics.time_to_first_token_ms:.1f}ms vs API {api_res.metrics.time_to_first_token_ms:.1f}ms).\n"
            f"- Costo por consulta: {winner_cost.value} ahorra ${abs(cost_delta):.6f} USD por llamada.\n"
            f"- Privacidad y Seguridad: El modelo integrado (EMBEDDED) no realiza llamadas externas (Air-Gapped, 0 paquetes a internet), "
            f"mientras que el modelo API requiere canal cifrado HTTPS a proveedores cloud gestionados.\n"
            f"- Huella de memoria en cliente: API utiliza apenas {api_res.metrics.memory_rss_mb:.1f} MB frente a "
            f"{embedded_res.metrics.memory_rss_mb:.0f} MB del modelo integrado residente."
        )

        return BenchmarkComparison(
            api_response=api_res,
            embedded_response=embedded_res,
            latency_delta_ms=latency_delta,
            cost_delta_usd=cost_delta,
            winner_latency=winner_latency,
            winner_cost=winner_cost,
            summary=summary,
        )
