"""LLM Architectural Harness: API-based vs Embedded In-Process Models."""

from llm_harness.api_client import APIModelClient
from llm_harness.base import BaseLLM
from llm_harness.comparator import LLMComparator
from llm_harness.embedded_client import EmbeddedModelClient
from llm_harness.models import (
    ArchitectureType,
    BenchmarkComparison,
    ExecutionMetrics,
    LLMRequest,
    LLMResponse,
)

__all__ = [
    "APIModelClient",
    "ArchitectureType",
    "BaseLLM",
    "BenchmarkComparison",
    "EmbeddedModelClient",
    "ExecutionMetrics",
    "LLMComparator",
    "LLMRequest",
    "LLMResponse",
]
