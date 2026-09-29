"""Data models for API-based vs Embedded LLM architecture benchmarking."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ArchitectureType(str, Enum):
    API = "API_BASED"
    EMBEDDED = "EMBEDDED_LOCAL"


@dataclass
class LLMRequest:
    prompt: str
    temperature: float = 0.7
    max_tokens: int = 512
    system_prompt: Optional[str] = None
    stream: bool = False
    context_chunks: List[str] = field(default_factory=list)


@dataclass
class ExecutionMetrics:
    total_latency_ms: float
    time_to_first_token_ms: float
    prompt_tokens: int
    completion_tokens: int
    tokens_per_second: float
    estimated_cost_usd: float
    memory_rss_mb: float = 0.0
    network_calls_count: int = 0
    privacy_airgapped: bool = False


@dataclass
class LLMResponse:
    text: str
    architecture: ArchitectureType
    model_name: str
    metrics: ExecutionMetrics
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "architecture": self.architecture.value,
            "model_name": self.model_name,
            "metrics": {
                "total_latency_ms": round(self.metrics.total_latency_ms, 2),
                "time_to_first_token_ms": round(self.metrics.time_to_first_token_ms, 2),
                "prompt_tokens": self.metrics.prompt_tokens,
                "completion_tokens": self.metrics.completion_tokens,
                "tokens_per_second": round(self.metrics.tokens_per_second, 2),
                "estimated_cost_usd": round(self.metrics.estimated_cost_usd, 6),
                "memory_rss_mb": round(self.metrics.memory_rss_mb, 2),
                "network_calls_count": self.metrics.network_calls_count,
                "privacy_airgapped": self.metrics.privacy_airgapped,
            },
            "metadata": self.metadata,
        }


@dataclass
class BenchmarkComparison:
    api_response: LLMResponse
    embedded_response: LLMResponse
    latency_delta_ms: float
    cost_delta_usd: float
    winner_latency: ArchitectureType
    winner_cost: ArchitectureType
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api": self.api_response.to_dict(),
            "embedded": self.embedded_response.to_dict(),
            "latency_delta_ms": round(self.latency_delta_ms, 2),
            "cost_delta_usd": round(self.cost_delta_usd, 6),
            "winner_latency": self.winner_latency.value,
            "winner_cost": self.winner_cost.value,
            "summary": self.summary,
        }
