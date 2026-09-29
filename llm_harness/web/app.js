document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const tabBtnLLM = document.getElementById("tabBtnLLM");
  const tabBtnEmbeddings = document.getElementById("tabBtnEmbeddings");
  const tabBtnOrchestrator = document.getElementById("tabBtnOrchestrator");
  const tabBtnKPI = document.getElementById("tabBtnKPI");
  const viewLLM = document.getElementById("viewLLM");
  const viewEmbeddings = document.getElementById("viewEmbeddings");
  const viewOrchestrator = document.getElementById("viewOrchestrator");
  const viewKPI = document.getElementById("viewKPI");

  function switchTab(tab) {
    [tabBtnLLM, tabBtnEmbeddings, tabBtnOrchestrator, tabBtnKPI].forEach(b => b?.classList.remove("active"));
    [viewLLM, viewEmbeddings, viewOrchestrator, viewKPI].forEach(v => { if (v) v.style.display = "none"; });

    if (tab === "llm") {
      tabBtnLLM?.classList.add("active");
      if (viewLLM) viewLLM.style.display = "block";
    } else if (tab === "embeddings") {
      tabBtnEmbeddings?.classList.add("active");
      if (viewEmbeddings) viewEmbeddings.style.display = "block";
      loadClusterMap();
      if (!document.getElementById("vecActive").textContent || document.getElementById("vecActive").textContent === "--") {
        generateVector();
      }
    } else if (tab === "orchestrator") {
      tabBtnOrchestrator?.classList.add("active");
      if (viewOrchestrator) viewOrchestrator.style.display = "block";
    } else if (tab === "kpi") {
      tabBtnKPI?.classList.add("active");
      if (viewKPI) viewKPI.style.display = "block";
      loadVisualKPIDashboard();
    }
  }

  tabBtnLLM?.addEventListener("click", () => switchTab("llm"));
  tabBtnEmbeddings?.addEventListener("click", () => switchTab("embeddings"));
  tabBtnOrchestrator?.addEventListener("click", () => switchTab("orchestrator"));
  tabBtnKPI?.addEventListener("click", () => switchTab("kpi"));

  // ==========================================
  // TAB 1: LLM COMPARISON
  // ==========================================
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

  const apiTotalLatency = document.getElementById("apiTotalLatency");
  const apiTTFT = document.getElementById("apiTTFT");
  const apiThroughput = document.getElementById("apiThroughput");
  const apiCost = document.getElementById("apiCost");
  const apiMemory = document.getElementById("apiMemory");
  const apiResponseText = document.getElementById("apiResponseText");
  const btnCopyApi = document.getElementById("btnCopyApi");

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

  // ==========================================
  // TAB 2: EMBEDDINGS & VECTOR EXPLORER
  // ==========================================

  // 1. Vector Generator
  const embedInput = document.getElementById("embedInput");
  const btnGenVector = document.getElementById("btnGenVector");
  const vecDim = document.getElementById("vecDim");
  const vecNorm = document.getElementById("vecNorm");
  const vecActive = document.getElementById("vecActive");
  const vectorHeatmap = document.getElementById("vectorHeatmap");
  const slotsContainer = document.getElementById("slotsContainer");

  async function generateVector() {
    const text = embedInput.value.trim();
    if (!text) return;

    btnGenVector.disabled = true;
    try {
      const res = await fetch("/api/embeddings/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();

      vecDim.textContent = data.dimension;
      vecNorm.textContent = data.norm.toFixed(5);
      vecActive.textContent = `${data.non_zero_dimensions} / ${data.dimension}`;

      // Render Heatmap (showing first 64 sample vector slots)
      vectorHeatmap.innerHTML = "";
      const maxVal = Math.max(...data.sample_vector.map(Math.abs)) || 1.0;
      data.sample_vector.forEach((val, idx) => {
        const block = document.createElement("div");
        block.className = "heat-block";
        const normalized = Math.min(1.0, Math.abs(val) / maxVal);

        if (val > 0) {
          block.style.backgroundColor = `rgba(16, 185, 129, ${0.15 + normalized * 0.85})`;
        } else if (val < 0) {
          block.style.backgroundColor = `rgba(244, 63, 94, ${0.15 + normalized * 0.85})`;
        } else {
          block.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
        }
        block.title = `Slot #${idx}: ${val.toFixed(4)}`;
        vectorHeatmap.appendChild(block);
      });

      // Render top activated slots
      slotsContainer.innerHTML = "";
      data.top_activated.slice(0, 10).forEach(slot => {
        const pill = document.createElement("span");
        pill.className = "slot-pill";
        pill.textContent = `Dim #${slot.index}: ${slot.value > 0 ? "+" : ""}${slot.value}`;
        slotsContainer.appendChild(pill);
      });

    } catch (e) {
      console.error(e);
    } finally {
      btnGenVector.disabled = false;
    }
  }

  btnGenVector?.addEventListener("click", generateVector);

  // 2. Cosine Similarity Calculator
  const textAInput = document.getElementById("textAInput");
  const textBInput = document.getElementById("textBInput");
  const btnCalcSimilarity = document.getElementById("btnCalcSimilarity");
  const simNumber = document.getElementById("simNumber");
  const simScoreRaw = document.getElementById("simScoreRaw");
  const simRating = document.getElementById("simRating");
  const simResultBox = document.getElementById("simResultBox");

  document.getElementById("pairPreset1")?.addEventListener("click", () => {
    textAInput.value = "Servicio de grúa para remolque de automóvil averiado";
    textBInput.value = "Auxilio vial mecánico y asistencia técnica en carretera";
    calcSimilarity();
  });

  document.getElementById("pairPreset2")?.addEventListener("click", () => {
    textAInput.value = "Consulta médica preventiva y paquete de check up general";
    textBInput.value = "Examen clínico de laboratorio y evaluación de salud";
    calcSimilarity();
  });

  document.getElementById("pairPreset3")?.addEventListener("click", () => {
    textAInput.value = "Reparación de fuga de agua y fontanería en domicilio";
    textBInput.value = "Inversión bursátil en fondos indexados y criptomonedas";
    calcSimilarity();
  });

  async function calcSimilarity() {
    const textA = textAInput.value.trim();
    const textB = textBInput.value.trim();
    if (!textA || !textB) return;

    btnCalcSimilarity.disabled = true;
    try {
      const res = await fetch("/api/embeddings/similarity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text_a: textA, text_b: textB }),
      });
      const data = await res.json();

      simNumber.textContent = `${data.similarity_percentage.toFixed(1)}%`;
      simScoreRaw.textContent = `Similitud Coseno: ${data.cosine_similarity.toFixed(4)}`;
      simRating.textContent = data.rating;

      // Update circle gradient
      const circle = simResultBox.querySelector(".sim-score-circle");
      if (circle) {
        circle.style.setProperty("--sim-pct", data.similarity_percentage);
      }
    } catch (e) {
      console.error(e);
    } finally {
      btnCalcSimilarity.disabled = false;
    }
  }

  btnCalcSimilarity?.addEventListener("click", calcSimilarity);

  // 3. Cluster Scatter Plot
  const scatterSvg = document.getElementById("scatterSvg");
  const scatterTooltip = document.getElementById("scatterTooltip");
  const btnRefreshClusters = document.getElementById("btnRefreshClusters");

  async function loadClusterMap() {
    try {
      const res = await fetch("/api/vector/clusters");
      const data = await res.json();

      // Clean old circles
      const oldCircles = scatterSvg.querySelectorAll(".scatter-point");
      oldCircles.forEach(c => c.remove());

      data.points.forEach(pt => {
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        const cx = (pt.x / 100.0) * 1000;
        const cy = (pt.y / 100.0) * 340;

        circle.setAttribute("cx", cx);
        circle.setAttribute("cy", cy);
        circle.setAttribute("r", "5.5");
        circle.setAttribute("fill", pt.color);
        circle.setAttribute("opacity", "0.75");
        circle.setAttribute("class", "scatter-point");

        // Hover event for tooltip
        circle.addEventListener("mouseenter", (e) => {
          scatterTooltip.style.display = "block";
          scatterTooltip.innerHTML = `
            <strong>${pt.cliente}</strong><br/>
            <span>Categoría: ${pt.categoria}</span><br/>
            <span>Servicio: ${pt.servicio}</span><br/>
            <small style="color:#94a3b8">Chunk ID: ${pt.id}</small>
          `;
          const rect = scatterSvg.getBoundingClientRect();
          scatterTooltip.style.left = `${(cx / 1000) * rect.width + 12}px`;
          scatterTooltip.style.top = `${(cy / 340) * rect.height - 20}px`;
        });

        circle.addEventListener("mouseleave", () => {
          scatterTooltip.style.display = "none";
        });

        scatterSvg.appendChild(circle);
      });
    } catch (e) {
      console.error("Cluster map load error:", e);
    }
  }

  btnRefreshClusters?.addEventListener("click", loadClusterMap);

  // 4. Live Vector Search against .vector_store.db
  const vectorSearchInput = document.getElementById("vectorSearchInput");
  const vectorHybridToggle = document.getElementById("vectorHybridToggle");
  const vectorTopK = document.getElementById("vectorTopK");
  const btnVectorSearch = document.getElementById("btnVectorSearch");
  const vectorResultsContainer = document.getElementById("vectorResultsContainer");

  async function runVectorSearch() {
    const query = vectorSearchInput.value.trim();
    if (!query) return;

    btnVectorSearch.disabled = true;
    btnVectorSearch.textContent = "Buscando...";
    vectorResultsContainer.innerHTML = "<div class='empty-state'>Buscando en la base vectorial...</div>";

    try {
      const res = await fetch("/api/vector/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          top_k: parseInt(vectorTopK.value, 10),
          hybrid: vectorHybridToggle.checked,
        }),
      });
      const data = await res.json();

      if (!data.results || data.results.length === 0) {
        vectorResultsContainer.innerHTML = "<div class='empty-state'>No se encontraron chunks coincidentes.</div>";
        return;
      }

      vectorResultsContainer.innerHTML = "";
      data.results.forEach(r => {
        const card = document.createElement("div");
        card.className = "v-result-card";

        const meta = r.metadata || {};
        const metaTags = [];
        if (meta.cliente) metaTags.push(`<span class="v-meta-tag">Cliente: ${meta.cliente}</span>`);
        if (meta.categoria) metaTags.push(`<span class="v-meta-tag">Cat: ${meta.categoria}</span>`);
        if (meta.servicio) metaTags.push(`<span class="v-meta-tag">Servicio: ${meta.servicio}</span>`);
        if (meta.Fecha) metaTags.push(`<span class="v-meta-tag">Fecha: ${meta.Fecha}</span>`);
        if (meta.is_summary) metaTags.push(`<span class="v-meta-tag" style="color:#06b6d4;">Resumen Analítico</span>`);

        card.innerHTML = `
          <div class="v-result-header">
            <span class="v-result-rank">#${r.rank} - Score: ${r.score.toFixed(4)}</span>
            <span class="v-score-badge">~${r.tokens} tokens</span>
          </div>
          <div class="v-result-meta">${metaTags.join(" ")}</div>
          <pre class="v-result-content">${r.content}</pre>
        `;
        vectorResultsContainer.appendChild(card);
      });

    } catch (e) {
      console.error(e);
      vectorResultsContainer.innerHTML = `<div class='empty-state text-amber'>Error: ${e.message}</div>`;
    } finally {
      btnVectorSearch.disabled = false;
      btnVectorSearch.textContent = "Buscar";
    }
  }

  btnVectorSearch?.addEventListener("click", runVectorSearch);
  vectorSearchInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runVectorSearch();
  });

  // ==========================================
  // TAB 3: AGENTIC AI ORCHESTRATOR (ReAct)
  // ==========================================
  const orchQueryInput = document.getElementById("orchQueryInput");
  const orchModelSelect = document.getElementById("orchModelSelect");
  const btnRunOrchestrator = document.getElementById("btnRunOrchestrator");
  const orchTraceSection = document.getElementById("orchTraceSection");
  const orchTraceSubtitle = document.getElementById("orchTraceSubtitle");
  const toolsInvokedContainer = document.getElementById("toolsInvokedContainer");
  const reactTimeline = document.getElementById("reactTimeline");
  const orchFinalAnswerText = document.getElementById("orchFinalAnswerText");
  const btnCopyOrchAnswer = document.getElementById("btnCopyOrchAnswer");

  document.getElementById("orchPreset1")?.addEventListener("click", () => {
    orchQueryInput.value = "¿Cuál es el servicio más solicitado en el dashboard y cuál es la edad promedio de los clientes que lo contrataron?";
  });
  document.getElementById("orchPreset2")?.addEventListener("click", () => {
    orchQueryInput.value = "Busca registros de clientes atendidos por emergencias de plomería o fugas de agua en su hogar";
  });
  document.getElementById("orchPreset3")?.addEventListener("click", () => {
    orchQueryInput.value = "¿Cuál es el porcentaje y cantidad total de solicitudes realizadas por mujeres frente a hombres?";
  });
  document.getElementById("orchPreset4")?.addEventListener("click", () => {
    orchQueryInput.value = "¿Cuántas solicitudes de Asistencia vial se han realizado y qué servicios específicos incluye?";
  });

  btnCopyOrchAnswer?.addEventListener("click", () => {
    navigator.clipboard.writeText(orchFinalAnswerText.textContent);
    btnCopyOrchAnswer.textContent = "¡Copiado!";
    setTimeout(() => { btnCopyOrchAnswer.textContent = "Copiar"; }, 1500);
  });

  async function runOrchestratorAgent() {
    const query = orchQueryInput.value.trim();
    if (!query) return;

    btnRunOrchestrator.disabled = true;
    btnRunOrchestrator.innerHTML = `
      <svg class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
        <path d="M12 2a10 10 0 0 1 10 10" />
      </svg>
      <span>Orquestando Agente...</span>
    `;

    orchTraceSection.style.display = "block";
    reactTimeline.innerHTML = "<div class='empty-state'>El agente está analizando el objetivo y planificando herramientas...</div>";
    orchFinalAnswerText.textContent = "Sintetizando...";

    try {
      const resp = await fetch("/api/orchestration/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          model: orchModelSelect.value,
        }),
      });

      if (!resp.ok) throw new Error(`HTTP Error ${resp.status}`);
      const trace = await resp.json();

      // Render Subtitle and Tools
      orchTraceSubtitle.textContent = `Modelo: ${trace.model_name} (${trace.architecture}) | Latencia: ${trace.total_latency_ms.toFixed(1)} ms`;

      toolsInvokedContainer.innerHTML = "";
      trace.tools_invoked.forEach(tool => {
        const badge = document.createElement("span");
        badge.className = "tool-badge-pill";
        badge.innerHTML = `🛠 ${tool}`;
        toolsInvokedContainer.appendChild(badge);
      });

      // Render Timeline Steps
      reactTimeline.innerHTML = "";
      trace.steps.forEach(step => {
        const card = document.createElement("div");
        card.className = "react-step-card";

        let actionHtml = "";
        if (step.action) {
          actionHtml = `
            <div class="step-action-box">
              <span class="step-action-label">Acción: ${step.action}</span>
              <pre class="step-action-code">${JSON.stringify(step.action_input, null, 2)}</pre>
            </div>
          `;
        }

        let obsHtml = "";
        if (step.observation) {
          obsHtml = `
            <div class="step-obs-box">
              <span class="step-obs-label">Observación de Datos:</span>
              <pre class="step-obs-code">${JSON.stringify(step.observation, null, 2)}</pre>
            </div>
          `;
        }

        card.innerHTML = `
          <div class="step-card-header">
            <span class="step-num-pill">Paso #${step.step_number}</span>
          </div>
          <div class="step-thought"><strong>💭 Pensamiento:</strong> ${step.thought}</div>
          ${actionHtml}
          ${obsHtml}
        `;
        reactTimeline.appendChild(card);
      });

      // Render Final Answer
      orchFinalAnswerText.textContent = trace.final_answer;

    } catch (err) {
      console.error(err);
      orchFinalAnswerText.textContent = `Error durante la orquestación: ${err.message}`;
    } finally {
      btnRunOrchestrator.disabled = false;
      btnRunOrchestrator.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Ejecutar Agente Orquestador</span>
      `;
    }
  }

  btnRunOrchestrator?.addEventListener("click", runOrchestratorAgent);

  // Initial fetch for system stats
  fetch("/api/stats")
    .then(r => r.json())
    .then(stats => {
      const statusText = document.getElementById("statusText");
      if (statusText) {
        if (stats.openai_active) {
          statusText.textContent = `OpenAI Activo (${stats.model_name || "gpt-6-luna"})`;
        } else {
          statusText.textContent = `Harness Activo (${stats.status})`;
        }
      }
      const apiModelName = document.getElementById("apiModelName");
      if (apiModelName && stats.api_model) {
        apiModelName.textContent = stats.api_model;
      }
      const badgeDbCount = document.getElementById("badgeDbCount");
      if (badgeDbCount && stats.vector_store) {
        badgeDbCount.textContent = `${stats.vector_store.total_chunks.toLocaleString()} Chunks Activos`;
      }
      const repApiProvider = document.getElementById("repApiProvider");
      if (repApiProvider && stats.api_model) {
        repApiProvider.textContent = stats.api_model;
      }
      const repVectorStats = document.getElementById("repVectorStats");
      if (repVectorStats && stats.vector_store) {
        repVectorStats.textContent = `${stats.vector_store.total_chunks.toLocaleString()} Chunks Activos`;
      }
    })
    .catch(() => {});

  // ==========================================
  // EXECUTIVE REPORT MODAL LOGIC
  // ==========================================
  const btnOpenReport = document.getElementById("btnOpenReport");
  const reportModalOverlay = document.getElementById("reportModalOverlay");
  const btnCloseReport = document.getElementById("btnCloseReport");
  const btnCloseReport2 = document.getElementById("btnCloseReport2");
  const btnPrintReport = document.getElementById("btnPrintReport");
  const repLastQuery = document.getElementById("repLastQuery");
  const repAgentAnswer = document.getElementById("repAgentAnswer");

  btnOpenReport?.addEventListener("click", () => {
    // Populate latest query / answer from Agent tab if available
    const orchQuery = document.getElementById("orchQueryInput");
    const orchAnswer = document.getElementById("orchFinalAnswerText");
    if (orchQuery && orchQuery.value.trim() && repLastQuery) {
      repLastQuery.textContent = orchQuery.value.trim();
    }
    if (orchAnswer && orchAnswer.textContent && orchAnswer.textContent !== "--" && repAgentAnswer) {
      repAgentAnswer.textContent = orchAnswer.textContent;
    }
    if (reportModalOverlay) reportModalOverlay.style.display = "flex";
  });

  function closeReportModal() {
    if (reportModalOverlay) reportModalOverlay.style.display = "none";
  }

  btnCloseReport?.addEventListener("click", closeReportModal);
  btnCloseReport2?.addEventListener("click", closeReportModal);
  reportModalOverlay?.addEventListener("click", (e) => {
    if (e.target === reportModalOverlay) closeReportModal();
  });

  btnPrintReport?.addEventListener("click", () => {
    window.print();
  });

  // ==========================================
  // TAB 4: DEDICATED VISUAL KPI DASHBOARD (dashboard.db)
  // ==========================================
  let kpiMetricsCache = null;
  let currentKpiFocus = "global";

  const btnRefreshCharts = document.getElementById("btnRefreshCharts");
  const scTotalRecords = document.getElementById("scTotalRecords");
  const scTopCategory = document.getElementById("scTopCategory");
  const scTopCategoryPct = document.getElementById("scTopCategoryPct");
  const scAvgAge = document.getElementById("scAvgAge");
  const scAgeRange = document.getElementById("scAgeRange");
  const scGenderRatio = document.getElementById("scGenderRatio");

  const chartCategoriesContainer = document.getElementById("chartCategoriesContainer");
  const chartGenderContainer = document.getElementById("chartGenderContainer");
  const chartTopServicesContainer = document.getElementById("chartTopServicesContainer");
  const chartTimelineContainer = document.getElementById("chartTimelineContainer");
  const chartAnalysisText = document.getElementById("chartAnalysisText");
  const btnCopyChartAnalysis = document.getElementById("btnCopyChartAnalysis");

  // Focus Pills Setup
  const focusPillButtons = [
    { btn: document.getElementById("btnFocusGlobal"), focus: "global" },
    { btn: document.getElementById("btnFocusCategories"), focus: "categories" },
    { btn: document.getElementById("btnFocusDemographics"), focus: "demographics" },
    { btn: document.getElementById("btnFocusServices"), focus: "services" },
  ];

  focusPillButtons.forEach(({ btn, focus }) => {
    btn?.addEventListener("click", () => {
      focusPillButtons.forEach(item => item.btn?.classList.remove("active"));
      btn.classList.add("active");
      currentKpiFocus = focus;
      loadChartAnalysis(focus);
    });
  });

  btnCopyChartAnalysis?.addEventListener("click", () => {
    if (chartAnalysisText) {
      navigator.clipboard.writeText(chartAnalysisText.textContent);
      btnCopyChartAnalysis.textContent = "¡Copiado!";
      setTimeout(() => { btnCopyChartAnalysis.textContent = "Copiar Análisis"; }, 1500);
    }
  });

  btnRefreshCharts?.addEventListener("click", () => {
    loadVisualKPIDashboard(true);
  });

  // Render Category Horizontal Bars
  function renderCategoriesChart(categories) {
    if (!chartCategoriesContainer) return;
    if (!categories || categories.length === 0) {
      chartCategoriesContainer.innerHTML = "<div class='empty-state'>Sin datos de categorías.</div>";
      return;
    }

    let html = "";
    categories.forEach(cat => {
      html += `
        <div class="cat-bar-item">
          <div class="cat-bar-info">
            <span class="cat-bar-name">${cat.categoria}</span>
            <span class="cat-bar-meta"><strong>${cat.total.toLocaleString()}</strong> (${cat.pct}%) · Edad prom: ${cat.avg_age} años</span>
          </div>
          <div class="cat-bar-track">
            <div class="cat-bar-fill" style="width: ${cat.pct}%; background: ${cat.color}; box-shadow: 0 0 10px ${cat.color}66;"></div>
          </div>
        </div>
      `;
    });
    chartCategoriesContainer.innerHTML = html;
  }

  // Render SVG Gender Donut Chart
  function renderGenderDonut(gender, totalRecords) {
    if (!chartGenderContainer) return;
    if (!gender || gender.length === 0) {
      chartGenderContainer.innerHTML = "<div class='empty-state'>Sin datos de demografía.</div>";
      return;
    }

    const fem = gender.find(g => g.genero === "F") || { total: 0, pct: 50, avg_age: 40 };
    const masc = gender.find(g => g.genero === "M") || { total: 0, pct: 50, avg_age: 40 };

    // Donut SVG parameters (r = 52, perimeter = 2 * PI * 52 = 326.72)
    const perimeter = 326.72;
    const femDash = ((fem.pct / 100.0) * perimeter).toFixed(2);
    const mascDash = ((masc.pct / 100.0) * perimeter).toFixed(2);

    const html = `
      <div class="donut-svg-wrapper">
        <svg viewBox="0 0 160 160" width="160" height="160" style="transform: rotate(-90deg);">
          <!-- Background track -->
          <circle cx="80" cy="80" r="52" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="20" />
          <!-- Male segment (Cyan) -->
          <circle cx="80" cy="80" r="52" fill="none" stroke="#06b6d4" stroke-width="20"
                  stroke-dasharray="${mascDash} ${perimeter}" stroke-dashoffset="0"
                  stroke-linecap="butt" style="transition: stroke-dasharray 1s ease;" />
          <!-- Female segment (Pink) -->
          <circle cx="80" cy="80" r="52" fill="none" stroke="#ec4899" stroke-width="20"
                  stroke-dasharray="${femDash} ${perimeter}" stroke-dashoffset="-${mascDash}"
                  stroke-linecap="butt" style="transition: stroke-dasharray 1s ease;" />
        </svg>
        <div class="donut-center-text">
          <span class="donut-center-val">${totalRecords.toLocaleString()}</span>
          <span class="donut-center-sub">Total Clientes</span>
        </div>
      </div>
      <div class="donut-legend">
        <div class="donut-legend-item">
          <span class="donut-dot" style="background: #ec4899; box-shadow: 0 0 8px rgba(236,72,153,0.5);"></span>
          <div>
            <div><strong>Femenino:</strong> ${fem.total.toLocaleString()} (${fem.pct}%)</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">Edad promedio: ${fem.avg_age} años</div>
          </div>
        </div>
        <div class="donut-legend-item">
          <span class="donut-dot" style="background: #06b6d4; box-shadow: 0 0 8px rgba(6,182,212,0.5);"></span>
          <div>
            <div><strong>Masculino:</strong> ${masc.total.toLocaleString()} (${masc.pct}%)</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">Edad promedio: ${masc.avg_age} años</div>
          </div>
        </div>
      </div>
    `;
    chartGenderContainer.innerHTML = html;
  }

  // Render Top 6 Services Ranking
  function renderTopServices(topServices) {
    if (!chartTopServicesContainer) return;
    if (!topServices || topServices.length === 0) {
      chartTopServicesContainer.innerHTML = "<div class='empty-state'>Sin datos de servicios.</div>";
      return;
    }

    let html = "";
    topServices.forEach((srv, idx) => {
      html += `
        <div class="ranking-item">
          <span class="ranking-pill">#${idx + 1}</span>
          <div class="ranking-name">
            <strong>${srv.servicio}</strong>
            <span class="ranking-cat">(${srv.categoria})</span>
          </div>
          <span class="ranking-val">${srv.total.toLocaleString()}</span>
          <span class="ranking-pct">${srv.pct}%</span>
        </div>
      `;
    });
    chartTopServicesContainer.innerHTML = html;
  }

  // Render Monthly Timeline Bar Chart (Pure SVG)
  function renderTimelineChart(timeline) {
    if (!chartTimelineContainer) return;
    if (!timeline || timeline.length === 0) {
      chartTimelineContainer.innerHTML = "<div class='empty-state'>Sin datos temporales.</div>";
      return;
    }

    const maxVal = Math.max(...timeline.map(t => t.total), 300);
    const svgWidth = 560;
    const svgHeight = 210;
    const barWidth = 26;
    const chartBottom = 165;
    const maxBarHeight = 120;

    let barsSvg = "";
    const stepX = (svgWidth - 60) / timeline.length;

    timeline.forEach((item, i) => {
      const x = 30 + (i * stepX);
      const h = Math.round((item.total / maxVal) * maxBarHeight);
      const y = chartBottom - h;
      const displayMonth = item.month.replace("20", ""); // e.g. "24-11"

      barsSvg += `
        <g class="timeline-bar-group">
          <!-- Count text on top of bar -->
          <text x="${x + (barWidth / 2)}" y="${y - 6}" font-size="10" fill="#38bdf8" text-anchor="middle" font-weight="600">
            ${item.total}
          </text>
          <!-- Bar column with glow -->
          <rect x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="4" fill="url(#kpiBarGradient)"
                opacity="0.88" style="transition: height 0.6s ease, y 0.6s ease; cursor: pointer;">
            <title>Mes: ${item.month} | Solicitudes: ${item.total}</title>
          </rect>
          <!-- Month label at bottom -->
          <text x="${x + (barWidth / 2)}" y="${chartBottom + 18}" font-size="10" fill="#94a3b8" text-anchor="middle">
            ${displayMonth}
          </text>
        </g>
      `;
    });

    const svg = `
      <svg viewBox="0 0 ${svgWidth} ${svgHeight}" width="100%" height="100%" style="overflow: visible;">
        <defs>
          <linearGradient id="kpiBarGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" />
            <stop offset="100%" stop-color="#0284c7" />
          </linearGradient>
        </defs>
        <!-- Horizontal grid line -->
        <line x1="20" y1="${chartBottom}" x2="${svgWidth - 10}" y2="${chartBottom}" stroke="rgba(255,255,255,0.12)" stroke-width="1" />
        <line x1="20" y1="${chartBottom - 60}" x2="${svgWidth - 10}" y2="${chartBottom - 60}" stroke="rgba(255,255,255,0.05)" stroke-dasharray="4" />
        <line x1="20" y1="${chartBottom - 120}" x2="${svgWidth - 10}" y2="${chartBottom - 120}" stroke="rgba(255,255,255,0.05)" stroke-dasharray="4" />
        ${barsSvg}
      </svg>
    `;

    chartTimelineContainer.innerHTML = svg;
  }

  // Load Executive Analysis from OpenAI based on the Charts
  async function loadChartAnalysis(focus = "global") {
    if (!chartAnalysisText) return;
    chartAnalysisText.innerHTML = `
      <div class="loading-state" style="display:flex; align-items:center; gap:8px;">
        <svg class="spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
          <path d="M12 2a10 10 0 0 1 10 10" />
        </svg>
        <span>Generando análisis estratégico con OpenAI gpt-6-luna (enfoque: ${focus})...</span>
      </div>
    `;

    try {
      const resp = await fetch("/api/kpi/analyze-charts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ focus }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      chartAnalysisText.textContent = data.analysis;
    } catch (err) {
      console.error(err);
      chartAnalysisText.textContent = `Error al sintetizar análisis estratégico con OpenAI: ${err.message}`;
    }
  }

  // Main KPI Dashboard Loader
  async function loadVisualKPIDashboard(forceRefresh = false) {
    if (kpiMetricsCache && !forceRefresh) {
      return;
    }

    if (btnRefreshCharts) {
      btnRefreshCharts.disabled = true;
    }

    try {
      const res = await fetch("/api/kpi/dashboard-metrics");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      kpiMetricsCache = data;

      // 1. Update Scorecards
      if (scTotalRecords) scTotalRecords.textContent = (data.summary.total_records || 2999).toLocaleString();
      if (scTopCategory) scTopCategory.textContent = data.summary.top_category || "Asistencia vial";
      if (scTopCategoryPct) {
        const topCat = data.categories?.[0];
        scTopCategoryPct.textContent = topCat ? `${topCat.total.toLocaleString()} (${topCat.pct}% del total)` : "--";
      }
      if (scAvgAge) scAvgAge.textContent = `${data.summary.avg_age || 40.2} años`;
      if (scAgeRange) scAgeRange.textContent = `Rango: ${data.summary.min_age || 18} a ${data.summary.max_age || 65} años`;
      if (scGenderRatio && data.gender && data.gender.length >= 2) {
        const fem = data.gender.find(g => g.genero === "F") || { pct: 59 };
        const masc = data.gender.find(g => g.genero === "M") || { pct: 41 };
        scGenderRatio.textContent = `${fem.pct}% F / ${masc.pct}% M`;
      }

      // 2. Render 4 Core Interactive Charts
      renderCategoriesChart(data.categories);
      renderGenderDonut(data.gender, data.summary.total_records);
      renderTopServices(data.top_services);
      renderTimelineChart(data.timeline);

      // 3. Load OpenAI Strategic Analysis
      loadChartAnalysis(currentKpiFocus);

    } catch (e) {
      console.error("Error loading KPI dashboard metrics:", e);
      if (chartCategoriesContainer) {
        chartCategoriesContainer.innerHTML = `<div class='empty-state text-amber'>Error al cargar métricas: ${e.message}</div>`;
      }
    } finally {
      if (btnRefreshCharts) {
        btnRefreshCharts.disabled = false;
      }
    }
  }

  // ==========================================
  // KPI DATABASE PROMPT (Q&A con OpenAI sobre dashboard.db)
  // ==========================================
  const kpiPromptInput = document.getElementById("kpiPromptInput");
  const btnSubmitKpiPrompt = document.getElementById("btnSubmitKpiPrompt");
  const kpiPromptResultArea = document.getElementById("kpiPromptResultArea");
  const kpiPromptGuardAlert = document.getElementById("kpiPromptGuardAlert");
  const kpiPromptGuardText = document.getElementById("kpiPromptGuardText");
  const kpiPromptResponseContent = document.getElementById("kpiPromptResponseContent");
  const kpiPromptModelBadge = document.getElementById("kpiPromptModelBadge");
  const kpiPromptLatency = document.getElementById("kpiPromptLatency");
  const kpiPromptRowCount = document.getElementById("kpiPromptRowCount");
  const kpiPromptAnswerText = document.getElementById("kpiPromptAnswerText");
  const kpiPromptSqlCode = document.getElementById("kpiPromptSqlCode");
  const kpiPromptTableWrapper = document.getElementById("kpiPromptTableWrapper");
  const btnCopyPromptAnswer = document.getElementById("btnCopyPromptAnswer");

  const tabKpiDetailsTable = document.getElementById("tabKpiDetailsTable");
  const tabKpiDetailsSql = document.getElementById("tabKpiDetailsSql");
  const kpiDetailsTableView = document.getElementById("kpiDetailsTableView");
  const kpiDetailsSqlView = document.getElementById("kpiDetailsSqlView");

  // Presets
  document.getElementById("kpiPromptPreset1")?.addEventListener("click", () => {
    if (kpiPromptInput) kpiPromptInput.value = "¿Cuál es la edad promedio de los clientes desglosada por cada categoría de servicio?";
  });
  document.getElementById("kpiPromptPreset2")?.addEventListener("click", () => {
    if (kpiPromptInput) kpiPromptInput.value = "¿Cuáles son los 5 servicios más solicitados en total y cuántas solicitudes tiene cada uno?";
  });
  document.getElementById("kpiPromptPreset3")?.addEventListener("click", () => {
    if (kpiPromptInput) kpiPromptInput.value = "¿Cuál es el porcentaje y cantidad total de clientes por género en la base de datos?";
  });
  document.getElementById("kpiPromptPreset4")?.addEventListener("click", () => {
    if (kpiPromptInput) kpiPromptInput.value = "¿Cuántas solicitudes de Asistencia vial se han realizado por cada mes registrado?";
  });

  // Toggle between Table and SQL code
  tabKpiDetailsTable?.addEventListener("click", () => {
    tabKpiDetailsTable.classList.add("active");
    tabKpiDetailsSql?.classList.remove("active");
    if (kpiDetailsTableView) kpiDetailsTableView.style.display = "block";
    if (kpiDetailsSqlView) kpiDetailsSqlView.style.display = "none";
  });

  tabKpiDetailsSql?.addEventListener("click", () => {
    tabKpiDetailsSql.classList.add("active");
    tabKpiDetailsTable?.classList.remove("active");
    if (kpiDetailsTableView) kpiDetailsTableView.style.display = "none";
    if (kpiDetailsSqlView) kpiDetailsSqlView.style.display = "block";
  });

  btnCopyPromptAnswer?.addEventListener("click", () => {
    if (kpiPromptAnswerText) {
      navigator.clipboard.writeText(kpiPromptAnswerText.textContent);
      btnCopyPromptAnswer.textContent = "¡Copiado!";
      setTimeout(() => { btnCopyPromptAnswer.textContent = "Copiar Respuesta"; }, 1500);
    }
  });

  async function executeKpiPromptQuery() {
    const query = kpiPromptInput?.value.trim();
    if (!query) return;

    btnSubmitKpiPrompt.disabled = true;
    btnSubmitKpiPrompt.innerHTML = `
      <svg class="spinner" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" stroke-opacity="0.25"/>
        <path d="M12 2a10 10 0 0 1 10 10" />
      </svg>
      <span>Consultando con OpenAI...</span>
    `;

    if (kpiPromptResultArea) kpiPromptResultArea.style.display = "block";
    if (kpiPromptGuardAlert) kpiPromptGuardAlert.style.display = "none";
    if (kpiPromptResponseContent) kpiPromptResponseContent.style.display = "block";
    if (kpiPromptAnswerText) kpiPromptAnswerText.textContent = "Generando consulta SQL y analizando con OpenAI gpt-6-luna...";
    if (kpiPromptSqlCode) kpiPromptSqlCode.textContent = "Generando sentencia SQL...";
    if (kpiPromptTableWrapper) kpiPromptTableWrapper.innerHTML = "<div class='empty-state'>Extrayendo registros desde SQLite...</div>";

    try {
      const resp = await fetch("/api/kpi/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!resp.ok) throw new Error(`HTTP Error ${resp.status}`);
      const data = await resp.json();

      if (kpiPromptLatency) kpiPromptLatency.textContent = `Latencia: ${data.latency_ms} ms`;
      if (kpiPromptRowCount) kpiPromptRowCount.textContent = `Filas: ${data.total_rows || 0}`;
      if (kpiPromptModelBadge && data.model_name) kpiPromptModelBadge.textContent = `OpenAI ${data.model_name}`;

      // Handle guardrail out-of-scope response
      if (data.is_kpi_query === false) {
        if (kpiPromptGuardAlert) {
          kpiPromptGuardAlert.style.display = "flex";
          if (kpiPromptGuardText) kpiPromptGuardText.innerHTML = data.analysis.replace(/\n/g, "<br>");
        }
        if (kpiPromptResponseContent) kpiPromptResponseContent.style.display = "none";
        return;
      }

      // Valid response
      if (kpiPromptGuardAlert) kpiPromptGuardAlert.style.display = "none";
      if (kpiPromptResponseContent) kpiPromptResponseContent.style.display = "block";
      if (kpiPromptAnswerText) kpiPromptAnswerText.textContent = data.analysis;
      if (kpiPromptSqlCode) kpiPromptSqlCode.textContent = data.sql || "--";

      // Render Data Table
      if (kpiPromptTableWrapper) {
        if (data.rows && data.rows.length > 0) {
          const cols = Object.keys(data.rows[0]);
          let tableHtml = `<table class="kpi-data-table"><thead><tr>`;
          cols.forEach(c => tableHtml += `<th>${c}</th>`);
          tableHtml += `</tr></thead><tbody>`;
          data.rows.forEach(r => {
            tableHtml += `<tr>`;
            cols.forEach(c => tableHtml += `<td>${r[c] !== null && r[c] !== undefined ? r[c] : ""}</td>`);
            tableHtml += `</tr>`;
          });
          tableHtml += `</tbody></table>`;
          kpiPromptTableWrapper.innerHTML = tableHtml;
        } else {
          kpiPromptTableWrapper.innerHTML = "<div class='empty-state'>Sin filas devueltas para los criterios especificados.</div>";
        }
      }

    } catch (err) {
      console.error(err);
      if (kpiPromptAnswerText) kpiPromptAnswerText.textContent = `Error al consultar base de datos: ${err.message}`;
    } finally {
      btnSubmitKpiPrompt.disabled = false;
      btnSubmitKpiPrompt.innerHTML = `
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Preguntar a OpenAI</span>
      `;
    }
  }

  btnSubmitKpiPrompt?.addEventListener("click", executeKpiPromptQuery);
  kpiPromptInput?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      executeKpiPromptQuery();
    }
  });
});
