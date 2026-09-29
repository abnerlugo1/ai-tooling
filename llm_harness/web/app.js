document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const promptInput = document.getElementById("promptInput");
  const temperatureSelect = document.getElementById("temperatureSelect");
  const maxTokensSelect = document.getElementById("maxTokensSelect");
  const toggleRAG = document.getElementById("toggleRAG");
  const btnCompare = document.getElementById("btnCompare");

  const summaryBanner = document.getElementById("summaryBanner");
  const summaryTitle = document.getElementById("summaryTitle");
  const summaryText = document.getElementById("summaryText");
  const kpiLatencyDelta = document.getElementById("kpiLatencyDelta");
  const kpiCostDelta = document.getElementById("kpiCostDelta");

  // API Elements
  const apiTotalLatency = document.getElementById("apiTotalLatency");
  const apiTTFT = document.getElementById("apiTTFT");
  const apiThroughput = document.getElementById("apiThroughput");
  const apiCost = document.getElementById("apiCost");
  const apiMemory = document.getElementById("apiMemory");
  const apiResponseText = document.getElementById("apiResponseText");
  const btnCopyApi = document.getElementById("btnCopyApi");

  // Embedded Elements
  const embeddedTotalLatency = document.getElementById("embeddedTotalLatency");
  const embeddedTTFT = document.getElementById("embeddedTTFT");
  const embeddedThroughput = document.getElementById("embeddedThroughput");
  const embeddedCost = document.getElementById("embeddedCost");
  const embeddedMemory = document.getElementById("embeddedMemory");
  const embeddedResponseText = document.getElementById("embeddedResponseText");
  const btnCopyEmbedded = document.getElementById("btnCopyEmbedded");

  // Presets
  document.getElementById("preset1")?.addEventListener("click", () => {
    promptInput.value = "Explica las diferencias arquitectónicas clave entre invocar un modelo de lenguaje vía API REST en la nube y ejecutar un modelo SLM cuantizado en proceso con llama.cpp.";
    toggleRAG.checked = false;
  });

  document.getElementById("preset2")?.addEventListener("click", () => {
    promptInput.value = "De acuerdo al Capstone 1 de AWS Bedrock y foundation models, ¿cuáles son los criterios de evaluación para comparar Bedrock Knowledge Bases con un despliegue local de llama.cpp?";
    toggleRAG.checked = true;
  });

  document.getElementById("preset3")?.addEventListener("click", () => {
    promptInput.value = "Para una institución médica o bancaria con requisitos de estricta privacidad Air-Gapped y alto volumen de tokens, ¿qué arquitectura es recomendada y por qué?";
    toggleRAG.checked = false;
  });

  // Copy handlers
  btnCopyApi?.addEventListener("click", () => {
    navigator.clipboard.writeText(apiResponseText.textContent);
    btnCopyApi.textContent = "¡Copiado!";
    setTimeout(() => { btnCopyApi.textContent = "Copiar"; }, 1500);
  });

  btnCopyEmbedded?.addEventListener("click", () => {
    navigator.clipboard.writeText(embeddedResponseText.textContent);
    btnCopyEmbedded.textContent = "¡Copiado!";
    setTimeout(() => { btnCopyEmbedded.textContent = "Copiar"; }, 1500);
  });

  // Benchmark Execution
  async function runBenchmark() {
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    btnCompare.disabled = true;
    btnCompare.innerHTML = `
      <svg class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
        <path d="M12 2a10 10 0 0 1 10 10" />
      </svg>
      <span>Evaluando...</span>
    `;

    apiResponseText.textContent = "Invocando endpoint API en la nube...";
    embeddedResponseText.textContent = "Ejecutando inferencia en proceso local...";

    try {
      const resp = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt,
          temperature: parseFloat(temperatureSelect.value),
          max_tokens: parseInt(maxTokensSelect.value, 10),
          use_rag: toggleRAG.checked,
          top_k: 2,
        }),
      });

      if (!resp.ok) {
        throw new Error(`HTTP Error ${resp.status}`);
      }

      const data = await resp.json();

      // Render API Card
      const apiM = data.api.metrics;
      apiTotalLatency.textContent = `${apiM.total_latency_ms.toFixed(1)} ms`;
      apiTTFT.textContent = `${apiM.time_to_first_token_ms.toFixed(1)} ms`;
      apiThroughput.textContent = `${apiM.tokens_per_second.toFixed(1)} tps`;
      apiCost.textContent = `$${apiM.estimated_cost_usd.toFixed(6)}`;
      apiMemory.textContent = `${apiM.memory_rss_mb.toFixed(1)} MB`;
      apiResponseText.textContent = data.api.text;

      // Render Embedded Card
      const embM = data.embedded.metrics;
      embeddedTotalLatency.textContent = `${embM.total_latency_ms.toFixed(1)} ms`;
      embeddedTTFT.textContent = `${embM.time_to_first_token_ms.toFixed(1)} ms`;
      embeddedThroughput.textContent = `${embM.tokens_per_second.toFixed(1)} tps`;
      embeddedCost.textContent = `$${embM.estimated_cost_usd.toFixed(6)}`;
      embeddedMemory.textContent = `${embM.memory_rss_mb.toLocaleString()} MB`;
      embeddedResponseText.textContent = data.embedded.text;

      // Render Summary Banner
      summaryBanner.style.display = "flex";
      summaryTitle.textContent = `Ganador en Velocidad: ${data.winner_latency} | Ganador en Costo: ${data.winner_cost}`;
      summaryText.textContent = data.summary;
      kpiLatencyDelta.textContent = `${Math.abs(data.latency_delta_ms).toFixed(1)} ms`;
      kpiCostDelta.textContent = `$${Math.abs(data.cost_delta_usd).toFixed(6)}`;

    } catch (err) {
      console.error(err);
      apiResponseText.textContent = `Error al ejecutar prueba: ${err.message}`;
      embeddedResponseText.textContent = `Error al ejecutar prueba: ${err.message}`;
    } finally {
      btnCompare.disabled = false;
      btnCompare.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Ejecutar Comparativa</span>
      `;
    }
  }

  btnCompare?.addEventListener("click", runBenchmark);

  // Initial fetch for system stats
  fetch("/api/stats")
    .then(r => r.json())
    .then(stats => {
      const statusText = document.getElementById("statusText");
      if (statusText) statusText.textContent = `Harness Activo (${stats.status})`;
    })
    .catch(() => {});
});
