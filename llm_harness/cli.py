"""Command line runner for LLM Architecture evaluation."""

from __future__ import annotations

import argparse
import json
import sys

from llm_harness.comparator import LLMComparator
from llm_harness.models import LLMRequest


def main():
    parser = argparse.ArgumentParser(description="Evaluate API vs Embedded LLM architectures")
    parser.add_argument("prompt", nargs="?", default="¿Cuáles son las diferencias entre modelos basados en API y modelos integrados?", help="Prompt to evaluate")
    parser.add_argument("--json", action="store_true", help="Output full JSON benchmark")
    parser.add_argument("--rag", action="store_true", help="Retrieve context from vector store")
    args = parser.parse_args()

    context_chunks = []
    if args.rag:
        try:
            from ingestion.vector_store import VectorStore
            store = VectorStore(db_path=".vector_store.db")
            res = store.search(args.prompt, top_k=2, hybrid=True)
            context_chunks = [r.chunk.content for r in res]
            print(f"[*] Injected {len(context_chunks)} RAG chunks into prompt context.")
        except Exception as e:
            print(f"[!] Warning: RAG retrieval failed: {e}")

    req = LLMRequest(prompt=args.prompt, context_chunks=context_chunks)
    comparator = LLMComparator()
    comparison = comparator.compare(req)

    if args.json:
        print(json.dumps(comparison.to_dict(), indent=2, ensure_ascii=False))
        return

    print("\n" + "=" * 70)
    print("           LLM ARCHITECTURE BENCHMARK: API vs EMBEDDED")
    print("=" * 70)
    print(f"Prompt: {args.prompt}\n")

    api = comparison.api_response
    emb = comparison.embedded_response

    print(f"1. ARQUITECTURA BASADA EN API ({api.model_name})")
    print(f"   - Latencia Total: {api.metrics.total_latency_ms:.1f} ms (TTFT: {api.metrics.time_to_first_token_ms:.1f} ms)")
    print(f"   - Throughput    : {api.metrics.tokens_per_second:.1f} tokens/seg")
    print(f"   - Costo Estimado: ${api.metrics.estimated_cost_usd:.6f} USD")
    print(f"   - Memoria RAM   : {api.metrics.memory_rss_mb:.1f} MB (Ligero en cliente)")
    print(f"   - Privacidad    : Tránsito HTTPS / Nube de terceros")

    print(f"\n2. ARQUITECTURA DE MODELO INTEGRADO ({emb.model_name})")
    print(f"   - Latencia Total: {emb.metrics.total_latency_ms:.1f} ms (TTFT: {emb.metrics.time_to_first_token_ms:.1f} ms)")
    print(f"   - Throughput    : {emb.metrics.tokens_per_second:.1f} tokens/seg")
    print(f"   - Costo Estimado: ${emb.metrics.estimated_cost_usd:.6f} USD (Cero costo de API)")
    print(f"   - Memoria RAM   : {emb.metrics.memory_rss_mb:,.0f} MB (Residente local)")
    print(f"   - Privacidad    : 100% Air-Gapped (0 llamadas externas)")

    print("\n" + "-" * 70)
    print(comparison.summary)
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
