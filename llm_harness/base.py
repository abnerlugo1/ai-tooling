"""Base interface for LLM client implementations."""

from __future__ import annotations

import abc
from llm_harness.models import ArchitectureType, LLMRequest, LLMResponse


class BaseLLM(abc.ABC):
    """Abstract base class for LLM architectures."""

    @property
    @abc.abstractmethod
    def architecture(self) -> ArchitectureType:
        """Returns whether the model is API-based or Embedded."""
        pass

    @property
    @abc.abstractmethod
    def model_name(self) -> str:
        """Identifier of the underlying model."""
        pass

    @abc.abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Executes generation and returns output with performance metrics."""
        pass

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Standardized token approximation heuristic."""
        if not text:
            return 0
        words = len(text.split())
        chars = len(text)
        return max(1, int((words * 1.3 + chars / 3.8) / 2))
