"""Embedded / In-process LLM client implementation (On-Device / Local Engine)."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from llm_harness.base import BaseLLM
from llm_harness.models import ArchitectureType, ExecutionMetrics, LLMRequest, LLMResponse


class EmbeddedModelClient(BaseLLM):
    """
    Client for Embedded / In-Process LLM architectures (e.g., llama.cpp GGUF, ONNX Runtime).
    Characterized by:
      - 100% In-process local execution (zero network calls, completely air-gapped)
      - Zero per-token API cost ($0.00 variable cost)
      - Local hardware compute utilization (RAM / VRAM resident)
      - Low, deterministic latency free from internet/network jitter
    """

    def __init__(
        self,
        model_name: str = "qwen2.5-coder-7b-instruct.Q4_K_M.gguf",
        model_path: Optional[str] = None,
        threads: int = 4,
        context_window: int = 4096,
    ) -> None:
        self._model_name = model_name
        self.model_path = model_path or os.getenv("EMBEDDED_MODEL_PATH")
        self.threads = threads
        self.context_window = context_window

    @property
    def architecture(self) -> ArchitectureType:
        return ArchitectureType.EMBEDDED

    @property
    def model_name(self) -> str:
        return self._model_name

    def _execute_embedded_inference(self, request: LLMRequest) -> str:
        """Executes in-process generation using embedded logic."""
        context_summary = ""
        if request.context_chunks:
            context_summary = (
                f"\n[Contextual Grounding: {len(request.context_chunks)} local chunks integrated into context window.]"
            )

        output = (
            f"[Embedded Architecture Response | Engine: In-Process Local Engine ({self._model_name})]\n\n"
            f"Inferencia generada localmente en proceso (CPU/VRAM embebida):\n"
            f"- Arquitectura: Modelo integrado / In-Process On-Premise.\n"
            f"- Entrada procesada: \"{request.prompt}\"\n"
            f"- Ventajas operativas: Cumplimiento total de privacidad (Air-Gapped, datos jamás salen del host), "
            f"costo de token nulo ($0.00) y funcionamiento sin conectividad a internet.\n"
            f"- Consideraciones de diseño: Requiere memoria residente (~4.2 GB RAM/VRAM para Q4_K_M), "
            f"concurrencia acotada por los núcleos de hardware disponibles y menor velocidad pico en CPUs modestas."
            f"{context_summary}"
        )
        return output

    def generate(self, request: LLMRequest) -> LLMResponse:
        full_prompt = request.prompt
        if request.context_chunks:
            full_prompt = (
                f"Context:\n" + "\n---\n".join(request.context_chunks) + f"\n\nQuestion: {request.prompt}"
            )

        prompt_tokens = self.estimate_tokens(full_prompt)
        start_time = time.perf_counter()

        # Simulate local compute cycle (compute-bound, fast TTFT ~45ms, generation ~90ms)
        time.sleep(0.09)
        response_text = self._execute_embedded_inference(request)

        end_time = time.perf_counter()
        total_latency_ms = (end_time - start_time) * 1000.0
        ttft_ms = 42.0  # Ultra-fast time-to-first-token locally without network handshake

        completion_tokens = self.estimate_tokens(response_text)
        tokens_per_second = (
            (completion_tokens / (total_latency_ms / 1000.0)) if total_latency_ms > 0 else 0.0
        )

        metrics = ExecutionMetrics(
            total_latency_ms=total_latency_ms,
            time_to_first_token_ms=ttft_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_per_second=tokens_per_second,
            estimated_cost_usd=0.0,  # Zero API cost
            memory_rss_mb=4200.0,   # Simulated 4.2 GB weight allocation
            network_calls_count=0,
            privacy_airgapped=True,
        )

        return LLMResponse(
            text=response_text,
            architecture=ArchitectureType.EMBEDDED,
            model_name=self._model_name,
            metrics=metrics,
            metadata={
                "compute_device": "Host Local (CPU/AVX2 + Metal/CUDA)",
                "quantization": "Q4_K_M GGUF",
                "threads": self.threads,
                "air_gapped": True,
            },
        )
