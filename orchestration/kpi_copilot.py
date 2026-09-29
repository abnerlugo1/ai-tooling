"""KPI Analytics Copilot exclusively dedicated to querying and analyzing Documents/dashboard.db with OpenAI."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

from llm_harness.api_client import APIModelClient
from llm_harness.models import LLMRequest


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BASE_DIR / "Documents" / "dashboard.db"


class KPICopilot:
    """
    Specialized Copilot that strictly analyzes business KPIs and operational metrics
    from Documents/dashboard.db using OpenAI (gpt-6-luna).
    """

    def __init__(self, db_path: Optional[Path] = None, llm: Optional[APIModelClient] = None) -> None:
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.llm = llm or APIModelClient()

    def _execute_sql(self, sql: str) -> Dict[str, Any]:
        """Safely executes a SELECT query against dashboard.db."""
        clean_sql = sql.strip().rstrip(";")
        first_token = clean_sql.split()[0].upper() if clean_sql.split() else ""
        if first_token != "SELECT":
            return {"error": "Solo se permiten consultas de lectura (SELECT).", "rows": []}

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(clean_sql + ";")
            rows = [dict(r) for r in cursor.fetchmany(100)]
            conn.close()
            return {"rows": rows, "total_rows": len(rows)}
        except Exception as e:
            return {"error": str(e), "rows": []}

    def _is_kpi_related(self, query: str) -> bool:
        """Determines if the query is strictly within the KPI scope of dashboard.db."""
        kpi_keywords = [
            "kpi", "métrica", "metrica", "cuántos", "cuantos", "promedio", "edad",
            "total", "cantidad", "porcentaje", "más solicitado", "mas solicitado",
            "top", "máximo", "maximo", "mínimo", "minimo", "frecuencia", "género",
            "genero", "hombres", "mujeres", "distribución", "distribucion", "servicio",
            "categoria", "categoría", "cliente", "cuenta", "fecha", "año", "mes",
            "solicitud", "solicitudes", "asistencia", "vial", "hogar", "check up",
            "dental", "funeraria", "jurídica", "juridica", "salud", "grúa", "grua",
            "batería", "bateria", "corriente", "llanta", "plomero", "volumen", "tendencia"
        ]
        q_lower = query.lower()
        return any(kw in q_lower for kw in kpi_keywords)

    def _generate_sql(self, query: str) -> str:
        """Generates SQLite SELECT query using OpenAI gpt-6-luna with strict schema grounding."""
        system_prompt = (
            "Eres un experto analista Text-to-SQL para SQLite especializado en extraer KPIs de negocio.\n"
            "Esquema exacto de la tabla 'dashboard':\n"
            "CREATE TABLE dashboard (\n"
            "  id INTEGER PRIMARY KEY,\n"
            "  cliente TEXT,\n"
            "  edad INTEGER,\n"
            "  genero TEXT,      -- 'F' para Femenino, 'M' para Masculino\n"
            "  num_cuenta TEXT,\n"
            "  categoria TEXT,   -- 'Asistencia vial', 'Check up', 'Membresia dental', 'Asistencia en el hogar', 'Plan salud', 'Asistencia funeraria', 'Asesoría jurídica'\n"
            "  servicio TEXT,    -- 'Grúa', 'Paso de corriente', 'Cambio de llanta', 'Plomero', 'Check up', etc.\n"
            "  fecha TEXT        -- formato 'YYYY-MM-DD'\n"
            ");\n\n"
            "Reglas estrictas:\n"
            "1. Devuelve SOLAMENTE la consulta SQL SELECT para SQLite.\n"
            "2. No agregues bloques de código markdown, comillas triples ni explicaciones.\n"
            "3. Utiliza funciones de agregación (COUNT, ROUND(AVG(edad), 1), MIN, MAX, SUM, GROUP BY, ORDER BY DESC).\n"
            "4. Si se solicitan porcentajes, calcúlalos respecto al total (2999 filas)."
        )

        req = LLMRequest(
            prompt=f"Genera la consulta SQL para responder a esta pregunta de KPI: '{query}'",
            system_prompt=system_prompt,
            max_tokens=200,
            temperature=0.0,
        )

        try:
            res = self.llm.generate(req)
            sql = res.text.strip()
            # Clean possible markdown wrapping
            sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
            sql = re.sub(r"\s*```$", "", sql)
            sql = sql.strip().rstrip(";")
            if sql.upper().startswith("SELECT"):
                return sql + ";"
        except Exception:
            pass

        # Fallback heuristic SQL
        q_lower = query.lower()
        if "edad" in q_lower:
            return "SELECT ROUND(AVG(edad), 1) as edad_promedio, MIN(edad) as edad_minima, MAX(edad) as edad_maxima FROM dashboard;"
        if "genero" in q_lower or "género" in q_lower or "hombres" in q_lower or "mujeres" in q_lower:
            return "SELECT genero, COUNT(*) as total, ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dashboard)), 1) as porcentaje FROM dashboard GROUP BY genero;"
        if "categoria" in q_lower or "categoría" in q_lower:
            return "SELECT categoria, COUNT(*) as total, ROUND(AVG(edad), 1) as edad_promedio FROM dashboard GROUP BY categoria ORDER BY total DESC;"
        return "SELECT servicio, categoria, COUNT(*) as total FROM dashboard GROUP BY servicio, categoria ORDER BY total DESC LIMIT 5;"

    def ask_kpi(self, user_query: str) -> Dict[str, Any]:
        """
        Processes a KPI inquiry strictly against dashboard.db.
        If out of scope, politely explains the boundary.
        """
        start_time = time.perf_counter()

        # Guardrail check: only answer KPIs related to dashboard.db
        if not self._is_kpi_related(user_query):
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            return {
                "query": user_query,
                "is_kpi_query": False,
                "error": None,
                "sql": None,
                "rows": [],
                "total_rows": 0,
                "analysis": (
                    "[AVISO] **Consulta fuera de alcance**: Esta sección está restringida y especializada exclusivamente "
                    "en responder **preguntas de KPIs, métricas cuantitativas y análisis de negocio** de la base de datos "
                    f"`{self.db_path.name}` (2,999 registros de clientes, edades, géneros, categorías de asistencia y fechas).\n\n"
                    "[EJEMPLOS] *Preguntas de KPIs permitidas:*\n"
                    "- ¿Cuál es el promedio de edad de los clientes atendidos por servicio?\n"
                    "- ¿Qué porcentaje de solicitudes corresponden a Asistencia Vial frente a Salud?\n"
                    "- ¿Cuáles son los 5 servicios con mayor volumen de solicitudes?\n"
                    "- ¿Cuál es la distribución de clientes por género en Membresía Dental?"
                ),
                "model_name": self.llm.model_name,
                "latency_ms": round(latency_ms, 2),
                "total_db_records": 2999,
            }

        # Step 1: Generate SQL query
        sql_query = self._generate_sql(user_query)

        # Step 2: Execute query against dashboard.db
        exec_res = self._execute_sql(sql_query)
        rows = exec_res.get("rows", [])
        sql_error = exec_res.get("error")

        if sql_error or not rows:
            # Fallback retry with safe query
            sql_query = "SELECT servicio, categoria, COUNT(*) as total FROM dashboard GROUP BY servicio, categoria ORDER BY total DESC LIMIT 5;"
            exec_res = self._execute_sql(sql_query)
            rows = exec_res.get("rows", [])

        # Step 3: Synthesize Executive KPI Analysis with OpenAI
        rows_str = json.dumps(rows, ensure_ascii=False)
        analysis_prompt = (
            f"Pregunta del KPI: '{user_query}'\n\n"
            f"Consulta SQL ejecutada en SQLite (dashboard.db):\n{sql_query}\n\n"
            f"Registros exactos extraídos ({len(rows)} filas):\n{rows_str}\n\n"
            "Genera un informe analítico ejecutivo conciso y profesional en español con la siguiente estructura:\n"
            "1. **Métrica Principal**: Indica claramente la cifra o KPI clave con números exactos en negrita.\n"
            "2. **Desglose y Distribución**: Explica las proporciones, promedios o volumen de los datos extraídos.\n"
            "3. **Insight de Negocio**: Una recomendación o conclusión operativa clave para la toma de decisiones."
        )

        synth_res = self.llm.generate(
            LLMRequest(
                prompt=analysis_prompt,
                system_prompt="Eres un Chief Data Officer y especialista senior en Inteligencia de Negocios y KPIs para bases de datos relacionales.",
                max_tokens=400,
                temperature=0.2,
            )
        )

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return {
            "query": user_query,
            "is_kpi_query": True,
            "error": None,
            "sql": sql_query,
            "rows": rows,
            "total_rows": len(rows),
            "analysis": synth_res.text,
            "model_name": self.llm.model_name,
            "latency_ms": round(latency_ms, 2),
            "total_db_records": 2999,
        }
