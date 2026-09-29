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

    def get_dashboard_chart_metrics(self) -> Dict[str, Any]:
        """Calculates exact aggregated data for all charts in the visual KPI dashboard."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # 1. Total and Age Stats
        c.execute("SELECT COUNT(*), ROUND(AVG(edad), 1), MIN(edad), MAX(edad) FROM dashboard;")
        total, avg_age, min_age, max_age = c.fetchone()

        # 2. Categories Distribution
        category_colors = {
            "Asistencia vial": "#06b6d4",        # Cyan
            "Check up": "#10b981",               # Emerald
            "Membresia dental": "#a855f7",       # Purple
            "Asistencia en el hogar": "#f59e0b", # Amber
            "Plan salud": "#ec4899",             # Pink
            "Asistencia funeraria": "#64748b",   # Slate
            "Asesoría jurídica": "#38bdf8",      # Light Blue
        }
        c.execute("""
            SELECT categoria, COUNT(*) as total, 
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dashboard), 1) as pct,
                   ROUND(AVG(edad), 1) as avg_age
            FROM dashboard 
            GROUP BY categoria 
            ORDER BY total DESC;
        """)
        categories = []
        for row in c.fetchall():
            cat, cnt, pct, cage = row
            categories.append({
                "categoria": cat,
                "total": cnt,
                "pct": pct,
                "avg_age": cage,
                "color": category_colors.get(cat, "#94a3b8"),
            })

        # 3. Gender Distribution
        c.execute("""
            SELECT genero, COUNT(*) as total,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dashboard), 1) as pct,
                   ROUND(AVG(edad), 1) as avg_age
            FROM dashboard 
            GROUP BY genero
            ORDER BY total DESC;
        """)
        gender = []
        for g, cnt, pct, gage in c.fetchall():
            gender.append({
                "genero": g,
                "label": "Femenino" if g == "F" else "Masculino",
                "total": cnt,
                "pct": pct,
                "avg_age": gage,
                "color": "#ec4899" if g == "F" else "#06b6d4",
            })

        # 4. Top 6 Services
        c.execute("""
            SELECT servicio, categoria, COUNT(*) as total,
                   ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dashboard), 1) as pct
            FROM dashboard 
            GROUP BY servicio, categoria 
            ORDER BY total DESC 
            LIMIT 6;
        """)
        top_services = []
        for srv, cat, cnt, pct in c.fetchall():
            top_services.append({
                "servicio": srv,
                "categoria": cat,
                "total": cnt,
                "pct": pct,
            })

        # 5. Monthly Timeline
        c.execute("""
            SELECT substr(fecha, 1, 7) as ym, COUNT(*) as total
            FROM dashboard 
            GROUP BY ym 
            ORDER BY ym;
        """)
        timeline = [{"month": ym, "total": cnt} for ym, cnt in c.fetchall()]

        conn.close()

        return {
            "summary": {
                "total_records": total,
                "avg_age": avg_age,
                "min_age": min_age,
                "max_age": max_age,
                "top_category": categories[0]["categoria"] if categories else "",
                "top_category_pct": categories[0]["pct"] if categories else 0,
            },
            "categories": categories,
            "gender": gender,
            "top_services": top_services,
            "timeline": timeline,
        }

    def analyze_charts(self, focus: str = "global") -> Dict[str, Any]:
        """Uses OpenAI to synthesize an executive analysis based on the visual charts."""
        metrics = self.get_dashboard_chart_metrics()
        metrics_json = json.dumps(metrics, ensure_ascii=False)

        prompt = (
            f"Actúa como Director de Analítica y BI. A continuación tienes las métricas agregadas del dashboard de clientes (2,999 registros):\n"
            f"{metrics_json}\n\n"
            f"Enfoque solicitado: '{focus}'.\n"
            "Genera un informe analítico ejecutivo conciso con:\n"
            "1. **Hallazgo Principal de los Gráficos**: Qué patrón dominante revelan los datos (ej. concentración en Asistencia Vial con 56.8% y predominancia femenina con 59%).\n"
            "2. **Análisis de Dispersión y Demanda**: Comparativa entre la categoría líder y los servicios de menor volumen.\n"
            "3. **Recomendación Estratégica**: Una acción clara para optimizar recursos, retención o cobertura de servicios."
        )

        res = self.llm.generate(
            LLMRequest(
                prompt=prompt,
                system_prompt="Eres un Senior BI Analyst especializado en presentación gráfica de KPIs y toma de decisiones corporativas.",
                max_tokens=450,
                temperature=0.2,
            )
        )

        return {
            "analysis": res.text,
            "focus": focus,
            "model": self.llm.model_name,
        }
