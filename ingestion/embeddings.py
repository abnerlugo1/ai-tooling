"""Embeddings providers and vectorizers for dense and hybrid semantic search."""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Dict, List, Optional


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Calculates cosine similarity between two float vectors."""
    if len(vec_a) != len(vec_b):
        raise ValueError(f"Vector dimensions mismatch: {len(vec_a)} vs {len(vec_b)}")

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class BaseEmbedder:
    """Abstract base class for text embedding models."""

    @property
    def dimension(self) -> int:
        raise NotImplementedError

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


class LocalDenseEmbedder(BaseEmbedder):
    """
    Lightweight, zero-external-dependency embedding vectorizer based on
    feature-hashing with subword n-grams and L2 normalization.
    Provides fast, deterministic vectors (default 384 dimensions) for local testing,
    offline environments, and continuous integration.
    """

    def __init__(self, dimension: int = 384) -> None:
        self._dim = dimension

    @property
    def dimension(self) -> int:
        return self._dim

    def _tokenize(self, text: str) -> List[str]:
        words = re.findall(r"\b\w+\b", text.lower())
        tokens = list(words)
        # Add character tri-grams for subword morphological matching
        for word in words:
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    tokens.append(word[i : i + 3])
        return tokens

    def embed_text(self, text: str) -> List[float]:
        vector = [0.0] * self._dim
        tokens = self._tokenize(text)

        if not tokens:
            return vector

        # Count frequencies
        token_freq: Dict[str, int] = {}
        for token in tokens:
            token_freq[token] = token_freq.get(token, 0) + 1

        for token, count in token_freq.items():
            # Stable md5 hash mapped to dimension slot
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            index = h % self._dim
            sign = 1.0 if ((h >> 8) & 1) == 0 else -1.0
            # Term weight with log scaling
            weight = (1.0 + math.log(count)) * sign
            vector[index] += weight

        # L2 normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [v / norm for v in vector]

        return vector


class BM25Scorer:
    """Lightweight Okapi BM25 implementation for lexical keyword ranking."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.doc_lens: List[int] = []
        self.tokenized_corpus: List[List[str]] = []

    def fit(self, corpus: List[str]) -> None:
        self.corpus_size = len(corpus)
        self.tokenized_corpus = [re.findall(r"\b\w+\b", doc.lower()) for doc in corpus]
        self.doc_lens = [len(doc) for doc in self.tokenized_corpus]
        self.avg_doc_len = (sum(self.doc_lens) / self.corpus_size) if self.corpus_size > 0 else 0.0

        self.doc_freqs = {}
        for doc in self.tokenized_corpus:
            unique_terms = set(doc)
            for term in unique_terms:
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

    def score(self, query: str, doc_index: int) -> float:
        query_terms = re.findall(r"\b\w+\b", query.lower())
        doc_tokens = self.tokenized_corpus[doc_index]
        doc_len = self.doc_lens[doc_index]
        score = 0.0

        term_freqs: Dict[str, int] = {}
        for token in doc_tokens:
            term_freqs[token] = term_freqs.get(token, 0) + 1

        for term in query_terms:
            if term not in term_freqs:
                continue

            df = self.doc_freqs.get(term, 0)
            idf = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)
            tf = term_freqs[term]

            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
            score += idf * (numerator / denominator)

        return score


class BedrockTitanEmbedder(BaseEmbedder):
    """
    Amazon Bedrock Titan Embeddings connector (e.g. amazon.titan-embed-text-v1/v2).
    Requires boto3 and AWS credentials.
    """

    def __init__(
        self,
        model_id: str = "amazon.titan-embed-text-v2:0",
        region_name: Optional[str] = None,
        dimensions: int = 1024,
    ) -> None:
        self.model_id = model_id
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self._dim = dimensions
        self._client = None

    @property
    def dimension(self) -> int:
        return self._dim

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client("bedrock-runtime", region_name=self.region_name)
            except ImportError:
                raise ImportError("boto3 is required for BedrockTitanEmbedder. Install with: pip install boto3")
        return self._client

    def embed_text(self, text: str) -> List[float]:
        import json
        client = self._get_client()
        body = json.dumps({"inputText": text, "dimensions": self._dim, "normalize": True})
        response = client.invoke_model(
            modelId=self.model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        response_body = json.loads(response["body"].read())
        return response_body["embedding"]
