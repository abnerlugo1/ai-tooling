"""Lightweight HTTP server serving the interactive web testing application and API endpoints."""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

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
            client = APIModelClient()
            is_openai = bool(client.api_key and client.api_key.startswith("sk-")) or "gpt" in client.model_name.lower()
            stats_data = {
                "api_model": f"OpenAI {client.model_name} (Activo)" if is_openai else client.model_name,
                "embedded_model": "Qwen 2.5 Coder 7B GGUF (In-Process)",
                "vector_store": store.stats(),
                "status": "ready",
                "openai_active": is_openai,
                "model_name": client.model_name,
            }
            self._send_json(stats_data)
            return

        if parsed_url.path == "/api/kpi/dashboard-metrics":
            from orchestration.kpi_copilot import KPICopilot
            copilot = KPICopilot()
            metrics = copilot.get_dashboard_chart_metrics()
            self._send_json(metrics)
            return

        if parsed_url.path == "/api/vector/clusters":
            store = VectorStore(db_path=".vector_store.db")
            # Sample up to 120 points for 2D visualization
            points = []
            category_color_map = {
                "Asistencia vial": "#06b6d4",       # Cyan
                "Check up": "#10b981",              # Emerald
                "Membresia dental": "#a855f7",      # Purple
                "Asistencia en el hogar": "#f59e0b",# Amber
                "Plan salud": "#ec4899",            # Pink
            }

            import math
            import hashlib

            for i, chunk in enumerate(store.chunks[:120]):
                cat = chunk.metadata.get("categoria", "Otros")
                srv = chunk.metadata.get("servicio", "General")
                cliente = chunk.metadata.get("cliente", f"Doc #{i}")
                color = category_color_map.get(cat, "#64748b")

                # Pseudo-PCA projection from 384-dim embedding to 2D canvas coordinates (0-100%)
                if chunk.embedding:
                    # Project first components
                    x_raw = sum(chunk.embedding[j] * math.cos(j * 0.1) for j in range(min(60, len(chunk.embedding))))
                    y_raw = sum(chunk.embedding[j] * math.sin(j * 0.1) for j in range(min(60, len(chunk.embedding))))
                    # Normalize to 10% - 90% bounds
                    x = max(8.0, min(92.0, 50.0 + x_raw * 18.0))
                    y = max(8.0, min(92.0, 50.0 + y_raw * 18.0))
                else:
                    h = int(hashlib.md5(chunk.content.encode("utf-8")).hexdigest(), 16)
                    x = 10.0 + (h % 80)
                    y = 10.0 + ((h >> 8) % 80)

                points.append({
                    "id": chunk.chunk_id,
                    "cliente": cliente,
                    "categoria": cat,
                    "servicio": srv,
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "color": color,
                    "tokens": chunk.token_count,
                })

            self._send_json({"points": points, "total_chunks": len(store.chunks)})
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

        # 1. Embeddings generate endpoint
        if parsed_url.path == "/api/embeddings/generate":
            text = body.get("text", "").strip()
            if not text:
                self._send_json({"error": "El campo 'text' es obligatorio"}, status=400)
                return

            from ingestion.embeddings import LocalDenseEmbedder
            embedder = LocalDenseEmbedder(dimension=384)
            vec = embedder.embed_text(text)
            norm = sum(v * v for v in vec) ** 0.5
            non_zero = sum(1 for v in vec if abs(v) > 1e-6)

            # Sort top 15 activated dimensions
            indexed = [{"index": idx, "value": round(val, 4)} for idx, val in enumerate(vec) if abs(val) > 1e-4]
            indexed.sort(key=lambda x: abs(x["value"]), reverse=True)

            self._send_json({
                "text": text,
                "dimension": len(vec),
                "norm": round(norm, 5),
                "non_zero_dimensions": non_zero,
                "sample_vector": [round(v, 4) for v in vec[:32]],
                "top_activated": indexed[:15],
            })
            return

        # 2. Semantic similarity calculation
        if parsed_url.path == "/api/embeddings/similarity":
            text_a = body.get("text_a", "").strip()
            text_b = body.get("text_b", "").strip()

            from ingestion.embeddings import LocalDenseEmbedder, cosine_similarity
            embedder = LocalDenseEmbedder(dimension=384)
            vec_a = embedder.embed_text(text_a)
            vec_b = embedder.embed_text(text_b)
            score = cosine_similarity(vec_a, vec_b)
            pct = max(0.0, min(100.0, (score + 1.0) / 2.0 * 100.0))

            if score > 0.7:
                rating = "Muy Alta Similitud Semántica"
            elif score > 0.4:
                rating = "Similitud Moderada / Coincidencia de Contexto"
            elif score > 0.15:
                rating = "Baja Similitud / Relación Leve"
            else:
                rating = "Sin Relación Semántica (Ortogonales o Distantes)"

            self._send_json({
                "text_a": text_a,
                "text_b": text_b,
                "cosine_similarity": round(score, 4),
                "similarity_percentage": round(pct, 1),
                "rating": rating,
            })
            return

        # 3. Direct Vector Search
        if parsed_url.path == "/api/vector/search":
            query = body.get("query", "").strip()
            top_k = int(body.get("top_k", 5))
            hybrid = bool(body.get("hybrid", True))
            alpha = float(body.get("alpha", 0.7))

            store = VectorStore(db_path=".vector_store.db")
            results = store.search(query=query, top_k=top_k, hybrid=hybrid, alpha=alpha)

            serialized_results = []
            for r in results:
                serialized_results.append({
                    "rank": r.rank,
                    "score": round(r.score, 4),
                    "chunk_id": r.chunk.chunk_id,
                    "content": r.chunk.content,
                    "tokens": r.chunk.token_count,
                    "metadata": r.chunk.metadata,
                })

            self._send_json({
                "query": query,
                "results": serialized_results,
                "total_found": len(serialized_results),
            })
            return

        # 4. LLM Compare endpoint
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

        # 5. Agentic Orchestrator endpoint
        if parsed_url.path == "/api/orchestration/run":
            query = body.get("query", "¿Cuál es el servicio más solicitado y cuál es la edad promedio de los clientes?").strip()
            model_type = body.get("model", "openai").lower()

            from orchestration.agent import OrchestratorAgent
            if model_type in ("openai", "api", "gpt-6-luna", "cloud"):
                llm = APIModelClient()
            else:
                llm = EmbeddedModelClient()
            agent = OrchestratorAgent(llm=llm)

            trace = agent.run(query)
            self._send_json(trace.to_dict())
            return

        # 6. Dedicated OpenAI KPI Analytics Copilot endpoint (strictly for dashboard.db)
        if parsed_url.path == "/api/kpi/query":
            query = body.get("query", "").strip()
            if not query:
                self._send_json({"error": "El campo 'query' es obligatorio"}, status=400)
                return

            from orchestration.kpi_copilot import KPICopilot
            copilot = KPICopilot()
            result = copilot.ask_kpi(query)
            self._send_json(result)
            return

        # 7. Executive Chart Analysis with OpenAI
        if parsed_url.path == "/api/kpi/analyze-charts":
            focus = body.get("focus", "global")
            from orchestration.kpi_copilot import KPICopilot
            copilot = KPICopilot()
            analysis_res = copilot.analyze_charts(focus=focus)
            self._send_json(analysis_res)
            return

        self._send_json({"error": f"Endpoint not found: {parsed_url.path}"}, status=404)


def run_server(host: Optional[str] = None, port: Optional[int] = None) -> None:
    try:
        from dotenv import load_dotenv
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except Exception:
        pass
    host = host or os.getenv("HOST", "0.0.0.0")
    port = port or int(os.getenv("PORT", "8080"))
    server_address = (host, port)
    httpd = HTTPServer(server_address, HarnessRequestHandler)
    print(f"[+] LLM Architecture Test Harness running at http://{host}:{port}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")


if __name__ == "__main__":
    run_server()
