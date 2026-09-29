"""Lightweight HTTP server serving the interactive web testing application and API endpoints."""

from __future__ import annotations

import json
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict
import urllib.parse

from ingestion.pipeline import IngestionPipeline
from ingestion.vector_store import VectorStore
from llm_harness.api_client import APIModelClient
from llm_harness.comparator import LLMComparator
from llm_harness.embedded_client import EmbeddedModelClient
from llm_harness.models import LLMRequest

WEB_DIR = Path(__file__).parent / "web"


class HarnessRequestHandler(SimpleHTTPRequestHandler):
    """Handles static web UI assets and REST API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)

        if parsed_url.path == "/api/stats":
            store = VectorStore(db_path=".vector_store.db")
            stats_data = {
                "api_model": "Anthropic Claude 3.5 Sonnet / AWS Bedrock",
                "embedded_model": "Qwen 2.5 Coder 7B GGUF (In-Process)",
                "vector_store": store.stats(),
                "status": "ready",
            }
            self._send_json(stats_data)
            return

        # Serve static assets
        super().do_GET()

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_length)

        try:
            body = json.loads(post_body.decode("utf-8")) if post_body else {}
        except Exception:
            self._send_json({"error": "Invalid JSON payload"}, status=400)
            return

        if parsed_url.path == "/api/compare":
            prompt = body.get("prompt", "Explica la diferencia entre arquitecturas de LLM basadas en API y modelos integrados.")
            max_tokens = int(body.get("max_tokens", 512))
            temperature = float(body.get("temperature", 0.7))
            use_rag = bool(body.get("use_rag", False))
            top_k = int(body.get("top_k", 2))

            context_chunks = []
            if use_rag:
                store = VectorStore(db_path=".vector_store.db")
                if not store.chunks:
                    # Auto-ingest capstones if DB is empty
                    capstones_dir = Path(__file__).resolve().parent.parent / "capstones"
                    if capstones_dir.exists():
                        pipeline = IngestionPipeline(vector_store=store, db_path=".vector_store.db")
                        pipeline.run(capstones_dir)

                search_res = store.search(prompt, top_k=top_k, hybrid=True)
                context_chunks = [r.chunk.content for r in search_res]

            req = LLMRequest(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                context_chunks=context_chunks,
            )

            comparator = LLMComparator()
            comparison = comparator.compare(req)

            resp_data = comparison.to_dict()
            resp_data["context_chunks_used"] = len(context_chunks)
            self._send_json(resp_data)
            return

        self._send_json({"error": f"Endpoint not found: {parsed_url.path}"}, status=404)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server_address = (host, port)
    httpd = HTTPServer(server_address, HarnessRequestHandler)
    print(f"[+] LLM Architecture Test Harness running at http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")


if __name__ == "__main__":
    run_server()
