"""Tool definitions and registry for Agentic AI Orchestrator."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from dashboard_db import DashboardDB
from ingestion.pipeline import IngestionPipeline
from ingestion.vector_store import VectorStore


@dataclass
class Tool:
    """Represents an executable tool usable by the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable[..., Any]

    def execute(self, **kwargs) -> Any:
        return self.func(**kwargs)


class ToolRegistry:
    """Registry maintaining tools available to the orchestrator agent."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    def _register_default_tools(self) -> None:
        # 1. SQLite Query Tool
        def run_sql(query: str) -> Dict[str, Any]:
            cleaned = query.strip().rstrip(";")
            if ";" in cleaned:
                return {"error": "Multi-sentencias no permitidas."}

            upper_q = cleaned.upper()
            first_token = upper_q.split()[0] if upper_q.split() else ""
            if first_token not in ("SELECT", "WITH", "PRAGMA"):
                return {"error": "Solo se permiten consultas de lectura (SELECT / WITH / PRAGMA)."}

            blocked = ("ATTACH", "DETACH", "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE")
            for b in blocked:
                if f" {b} " in f" {upper_q} ":
                    return {"error": f"Operación no permitida: {b}"}

            try:
                db = DashboardDB()
                results = db.query(cleaned + ";")
                return {
                    "total_rows": len(results),
                    "rows": results[:50],  # cap at 50 rows for prompt safety
                    "truncated": len(results) > 50,
                }
            except Exception as e:
                return {"error": str(e)}

        self.register(Tool(
            name="sql_query",
            description="Ejecuta consultas SQL sobre la base de datos de dashboard (tabla 'dashboard': id, cliente, edad, genero, num_cuenta, categoria, servicio, fecha). Útil para conteos, promedios, filtros exactos, agrupaciones y estadísticas.",
            parameters={"query": "string (sentencia SQL SELECT válida)"},
            func=run_sql,
        ))

        # 2. Database Schema Inspector Tool
        def get_db_schema() -> Dict[str, Any]:
            db = DashboardDB()
            schema_info = db.query("PRAGMA table_info(dashboard)")
            return {
                "table_name": "dashboard",
                "columns": [{"name": col["name"], "type": col["type"]} for col in schema_info],
                "total_records": db.query("SELECT COUNT(*) as total FROM dashboard")[0]["total"],
            }

        self.register(Tool(
            name="get_db_schema",
            description="Obtiene el esquema de columnas y tipos de datos de la tabla 'dashboard'.",
            parameters={},
            func=get_db_schema,
        ))

        # 3. Vector Search RAG Tool
        def run_vector_search(query: str, top_k: int = 3, hybrid: bool = True) -> Dict[str, Any]:
            store = VectorStore(db_path=".vector_store.db")
            results = store.search(query=query, top_k=top_k, hybrid=hybrid)
            return {
                "query": query,
                "results_count": len(results),
                "chunks": [
                    {
                        "score": round(r.score, 4),
                        "content": r.chunk.content,
                        "metadata": r.chunk.metadata,
                    }
                    for r in results
                ],
            }

        self.register(Tool(
            name="semantic_search",
            description="Búsqueda vectorial semántica e híbrida en el Vector Store (3,001 chunks de dashboard .xlsx y capstones). Útil para buscar conceptos descriptivos, notas de servicio, consultas de texto libre o similitud.",
            parameters={"query": "string", "top_k": "int (default 3)", "hybrid": "bool (default True)"},
            func=run_vector_search,
        ))

        # 4. Ingestion Pipeline Tool (Hardened against Path Traversal)
        def run_ingestion(source_path: str) -> Dict[str, Any]:
            base_dir = Path(__file__).resolve().parent.parent
            target = Path(source_path)
            resolved = target.resolve() if target.is_absolute() else (base_dir / target).resolve()

            # Prevent directory traversal outside the workspace
            try:
                resolved.relative_to(base_dir)
            except ValueError:
                return {"error": "Acceso denegado: solo se permite ingestar archivos dentro del directorio del proyecto."}

            if not resolved.exists():
                return {"error": f"Archivo o carpeta no encontrada: {source_path}"}

            pipeline = IngestionPipeline(db_path=".vector_store.db")
            report = pipeline.run(str(resolved))
            return report.to_dict()

        self.register(Tool(
            name="ingest_document",
            description="Carga, divide en chunks y vectoriza un nuevo archivo o carpeta (Markdown, TXT, CSV, Excel) en la base de datos vectorial.",
            parameters={"source_path": "string (ruta del archivo o directorio)"},
            func=run_ingestion,
        ))
