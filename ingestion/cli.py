"""Command Line Interface (CLI) for Ingestion and Processing Pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ingestion.chunker import RecursiveCharacterChunker
from ingestion.pipeline import IngestionPipeline
from ingestion.vector_store import VectorStore


def cmd_ingest(args: argparse.Namespace) -> None:
    """Ingests files or a folder into the vector store."""
    print(f"[*] Starting ingestion on source: {args.source}")
    chunker = RecursiveCharacterChunker(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    vector_store = VectorStore(db_path=args.db)
    pipeline = IngestionPipeline(chunker=chunker, vector_store=vector_store)

    report = pipeline.run(args.source)

    print("\n--- Ingestion Report ---")
    print(f"Documents Loaded : {report.documents_loaded}")
    print(f"Chunks Created   : {report.chunks_created}")
    print(f"Estimated Tokens : {report.total_tokens}")
    print(f"Duration         : {report.duration_seconds:.3f}s")

    if report.errors:
        print(f"Errors ({len(report.errors)}):")
        for err in report.errors:
            print(f"  - {err}")
    else:
        print("[OK] Ingestion completed successfully.")


def cmd_query(args: argparse.Namespace) -> None:
    """Searches the vector store with a user query."""
    vector_store = VectorStore(db_path=args.db)
    if not vector_store.chunks:
        print(f"[!] No documents found in database '{args.db}'. Run 'ingest' first.")
        sys.exit(1)

    print(f"[*] Querying '{args.query}' (top_k={args.top_k}, hybrid={args.hybrid})...\n")
    results = vector_store.search(
        query=args.query,
        top_k=args.top_k,
        hybrid=args.hybrid,
        alpha=args.alpha,
    )

    if not results:
        print("[-] No matching chunks found.")
        return

    for res in results:
        chunk = res.chunk
        src = chunk.metadata.get("source", "N/A")
        print(f"============================================================")
        print(f"Rank {res.rank} | Score: {res.score:.4f} | Chunk ID: {chunk.chunk_id}")
        print(f"Source: {src} (Tokens: ~{chunk.token_count})")
        print(f"------------------------------------------------------------")
        preview = chunk.content[:400] + ("..." if len(chunk.content) > 400 else "")
        print(preview)
        print()


def cmd_stats(args: argparse.Namespace) -> None:
    """Shows statistics about the vector store."""
    vector_store = VectorStore(db_path=args.db)
    stats = vector_store.stats()
    print("\n--- Vector Store Statistics ---")
    print(json.dumps(stats, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion.cli",
        description="Ingestion & Processing Pipeline CLI for RAG & AI Tooling",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Ingest command
    parser_ingest = subparsers.add_parser("ingest", help="Ingest a file or directory into vector store")
    parser_ingest.add_argument("source", help="Path to file or folder to ingest")
    parser_ingest.add_argument("--db", default=".vector_store.db", help="SQLite database path (default: .vector_store.db)")
    parser_ingest.add_argument("--chunk-size", type=int, default=500, help="Max chunk size in characters")
    parser_ingest.add_argument("--chunk-overlap", type=int, default=50, help="Overlap between chunks in characters")
    parser_ingest.set_defaults(func=cmd_ingest)

    # Query command
    parser_query = subparsers.add_parser("query", help="Semantic query against vector store")
    parser_query.add_argument("query", help="Text search query")
    parser_query.add_argument("--db", default=".vector_store.db", help="SQLite database path")
    parser_query.add_argument("--top-k", type=int, default=3, help="Number of results to return")
    parser_query.add_argument("--hybrid", action="store_true", help="Enable hybrid dense + BM25 search")
    parser_query.add_argument("--alpha", type=float, default=0.7, help="Dense vs BM25 weight (0.0 to 1.0)")
    parser_query.set_defaults(func=cmd_query)

    # Stats command
    parser_stats = subparsers.add_parser("stats", help="Display vector store statistics")
    parser_stats.add_argument("--db", default=".vector_store.db", help="SQLite database path")
    parser_stats.set_defaults(func=cmd_stats)

    parsed_args = parser.parse_args()
    parsed_args.func(parsed_args)


if __name__ == "__main__":
    main()
