"""Command Line Interface for the Agentic AI Orchestrator."""

from __future__ import annotations

import argparse
import json
import sys

from orchestration.agent import OrchestratorAgent
from llm_harness.api_client import APIModelClient
from llm_harness.embedded_client import EmbeddedModelClient


def main():
    parser = argparse.ArgumentParser(description="Agentic AI Orchestrator with Tool Use")
    parser.add_argument("query", nargs="?", default="¿Cuál es el servicio más solicitado y cuál es la edad promedio de los clientes?", help="Consulta del usuario")
    parser.add_argument("--model", choices=["api", "embedded"], default="api", help="Modelo de razonamiento (api o embedded)")
    parser.add_argument("--json", action="store_true", help="Salida completa en formato JSON")
    args = parser.parse_args()

    llm = APIModelClient() if args.model == "api" else EmbeddedModelClient()
    agent = OrchestratorAgent(llm=llm)

    print(f"[*] Ejecutando Agente Orquestador con modelo: {llm.model_name}...")
    trace = agent.run(args.query)

    if args.json:
        print(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False))
        return

    print("\n" + "=" * 70)
    print("                 TRAZA DE EJECUCIÓN DEL AGENTE (ReAct)")
    print("=" * 70)
    print(f"Consulta: {trace.query}\n")

    for s in trace.steps:
        print(f"[Paso {s.step_number}]")
        print(f"  PENSAMIENTO : {s.thought}")
        if s.action:
            print(f"  ACCION      : {s.action} con entrada {json.dumps(s.action_input, ensure_ascii=False)}")
            obs_preview = json.dumps(s.observation, ensure_ascii=False)
            if len(obs_preview) > 250:
                obs_preview = obs_preview[:250] + "..."
            print(f"  OBSERVACION : {obs_preview}")
        print("-" * 70)

    print("\n[RESPUESTA FINAL GROUNDED]:")
    print(trace.final_answer)
    print(f"\n[Latencia Total: {trace.total_latency_ms:.1f} ms | Herramientas invocadas: {', '.join(trace.tools_invoked)}]")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
