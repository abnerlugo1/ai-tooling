"""Agentic AI Orchestrator implementing multi-tool ReAct execution and LLM routing."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from llm_harness.api_client import APIModelClient
from llm_harness.base import BaseLLM
from llm_harness.embedded_client import EmbeddedModelClient
from llm_harness.models import ArchitectureType, LLMRequest
from orchestration.tools import ToolRegistry


@dataclass
class AgentStep:
    """Represents a single step in the ReAct orchestration trace."""
    step_number: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[Any] = None


@dataclass
class AgentExecutionTrace:
    """Complete trace of an agent's reasoning, tool invocations and final answer."""
    query: str
    steps: List[AgentStep] = field(default_factory=list)
    final_answer: str = ""
    model_name: str = ""
    architecture: str = ""
    total_latency_ms: float = 0.0
    tools_invoked: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "steps": [
                {
                    "step_number": s.step_number,
                    "thought": s.thought,
                    "action": s.action,
                    "action_input": s.action_input,
                    "observation": s.observation,
                }
                for s in self.steps
            ],
            "final_answer": self.final_answer,
            "model_name": self.model_name,
            "architecture": self.architecture,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "tools_invoked": self.tools_invoked,
        }


class OrchestratorAgent:
    """
    Intelligent Orchestrator Agent that analyzes user queries, plans multi-step execution,
    selects appropriate tools (SQLite Text-to-SQL, Vector Search RAG, Ingestion),
    and synthesizes grounded answers using either API-based or Embedded LLMs.
    """

    def __init__(
        self,
        llm: Optional[BaseLLM] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ) -> None:
        self.llm = llm or APIModelClient()
        self.registry = tool_registry or ToolRegistry()

    def run(self, user_query: str) -> AgentExecutionTrace:
        """Executes the autonomous reasoning loop for a given query."""
        start_time = time.perf_counter()
        trace = AgentExecutionTrace(
            query=user_query,
            model_name=self.llm.model_name,
            architecture=self.llm.architecture.value,
        )

        # 1. Step 1: Query Intent Analysis & Plan
        lower_q = user_query.lower()
        needs_sql = any(k in lower_q for k in [
            "cuántos", "cuantos", "promedio", "edad", "total", "cantidad", "porcentaje",
            "más solicitado", "mas solicitado", "top", "máximo", "mínimo", "frecuencia",
            "género", "genero", "cuenta", "hombres", "mujeres", "distribución"
        ])
        needs_vector = any(k in lower_q for k in [
            "semántica", "semantica", "buscar", "plomero", "llanta", "batería", "corriente",
            "explicar", "capstone", "similitud", "concepto", "caso", "quién", "quien"
        ])
        needs_ingestion = any(k in lower_q for k in ["ingestar", "cargar archivo", "indexar"])

        step_num = 1

        # Execution pathway A: Ingestion requested
        if needs_ingestion:
            thought = "El usuario solicitó indexar o cargar un nuevo archivo. Debo invocar la herramienta de ingesta."
            tool = self.registry.get_tool("ingest_document")
            # Extract file path or default to dashboard .xlsx
            m = re.search(r"['\"]([^'\"]+)['\"]", user_query)
            target_path = m.group(1) if m else "Documents/dashboard .xlsx"

            step = AgentStep(
                step_number=step_num,
                thought=thought,
                action="ingest_document",
                action_input={"source_path": target_path},
            )
            step_num += 1

            if tool:
                step.observation = tool.execute(source_path=target_path)
                trace.tools_invoked.append("ingest_document")
            trace.steps.append(step)

            final_prompt = f"El usuario solicitó: '{user_query}'. El reporte de ingesta fue: {step.observation}. Genera una respuesta clara y profesional resumiendo el resultado."
            llm_res = self.llm.generate(LLMRequest(prompt=final_prompt))
            trace.final_answer = llm_res.text

        # Execution pathway B: Structured / SQL query
        elif needs_sql:
            # Step 1: Thought & SQL Construction
            thought = (
                "La consulta requiere cálculos estructurados, agregaciones o filtros sobre la base de datos de dashboard. "
                "Generaré y ejecutaré una consulta SQL sobre la tabla 'dashboard'."
            )

            # Rule-based / LLM SQL builder
            sql_query = self._generate_sql(user_query)

            step1 = AgentStep(
                step_number=step_num,
                thought=thought,
                action="sql_query",
                action_input={"query": sql_query},
            )
            step_num += 1

            tool = self.registry.get_tool("sql_query")
            if tool:
                obs = tool.execute(query=sql_query)
                step1.observation = obs
                trace.tools_invoked.append("sql_query")
            trace.steps.append(step1)

            # Step 2: Synthesis Thought
            thought_synth = (
                f"Obtuve {step1.observation.get('total_rows', 0)} filas desde SQLite. "
                "Sintetizaré la respuesta final fundamentada con métricas exactas."
            )
            step2 = AgentStep(
                step_number=step_num,
                thought=thought_synth,
            )
            trace.steps.append(step2)

            # Generate final synthesis
            rows_preview = json.dumps(step1.observation.get("rows", []), ensure_ascii=False)
            context = f"SQL Ejecutado: {sql_query}\nResultado SQLite: {rows_preview}"
            synth_prompt = (
                f"Pregunta del usuario: {user_query}\n\n"
                f"Datos obtenidos de la base de datos relacional SQLite:\n{context}\n\n"
                f"Responde de forma clara, directa y fundamentada con los números exactos extraídos de la base de datos."
            )
            llm_res = self.llm.generate(LLMRequest(prompt=synth_prompt))
            trace.final_answer = llm_res.text

        # Execution pathway C: Semantic Search RAG
        else:
            thought = (
                "La consulta es de naturaleza semántica o descriptiva. "
                "Utilizaré la herramienta 'semantic_search' para recuperar los chunks vectoriales más relevantes del Vector Store."
            )
            step1 = AgentStep(
                step_number=step_num,
                thought=thought,
                action="semantic_search",
                action_input={"query": user_query, "top_k": 3, "hybrid": True},
            )
            step_num += 1

            tool = self.registry.get_tool("semantic_search")
            if tool:
                obs = tool.execute(query=user_query, top_k=3, hybrid=True)
                step1.observation = obs
                trace.tools_invoked.append("semantic_search")
            trace.steps.append(step1)

            # Synthesis step
            chunks = [c["content"] for c in step1.observation.get("chunks", [])]
            thought_synth = f"Recuperé {len(chunks)} chunks de contexto semántico. Sintetizando respuesta con el LLM."
            step2 = AgentStep(step_number=step_num, thought=thought_synth)
            trace.steps.append(step2)

            synth_prompt = (
                f"Pregunta: {user_query}\n\n"
                f"Contexto semántico recuperado:\n" + "\n---\n".join(chunks) + "\n\n"
                f"Proporciona una respuesta precisa basada estrictamente en la evidencia recuperada."
            )
            llm_res = self.llm.generate(LLMRequest(prompt=synth_prompt))
            trace.final_answer = llm_res.text

        trace.total_latency_ms = (time.perf_counter() - start_time) * 1000.0
        return trace

    def _generate_sql_with_llm(self, query: str) -> Optional[str]:
        """Uses LLM to dynamically generate SQL query for SQLite dashboard table."""
        prompt = (
            "Eres un motor Text-to-SQL para SQLite.\n"
            "Esquema de la tabla 'dashboard':\n"
            "CREATE TABLE dashboard (\n"
            "  id INTEGER PRIMARY KEY,\n"
            "  cliente TEXT,\n"
            "  servicio TEXT,\n"
            "  edad INTEGER,\n"
            "  genero TEXT,\n"
            "  fecha TEXT,\n"
            "  categoria TEXT,\n"
            "  anio INTEGER\n"
            ");\n\n"
            f"Pregunta del usuario: '{query}'\n\n"
            "Genera SOLAMENTE la consulta SQL SELECT para SQLite sin formato markdown, sin explicaciones ni prefijos.\n"
            "Ejemplo de salida directa: SELECT servicio, COUNT(*) as total FROM dashboard GROUP BY servicio ORDER BY total DESC LIMIT 5;"
        )
        try:
            req = LLMRequest(prompt=prompt, max_tokens=150, temperature=0.0)
            res = self.llm.generate(req)
            candidate = res.text.strip()
            # Clean markdown formatting if present
            candidate = re.sub(r"^```(?:sql)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)
            candidate = candidate.strip()
            # Strip trailing semicolon for uniformity or keep it
            if candidate.upper().startswith("SELECT"):
                return candidate
        except Exception as e:
            print(f"[!] Info: Text-to-SQL with LLM fallback ({e})")
        return None

    def _generate_sql(self, query: str) -> str:
        """Determines appropriate SQL query using LLM if available or rule-based patterns."""
        # Try LLM generation if available and not forced simulation
        if getattr(self.llm, "architecture", None) == ArchitectureType.API:
            # Check if real API is available
            api_key = getattr(self.llm, "api_key", None)
            force_sim = getattr(self.llm, "force_simulation", False)
            if api_key and not force_sim:
                llm_sql = self._generate_sql_with_llm(query)
                if llm_sql:
                    return llm_sql

        q = query.lower()

        if "edad promedio" in q or "promedio de edad" in q:
            if "servicio" in q:
                return "SELECT servicio, COUNT(*) as total, ROUND(AVG(edad), 1) as edad_promedio FROM dashboard GROUP BY servicio ORDER BY total DESC LIMIT 10;"
            elif "categoria" in q or "categoría" in q:
                return "SELECT categoria, COUNT(*) as total, ROUND(AVG(edad), 1) as edad_promedio FROM dashboard GROUP BY categoria ORDER BY total DESC;"
            elif "genero" in q or "género" in q:
                return "SELECT genero, COUNT(*) as total, ROUND(AVG(edad), 1) as edad_promedio FROM dashboard GROUP BY genero;"
            return "SELECT ROUND(AVG(edad), 1) as edad_promedio, MIN(edad) as minima, MAX(edad) as maxima FROM dashboard;"

        if "más solicitado" in q or "mas solicitado" in q or "top" in q:
            if "categoría" in q or "categoria" in q:
                return "SELECT categoria, COUNT(*) as total FROM dashboard GROUP BY categoria ORDER BY total DESC LIMIT 5;"
            return "SELECT servicio, categoria, COUNT(*) as total FROM dashboard GROUP BY servicio, categoria ORDER BY total DESC LIMIT 5;"

        if "género" in q or "genero" in q or "hombres" in q or "mujeres" in q:
            return "SELECT genero, COUNT(*) as total, ROUND((COUNT(*) * 100.0 / (SELECT COUNT(*) FROM dashboard)), 1) as porcentaje FROM dashboard GROUP BY genero;"

        if "asistencia vial" in q:
            return "SELECT servicio, COUNT(*) as total FROM dashboard WHERE categoria = 'Asistencia vial' GROUP BY servicio ORDER BY total DESC;"

        if "plomero" in q:
            return "SELECT id, cliente, edad, genero, fecha FROM dashboard WHERE servicio = 'Plomero' LIMIT 10;"

        # Default fallback: general counts
        return "SELECT categoria, COUNT(*) as total_solicitudes FROM dashboard GROUP BY categoria ORDER BY total_solicitudes DESC LIMIT 5;"
