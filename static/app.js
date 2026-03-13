const state = {
  overview: null,
  shipments: [],
  filteredShipments: [],
  overviewRiskFilter: "All",
  latestSimulation: null,
  copilotOpen: false,
  llmSettings: null,
};

const panelMap = {
  overview: "overviewPanel",
  readiness: "readinessPanel",
  discovery: "discoveryPanel",
  risk: "riskPanel",
  disruption: "disruptionPanel",
  actions: "actionsPanel",
  value: "valuePanel",
  simulator: "simulatorPanel",
};

const kpiLabels = {
  total_shipments: "Total Shipments",
  delayed_shipments: "Delayed Shipments",
  on_time_pct: "On-Time %",
  average_delay_days: "Avg Delay Days",
  high_risk_shipments: "High-Risk Shipments",
  top_affected_warehouse: "Top Affected Warehouse",
  top_affected_carrier: "Top Affected Carrier",
  external_disruption_index: "External Disruption Index",
};

function showLoader(show) {
  document.getElementById("loader").classList.toggle("hidden", !show);
}

async function fetchJSON(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function updateLlmStatus(message, isError = false) {
  return;
}

function renderLlmSettingsState() {
  const input = document.getElementById("llmKeyInput");
  const title = document.getElementById("llmSettingsTitle");
  const pill = document.getElementById("llmSettingsPill");
  const configured = Boolean(state.llmSettings?.configured);
  const masked = state.llmSettings?.straive_api_key_masked || "";

  title.textContent = configured ? "API Key Saved" : "Set API Key";
  pill.textContent = configured ? "Saved" : "Gemini";
  pill.className = `pill ${configured ? "success" : "info"}`;

  if (!input.value) {
    input.placeholder = configured && masked ? `Saved key: ${masked}` : "Enter Straive API key";
  }
}

async function loadLlmSettings() {
  const result = await fetchJSON("/api/llm/settings");
  state.llmSettings = result;
  document.getElementById("llmKeyInput").value = "";
  renderLlmSettingsState();
}

async function saveLlmSettings() {
  const payload = {
    straive_api_key: document.getElementById("llmKeyInput").value.trim(),
    straive_model: "gemini-2.5-pro",
  };
  if (!payload.straive_api_key) {
    updateLlmStatus("API key is required to save Straive settings.", true);
    return;
  }
  const result = await fetchJSON("/api/llm/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.llmSettings = result;
  document.getElementById("llmKeyInput").value = "";
  renderLlmSettingsState();
}

async function clearLlmSettings() {
  await fetchJSON("/api/llm/settings/clear", {
    method: "POST",
  });
  state.llmSettings = null;
  document.getElementById("llmKeyInput").value = "";
  renderLlmSettingsState();
}

async function testLlmSettings() {
  const result = await fetchJSON("/api/llm/settings/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: "Summarize the current network risk posture in one sentence." }),
  });
  updateLlmStatus(result.ok ? `Test successful: ${result.message}` : `Test failed: ${result.message}`, !result.ok);
}

function safeText(value) {
  return String(value ?? "");
}

function formatNumber(value, digits = 0) {
  if (typeof value !== "number" || Number.isNaN(value)) return safeText(value);
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatPercent(value, digits = 1) {
  return `${formatNumber(value, digits)}%`;
}

function riskStatusMeta(delayRisk) {
  if (delayRisk >= 40) return { label: "Critical Risk", className: "status-critical" };
  if (delayRisk >= 25) return { label: "Moderate Risk", className: "status-watch" };
  return { label: "Stable", className: "status-pass" };
}

function renderGlobalStatus() {
  const { kpis, sla_breach_prediction, financial_exposure } = state.overview;
  const delayRisk = sla_breach_prediction.breach_rate;
  const status = riskStatusMeta(delayRisk);
  document.getElementById("globalStatusStrip").innerHTML = `
    <div class="status-strip-left">
      <span class="status-pill ${status.className}">Network Status: ${status.label}</span>
      <strong class="status-title">${delayRisk >= 40 ? "Immediate network intervention required" : delayRisk >= 25 ? "Network under active watch" : "Network operating within threshold"}</strong>
      <span class="status-subline">Live control-tower assessment based on current shipment risk, disruption exposure, and SLA breach projection.</span>
    </div>
    <div class="status-strip-metrics">
      <div class="status-metric"><span>Delay Risk</span><strong>${formatPercent(delayRisk, 1)}</strong></div>
      <div class="status-metric"><span>Shipments at Risk</span><strong>${formatNumber(kpis.high_risk_shipments)}</strong></div>
      <div class="status-metric"><span>Projected Cost Exposure</span><strong>$${formatNumber(financial_exposure.estimated_penalty_risk)}</strong></div>
      <div class="status-metric"><span>Top Watchpoint</span><strong>${kpis.top_affected_warehouse}</strong></div>
    </div>
  `;
}

function renderKPIs(kpis) {
  const cards = [
    ["Total Shipments", formatNumber(kpis.total_shipments), "Monitored across the active network."],
    ["Delayed Shipments", formatNumber(kpis.delayed_shipments), "Historical and current exception count."],
    ["On-Time %", `${kpis.on_time_pct}%`, "Current service performance benchmark."],
    ["High-Risk Shipments", formatNumber(kpis.high_risk_shipments), "Shipments needing active intervention."],
  ];
  document.getElementById("kpiGrid").innerHTML = cards.map(([label, value, tip]) => `
    <div class="kpi-card live-kpi-card" title="${tip}">
      <p class="eyebrow">${label}</p>
      <div class="value">${value}</div>
      <small>${tip}</small>
    </div>
  `).join("");
}

function renderExecutiveSummary() {
  document.getElementById("executiveSummaryMini").textContent = state.overview.executive_narrative;
  document.getElementById("overviewCompactSignals").innerHTML = state.overview.operational_insights.slice(0, 3)
    .map((text) => `<div class="feed-item"><strong>AI Insight</strong><span>${text}</span></div>`)
    .join("");
}

function renderCommandSnapshot() {
  const watchpoint = state.overview.kpis.top_affected_warehouse;
  const topLane = state.overview.lane_intelligence?.[0];
  const sla = state.overview.sla_breach_prediction;
  document.getElementById("commandSnapshot").innerHTML = `
    <div class="detail-stat">
      <strong>Primary Watchpoint</strong>
      <span>${watchpoint}</span>
    </div>
    <div class="detail-stat">
      <strong>Predicted SLA Breaches</strong>
      <span>${formatNumber(sla.predicted_breaches)} shipments</span>
    </div>
    <div class="detail-stat">
      <strong>Lane Under Stress</strong>
      <span>${topLane ? `${topLane.lane} | ${formatPercent(topLane.avg_risk * 100, 1)}` : "No active lane signal"}</span>
    </div>
  `;
}

function renderRiskDistribution() {
  const counts = state.overview.risk_band_counts;
  const total = Object.values(counts).reduce((sum, value) => sum + Number(value || 0), 0) || 1;
  const bands = [
    { band: "Low", count: counts.Low || 0, className: "risk-low", color: "#17a673" },
    { band: "Medium", count: counts.Medium || 0, className: "risk-medium", color: "#f2a900" },
    { band: "High", count: counts.High || 0, className: "risk-high", color: "#e55353" },
  ];
  document.getElementById("riskDistribution").innerHTML = `
    <div class="stacked-risk-bar">
      ${bands.map((item) => `
        <button class="stack-segment ${state.overviewRiskFilter === item.band ? "is-active" : ""}" data-risk-filter="${item.band}" style="width:${Math.max(12, (item.count / total) * 100)}%; background:${item.color}">
          ${item.band}
        </button>
      `).join("")}
    </div>
    <div class="risk-distribution-legend">
      <button class="risk-filter-pill ${state.overviewRiskFilter === "All" ? "is-active" : ""}" data-risk-filter="All">All</button>
      ${bands.map((item) => `
        <button class="risk-filter-pill ${state.overviewRiskFilter === item.band ? "is-active" : ""}" data-risk-filter="${item.band}">
          <span>${item.band}</span>
          <strong>${formatNumber(item.count)}</strong>
        </button>
      `).join("")}
    </div>
  `;
}

function warehouseMapPosition(label) {
  const positions = {
    "SEA-01": { x: 14, y: 18 },
    "LAX-01": { x: 16, y: 66 },
    "DAL-02": { x: 50, y: 66 },
    "CHI-01": { x: 58, y: 34 },
    "ATL-01": { x: 67, y: 62 },
    "NJ-01": { x: 84, y: 28 },
  };
  return positions[label] || { x: 50, y: 50 };
}

function renderNetworkMap() {
  const container = document.getElementById("networkMap");
  if (!container) return;
  const rows = [...state.overview.capacity_stress].slice(0, 6);
  const nodes = rows.map((row) => {
    const pos = warehouseMapPosition(row.origin_warehouse);
    const riskPct = row.avg_risk * 100;
    const riskClass = riskPct >= 38 ? "node-high" : riskPct >= 24 ? "node-medium" : "node-low";
    return {
      id: row.origin_warehouse,
      x: pos.x,
      y: pos.y,
      riskPct,
      backlog: row.backlog || 0,
      volume: row.volume || 0,
      riskClass,
      utilization: row.utilization * 100,
    };
  });
  const lanes = state.overview.lane_intelligence.slice(0, 6).map((lane, index) => {
    const source = nodes.find((node) => lane.lane.startsWith(node.id)) || nodes[index % Math.max(nodes.length, 1)];
    const regionTargets = {
      West: { x: 28, y: 55 },
      Midwest: { x: 62, y: 42 },
      South: { x: 70, y: 74 },
      Texas: { x: 56, y: 70 },
      Northeast: { x: 88, y: 24 },
    };
    const targetRegion = Object.keys(regionTargets).find((region) => lane.lane.includes(region)) || "Midwest";
    return { source, target: regionTargets[targetRegion], risk: lane.avg_risk * 100, label: lane.lane };
  }).filter((lane) => lane.source);
  const topNode = [...nodes].sort((a, b) => b.riskPct - a.riskPct)[0];
  document.getElementById("mapLegend").innerHTML = `
    <span><i class="legend-dot low"></i>Low</span>
    <span><i class="legend-dot medium"></i>Watch</span>
    <span><i class="legend-dot high"></i>Critical</span>
  `;
  if (!nodes.length) {
    container.innerHTML = `
      <div class="map-empty-state">
        <strong>Network topology unavailable</strong>
        <span>No warehouse risk nodes were returned for the active dataset.</span>
      </div>
    `;
    return;
  }
  container.innerHTML = `
    <div class="map-overlay-card">
      <strong>${nodes.length} active nodes | ${lanes.length} monitored lanes</strong>
      <span>Primary watchpoint: ${topNode?.id || "Unavailable"} at ${(topNode?.riskPct || 0).toFixed(1)}% delay risk</span>
    </div>
    <div class="us-map-shape"></div>
    ${lanes.map((lane) => {
      const dx = lane.target.x - lane.source.x;
      const dy = lane.target.y - lane.source.y;
      const length = Math.sqrt(dx * dx + dy * dy);
      const angle = Math.atan2(dy, dx) * (180 / Math.PI);
      return `<div class="map-lane" title="${lane.label} | ${(lane.risk).toFixed(1)}% risk" style="left:${lane.source.x}%; top:${lane.source.y}%; width:${length}%; transform:rotate(${angle}deg)"></div>`;
    }).join("")}
    ${nodes.map((node) => `
      <button
        class="map-node ${node.riskClass}"
        style="left:${node.x}%; top:${node.y}%"
        title="${node.id} | Delay probability ${node.riskPct.toFixed(1)}% | Backlog ${formatNumber(node.backlog, 1)} | Utilization ${node.utilization.toFixed(1)}%"
      >
        <span>${node.id}</span>
        <small>${node.riskPct.toFixed(0)}%</small>
      </button>
    `).join("")}
    <div class="map-footnote">Hover nodes to inspect warehouse risk, backlog level, and utilization.</div>
  `;
}

function renderAiActions() {
  document.getElementById("aiActionsPanel").innerHTML = state.overview.decision_actions.slice(0, 3).map((item, index) => `
    <div class="decision-card ai-action-card">
      <div class="decision-card-head">
        <strong>${item.title}</strong>
        <span class="confidence-pill">${Math.min(96, Math.max(68, Math.round(item.delay_reduction_pct * 2.8)))}% confidence</span>
      </div>
      <p><strong>Reason:</strong> ${item.problem}</p>
      <p><strong>Impact:</strong> ${item.delay_reduction_pct}% delay reduction</p>
      <p><strong>Savings:</strong> $${formatNumber(Math.round(item.cost_impact * 0.78))}</p>
      <p>${item.option}</p>
      <button class="primary-btn small-btn" data-sim-action-index="${index}">Simulate Impact</button>
    </div>
  `).join("");
}

function filteredOverviewShipments() {
  const rows = state.overview.top_shipments || [];
  if (state.overviewRiskFilter === "All") return rows;
  return rows.filter((row) => row.risk_band === state.overviewRiskFilter);
}

function renderExceptionsTable() {
  const rows = filteredOverviewShipments().slice(0, 10);
  document.getElementById("exceptionTableBody").innerHTML = rows.map((row) => `
    <tr>
      <td>${row.shipment_id}</td>
      <td>${row.origin_warehouse} → ${row.destination.split(",")[1]?.trim() || row.destination}</td>
      <td>${row.carrier}</td>
      <td>${(row.risk_probability * 100).toFixed(1)}%</td>
      <td>${row.key_risk_driver}</td>
      <td>${row.delay_days || 0} days</td>
      <td>${row.recommended_action}</td>
      <td class="table-cta">
        <button class="ghost-btn exception-action-btn" data-exception-action="Reroute" data-id="${row.shipment_id}">Reroute</button>
        <button class="ghost-btn exception-action-btn" data-exception-action="Expedite" data-id="${row.shipment_id}">Expedite</button>
        <button class="ghost-btn exception-action-btn" data-exception-action="Escalate carrier" data-id="${row.shipment_id}">Escalate</button>
      </td>
    </tr>
  `).join("");
}

function renderScenarioQuick() {
  const presets = [
    { label: "Storm near LAX", type: "storm_region", entity: "West", severity: 4 },
    { label: "Carrier strike", type: "carrier_underperformance", entity: state.overview.kpis.top_affected_carrier, severity: 4 },
    { label: "Staffing shortage", type: "staffing_shortage", entity: state.overview.kpis.top_affected_warehouse, severity: 3 },
    { label: "High holiday volume", type: "backlog_spike", entity: state.overview.kpis.top_affected_warehouse, severity: 5 },
  ];
  document.getElementById("scenarioQuickGrid").innerHTML = presets.map((preset, index) => `
    <button class="scenario-chip ${state.latestSimulation?.index === index ? "is-active" : ""}" data-scenario-index="${index}" data-scenario-type="${preset.type}" data-scenario-entity="${preset.entity}" data-scenario-severity="${preset.severity}">
      ${preset.label}
    </button>
  `).join("");
  document.getElementById("scenarioImpactSummary").innerHTML = state.latestSimulation?.summaryMarkup || `
    <div class="metric-item"><strong>Simulation status</strong><span>Select a disruption to recompute risk, risk mix, and recommended actions.</span></div>
  `;
}

function renderActions(shipments) {
  const container = document.getElementById("topActions");
  if (!container) return;
  const actions = Object.entries(
    shipments.reduce((acc, row) => {
      acc[row.recommended_action] = (acc[row.recommended_action] || 0) + 1;
      return acc;
    }, {})
  ).sort((a, b) => b[1] - a[1]).slice(0, 3);
  container.innerHTML = actions
    .map(([action, count]) => `<div class="action-item"><strong>${action}</strong><span>${count} shipments impacted in current view</span></div>`)
    .join("");
}

function renderReadiness() {
  const quality = state.overview.data_quality;
  const score = quality.quality_score;
  const validationTiles = quality.validation_matrix;
  const qualityIssues = quality.anomaly_flags;
  const coverage = quality.coverage;
  const driftLead = quality.drift_rows.sort((a, b) => Math.abs(b.drift_pct) - Math.abs(a.drift_pct))[0];

  document.getElementById("qualityHeadline").innerHTML = `
    <p class="eyebrow">Data Quality Checks</p>
    <h3>Control-tower data is fit for prediction and operational actioning</h3>
    <p class="summary-copy">Quality controls now evaluate the active dataset for completeness, timestamp integrity, and behavioral drift before the scoring layer is trusted.</p>
  `;
  document.getElementById("qualityCoverage").innerHTML = `
    <p class="eyebrow">Quality Score</p>
    <h3>${score} / 100</h3>
    <div class="micro-grid">
      <div class="micro-stat"><strong>${quality.missing_ratio_pct}%</strong><span>Average missingness</span></div>
      <div class="micro-stat"><strong>${quality.sequence_integrity_pct}%</strong><span>Sequence valid</span></div>
      <div class="micro-stat"><strong>${quality.validation_matrix.length}</strong><span>Validation domains</span></div>
      <div class="micro-stat"><strong>${score >= 92 ? "Ready" : "Watch"}</strong><span>Scoring status</span></div>
    </div>
  `;
  document.getElementById("qualityAlert").innerHTML = `
    <p class="eyebrow">QA Watchpoint</p>
    <h3>${driftLead.field.replaceAll("_", " ")} is drifting fastest</h3>
    <div class="summary-flag">${driftLead.drift_pct > 0 ? "+" : ""}${driftLead.drift_pct}% recent shift</div>
    <p class="summary-copy">The strongest recent movement is being monitored because fast distribution changes can distort model stability and root-cause interpretation.</p>
  `;

  document.getElementById("readinessChecklist").innerHTML = validationTiles
    .map((tile) => `
      <div class="quality-tile">
        <div class="quality-tile-header">
          <strong>${tile.title}</strong>
          <span class="status-chip ${tile.status === "Pass" ? "status-pass" : tile.status === "Critical" ? "status-critical" : "status-watch"}">${tile.status}</span>
        </div>
        <div class="quality-stat">${tile.value}</div>
        <span>${tile.copy}</span>
      </div>
    `)
    .join("");

  document.getElementById("readinessScorecard").innerHTML = `
    <div class="metric-item"><strong>Readiness Score</strong><span>${score} / 100</span></div>
    <div class="metric-item"><strong>Completeness</strong><span>${(100 - quality.missing_ratio_pct).toFixed(2)}%</span></div>
    <div class="metric-item"><strong>Sequence Validation</strong><span>${quality.sequence_integrity_pct}% valid lifecycle order</span></div>
    <div class="metric-item"><strong>Model Eligibility</strong><span>${score >= 92 ? "Approved for scoring" : "Review before scoring"}</span></div>
  `;

  document.getElementById("qualityIssues").innerHTML = qualityIssues
    .map((issue) => `
      <div class="feed-item">
        <strong>${issue.severity}: ${issue.title}</strong>
        <span>${issue.detail}</span>
      </div>
    `)
    .join("");

  document.getElementById("qualityCoverageGrid").innerHTML = coverage
    .map((item) => `<div class="metric-item"><strong>${item.title}</strong><span>${item.value}</span></div>`)
    .join("");
}

function transparentLayout() {
  return {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { family: "Manrope, sans-serif", color: "#1d232c" },
  };
}

function baseBarLayout(yTitle, horizontal = false) {
  return {
    ...transparentLayout(),
    margin: { t: 20, l: horizontal ? 170 : 40, r: 20, b: 60 },
    xaxis: horizontal ? { title: yTitle } : { tickangle: -18 },
    yaxis: horizontal ? {} : { title: yTitle },
  };
}

function renderCharts() {
  const overview = state.overview;
  const eventMarkers = [
    { day: overview.trend[8]?.order_day, label: "Storm" },
    { day: overview.trend[18]?.order_day, label: "Strike" },
    { day: overview.trend[25]?.order_day, label: "Holiday spike" },
  ].filter((event) => event.day);
  Plotly.newPlot(
    "trendChart",
    [
      {
        x: overview.trend.map((row) => row.order_day),
        y: overview.trend.map((row) => Number((row.delay_rate * 100).toFixed(2))),
        type: "scatter",
        mode: "lines+markers",
        name: "Delay Rate %",
        line: { color: "#f58220", width: 3 },
      },
      {
        x: overview.trend.map((row) => row.order_day),
        y: overview.trend.map((row) => Number((row.avg_risk * 100).toFixed(2))),
        type: "scatter",
        mode: "lines",
        name: "Average Risk %",
        line: { color: "#2f6df6", width: 3, dash: "dot" },
        yaxis: "y2",
      },
    ],
    {
      ...transparentLayout(),
      margin: { t: 20, l: 40, r: 40, b: 30 },
      yaxis: { title: "Delay Rate %" },
      yaxis2: { title: "Average Risk %", overlaying: "y", side: "right" },
      shapes: eventMarkers.map((event) => ({
        type: "line",
        x0: event.day,
        x1: event.day,
        y0: 0,
        y1: 1,
        yref: "paper",
        line: { color: "rgba(229,83,83,0.22)", width: 2, dash: "dot" },
      })),
      annotations: eventMarkers.map((event) => ({
        x: event.day,
        y: 1,
        yref: "paper",
        text: event.label,
        showarrow: false,
        yshift: 10,
        font: { size: 11, color: "#68717d" },
      })),
    },
    { displayModeBar: false, responsive: true }
  );
  Plotly.newPlot(
    "riskDriverDonut",
    [{
      labels: overview.root_cause_breakdown.map((r) => r.cause),
      values: overview.root_cause_breakdown.map((r) => r.share),
      type: "pie",
      hole: 0.62,
      marker: { colors: ["#f58220", "#f2a900", "#e55353", "#2f6df6", "#17a673"] },
      textinfo: "none",
      sort: false,
    }],
    {
      ...transparentLayout(),
      margin: { t: 0, l: 0, r: 0, b: 0 },
      showlegend: false,
      annotations: [{ text: "Drivers", x: 0.5, y: 0.5, showarrow: false, font: { size: 16, color: "#1d232c" } }],
    },
    { displayModeBar: false, responsive: true }
  );
}

function riskBadge(band) {
  const css = band === "High" ? "risk-high" : band === "Medium" ? "risk-medium" : "risk-low";
  return `<span class="risk-badge ${css}">${band}</span>`;
}

function renderShipmentTable(rows = state.overview.top_shipments) {
  state.filteredShipments = rows;
  document.getElementById("shipmentTableBody").innerHTML = rows.map((row) => `
      <tr>
        <td>${safeText(row.shipment_id)}</td>
        <td>${safeText(row.destination)}</td>
        <td>${safeText(row.carrier)}</td>
        <td>${safeText(row.origin_warehouse)}</td>
        <td>${(row.risk_probability * 100).toFixed(1)}%</td>
        <td>${riskBadge(row.risk_band)}</td>
        <td>${safeText(row.key_risk_driver)}</td>
        <td>${row.external_overlays.map((item) => `<span class="overlay-badge">${item}</span>`).join("") || "None"}</td>
        <td>${safeText(row.recommended_action)}</td>
        <td class="table-cta"><button class="ghost-btn shipment-detail-btn" data-id="${row.shipment_id}">Why</button></td>
      </tr>
    `).join("");
}

function renderAlerts() {
  document.getElementById("alertFeed").innerHTML = state.overview.region_signals
    .sort((a, b) => b.disruption_severity - a.disruption_severity)
    .map((signal) => `
      <div class="feed-item">
        <strong>${signal.destination_region}</strong>
        <span>Severity ${signal.disruption_severity}. Weather ${signal.avg_weather.toFixed(1)}, traffic ${signal.avg_traffic.toFixed(1)}, closures ${signal.closures}, strikes ${signal.strikes}, port pressure ${signal.port_congestion_score.toFixed(1)}.</span>
      </div>
    `).join("");
}

function renderRegionSeverityBlock() {
  const signals = state.overview.region_signals || [];
  if (!signals.length) {
    document.getElementById("regionSeveritySummary").innerHTML = `
      <div class="detail-stat"><strong>0</strong><span>Active regions</span></div>
      <div class="detail-stat"><strong>0</strong><span>Peak severity</span></div>
      <div class="detail-stat"><strong>No feed</strong><span>Signal status</span></div>
    `;
    document.getElementById("regionSeverityFeed").innerHTML = `
      <div class="empty-state"><strong>Disruption feed unavailable</strong><span>No regional disruption records were returned for the active dataset.</span></div>
    `;
    return;
  }

  const sorted = [...signals].sort((a, b) => b.disruption_severity - a.disruption_severity);
  const top = sorted[0];
  const avgSeverity = sorted.reduce((sum, row) => sum + Number(row.disruption_severity || 0), 0) / sorted.length;
  const impactedShipments = sorted.reduce((sum, row) => sum + Number(row.shipment_count || 0), 0);
  const peakSeverity = Math.max(...sorted.map((row) => Number(row.disruption_severity || 0)), 1);
  document.getElementById("regionSeveritySummary").innerHTML = `
    <div class="detail-stat"><strong>${sorted.length}</strong><span>Active regions</span></div>
    <div class="detail-stat"><strong>${formatNumber(top.disruption_severity, 1)}</strong><span>Peak severity</span></div>
    <div class="detail-stat"><strong>${formatNumber(avgSeverity, 1)}</strong><span>Average severity</span></div>
  `;
  document.getElementById("regionSeverityFeed").innerHTML = sorted.slice(0, 3).map((row, index) => `
    <div class="signal-row">
      <div class="signal-row-head">
        <strong>${index + 1}. ${row.destination_region}</strong>
        <span>${formatNumber(row.disruption_severity, 1)}</span>
      </div>
      <div class="signal-bar"><span style="width:${Math.max(8, (Number(row.disruption_severity || 0) / peakSeverity) * 100)}%"></span></div>
      <span>Weather ${formatNumber(row.avg_weather, 1)} | Traffic ${formatNumber(row.avg_traffic, 1)} | Closures ${formatNumber(row.closures)} | Strikes ${formatNumber(row.strikes)}</span>
    </div>
  `).join("") + `
    <div class="feed-item"><strong>Regional footprint</strong><span>${formatNumber(impactedShipments)} shipment-region observations are currently covered by the disruption layer.</span></div>
  `;
}

function renderCopilotDock() {
  const isOpen = state.copilotOpen;
  document.getElementById("copilotModal").classList.toggle("hidden", !isOpen);
  document.getElementById("copilotLauncher").classList.toggle("is-active", isOpen);
  const prompts = [
    "Why are delays increasing in the network?",
    `Why is ${state.overview.kpis.top_affected_warehouse} driving risk?`,
    `What is the fastest action to reduce SLA breaches?`,
  ];
  document.getElementById("copilotPromptTray").innerHTML = prompts.map((prompt) => `
    <button class="detail-chip" data-copilot-prompt="${prompt}">${prompt}</button>
  `).join("");
}

function renderValues() {
  const exposure = state.overview.financial_exposure;
  const longTerm = [
    "Improved on-time performance through systematic risk management.",
    "Better labor and carrier capacity planning using repeatable predictive signals.",
    "Stronger SLA adherence with measurable carrier governance.",
    "A durable operations culture centered on data-driven operational decisions.",
  ];
  document.getElementById("financialExposure").innerHTML = `
    <div class="metric-item"><strong>High-risk shipment value</strong><span>$${Number(exposure.high_risk_shipments_value).toLocaleString()}</span></div>
    <div class="metric-item"><strong>Estimated penalty risk</strong><span>$${Number(exposure.estimated_penalty_risk).toLocaleString()}</span></div>
    <div class="metric-item"><strong>Potential expedite cost</strong><span>$${Number(exposure.potential_expedite_cost).toLocaleString()}</span></div>
    <div class="metric-item"><strong>Predicted SLA breaches</strong><span>${state.overview.sla_breach_prediction.predicted_breach_shipments}</span></div>
  `;
  document.getElementById("longTermValue").innerHTML = longTerm.map((item) => `<div class="value-item">${item}</div>`).join("");
  document.getElementById("executiveNarrative").textContent = state.overview.executive_narrative;
  document.getElementById("learningLoop").innerHTML = `
    <div class="metric-item"><strong>Predicted delay average</strong><span>${state.overview.learning_loop.predicted_delay_avg}%</span></div>
    <div class="metric-item"><strong>Actual delay rate</strong><span>${state.overview.learning_loop.actual_delay_rate}%</span></div>
    <div class="metric-item"><strong>Status</strong><span>${state.overview.learning_loop.status}</span></div>
  `;
}

function renderInsights() {
  const topCause = state.overview.root_cause_breakdown[0];
  const topLane = state.overview.lane_intelligence[0];
  const topWarehouse = [...state.overview.capacity_stress].sort((a, b) => b.avg_risk - a.avg_risk)[0];
  const weakestCarrier = [...state.overview.carrier_reliability].sort((a, b) => a.reliability - b.reliability)[0];
  const mappedExposure = state.overview.root_cause_breakdown.reduce((sum, row) => sum + Number(row.share || 0), 0);

  document.getElementById("riskInsightHeadline").textContent = `${topCause.cause} is the dominant operational risk pattern`;
  document.getElementById("riskInsightNarrative").textContent = `${topCause.cause} is driving ${topCause.share}% of current predicted delay exposure. The highest stress is concentrated around ${topWarehouse.origin_warehouse}, while ${weakestCarrier.carrier} is the weakest carrier reliability node. The most fragile lane right now is ${topLane.lane}.`;
  document.getElementById("riskInsightStats").innerHTML = `
    <div class="decision-stat"><strong>${topCause.share}%</strong><span>Root-cause share</span></div>
    <div class="decision-stat"><strong>${(topLane.avg_risk * 100).toFixed(1)}%</strong><span>Top lane risk</span></div>
    <div class="decision-stat"><strong>${(weakestCarrier.reliability * 100).toFixed(1)}%</strong><span>Weakest carrier reliability</span></div>
  `;
  document.getElementById("riskFocusList").innerHTML = [
    `${topWarehouse.origin_warehouse} is the highest average-risk warehouse`,
    `${weakestCarrier.carrier} is underperforming network reliability`,
    `${topLane.lane} is the first lane to stabilize`,
  ].map((text, index) => `
    <div class="decision-priority-item">
      <strong>${index + 1}. Focus area</strong>
      <span>${text}</span>
    </div>
  `).join("");

  document.getElementById("rootCauseSummary").innerHTML = `
    <div class="detail-stat"><strong>${topCause.cause}</strong><span>Top cause</span></div>
    <div class="detail-stat"><strong>${topCause.share}%</strong><span>Leading share</span></div>
    <div class="detail-stat"><strong>${formatNumber(mappedExposure, 1)}%</strong><span>Mapped exposure</span></div>
  `;

  document.getElementById("rootCauseBreakout").innerHTML = state.overview.root_cause_breakdown.map((row) => `
    <div class="signal-row">
      <div class="signal-row-head">
        <strong>${row.cause}</strong>
        <span>${row.share}%</span>
      </div>
      <div class="signal-bar"><span style="width:${Math.min(row.share, 100)}%"></span></div>
    </div>
  `).join("");

  document.getElementById("stressMatrix").innerHTML = [
    ...state.overview.capacity_stress.slice(0, 3).map((row) => ({
      label: row.origin_warehouse,
      sublabel: `Warehouse utilization ${(row.utilization * 100).toFixed(1)}% | Avg risk ${(row.avg_risk * 100).toFixed(1)}%`,
      value: row.avg_risk * 100,
    })),
    ...state.overview.carrier_reliability.slice(-3).reverse().map((row) => ({
      label: row.carrier,
      sublabel: `Carrier reliability ${(row.reliability * 100).toFixed(1)}% | Avg risk ${(row.avg_risk * 100).toFixed(1)}%`,
      value: row.avg_risk * 100,
    })),
  ].map((row) => `
    <div class="signal-row">
      <div class="signal-row-head">
        <strong>${row.label}</strong>
        <span>${row.value.toFixed(1)} risk index</span>
      </div>
      <span>${row.sublabel}</span>
      <div class="signal-bar"><span style="width:${Math.min(row.value, 100)}%"></span></div>
    </div>
  `).join("");

  document.getElementById("overviewCompactSignals").innerHTML = state.overview.operational_insights.slice(0, 3).map((text) => `
    <div class="feed-item"><strong>Signal</strong><span>${text}</span></div>
  `).join("");
  const icons = {
    "External disruption": "🌩",
    "Inventory shortage": "📦",
    "Warehouse backlog": "🏭",
    "Staffing strain": "👥",
    "Carrier reliability": "🚚",
  };
  const driverPeak = Math.max(...state.overview.root_cause_breakdown.map((row) => Number(row.share || 0)), 1);
  document.getElementById("riskDriverList").innerHTML = state.overview.root_cause_breakdown.map((row) => `
    <div class="signal-row">
      <div class="signal-row-head">
        <strong>${icons[row.cause] || "•"} ${row.cause}</strong>
        <span>${row.share}%</span>
      </div>
      <div class="signal-bar"><span style="width:${Math.max(10, (Number(row.share || 0) / driverPeak) * 100)}%"></span></div>
    </div>
  `).join("");
  document.getElementById("laneIntelligence").innerHTML = state.overview.lane_intelligence.map((row) => `
    <div class="signal-row">
      <div class="signal-row-head">
        <strong>${row.lane}</strong>
        <span>${(row.avg_risk * 100).toFixed(1)}%</span>
      </div>
      <span>${(row.delay_rate * 100).toFixed(1)}% delay rate across ${row.volume} shipments</span>
      <div class="signal-bar"><span style="width:${Math.min(row.avg_risk * 100, 100)}%"></span></div>
    </div>
  `).join("");
  document.getElementById("warehouseHeatmap").innerHTML = state.overview.warehouse_heatmap.map((row) => `
    <div class="heat-row heat-${row.status.toLowerCase()}">
      <div class="heat-row-head">
        <strong>${row.origin_warehouse}</strong>
        <span>${row.status}</span>
      </div>
      <span>Average risk ${(row.avg_risk * 100).toFixed(1)}%</span>
      <span>Utilization ${(row.utilization * 100).toFixed(1)}%</span>
    </div>
  `).join("");
}

function renderActionsPanel() {
  document.getElementById("alertCenter").innerHTML = state.overview.alerts.map((alert) => `
    <div class="feed-item">
      <strong>${alert.severity}: ${alert.title}</strong>
      <span>${alert.detail}</span>
      <div class="action-btn-row">
        <button class="ghost-btn action-btn" data-action-kind="acknowledge_alert" data-action-label="Acknowledge alert" data-action-target="${alert.title}">Acknowledge</button>
        <button class="ghost-btn action-btn" data-action-kind="escalate_alert" data-action-label="Escalate alert" data-action-target="${alert.title}">Escalate</button>
        <button class="ghost-btn action-btn" data-action-kind="open_playbook" data-action-label="Open playbook" data-action-target="${alert.title}">Open Playbook</button>
      </div>
    </div>
  `).join("");
  document.getElementById("timelineFeed").innerHTML = state.overview.operational_timeline.map((item) => `
    <div class="timeline-item">
      <p class="eyebrow">${item.time}</p>
      <strong>${item.event}</strong>
    </div>
  `).join("");
  document.getElementById("actionSimulationCards").innerHTML = state.overview.action_simulations.map((item) => `
    <div class="metric-item">
      <strong>${item.action} | ${item.target}</strong>
      <span>Delay probability drops from ${(item.before * 100).toFixed(0)}% to ${(item.after * 100).toFixed(0)}%</span>
      <span>${item.effect}</span>
      <div class="action-btn-row">
        <button class="ghost-btn action-btn" data-action-kind="simulate_action" data-action-label="Run simulation" data-action-target="${item.target}">Run Simulation</button>
      </div>
    </div>
  `).join("");
  document.getElementById("decisionEngine").innerHTML = state.overview.decision_actions.map((item) => `
    <div class="decision-card">
      <strong>${item.title}</strong>
      <p>${item.problem}</p>
      <p>${item.option}</p>
      <p>Delay reduction ${item.delay_reduction_pct}% | Cost $${item.cost_impact.toLocaleString()} | SLA saved ${item.sla_saved} | ROI ${item.roi}</p>
      <div class="action-btn-row">
        <button class="primary-btn small-btn action-btn" data-action-kind="execute_decision" data-action-label="Execute action" data-action-target="${item.title}">Execute Now</button>
        <button class="ghost-btn action-btn" data-action-kind="simulate_decision" data-action-label="Simulate action" data-action-target="${item.title}">Simulate</button>
        <button class="ghost-btn action-btn" data-action-kind="assign_owner" data-action-label="Assign owner" data-action-target="${item.title}">Assign Owner</button>
      </div>
    </div>
  `).join("");
  document.getElementById("playbookRules").innerHTML = state.overview.playbooks.map((item) => `
    <div class="feed-item">
      <strong>${item.name}</strong>
      <span>${item.rule}</span>
      <div class="action-btn-row">
        <button class="ghost-btn action-btn" data-action-kind="trigger_playbook" data-action-label="Trigger playbook" data-action-target="${item.name}">Trigger</button>
      </div>
    </div>
  `).join("");
  document.getElementById("actionExecutionFeed").innerHTML = `
    <div class="feed-item">
      <strong>Action console</strong>
      <span>Execute, simulate, escalate, or trigger automation rules directly from this page.</span>
    </div>
  `;
}

function postActionFeedback(title, detail) {
  document.getElementById("actionExecutionFeed").innerHTML = `
    <div class="feed-item">
      <strong>${title}</strong>
      <span>${detail}</span>
    </div>
  `;
}

function renderAgentStatus() {
  document.getElementById("agentStatus").innerHTML = state.overview.agent_status.map((agent) => `
    <div class="agent-status-item">
      <strong>${agent.name}</strong>
      <span>${agent.status === "active" ? "Active ✓" : "Standby"}</span>
    </div>
  `).join("");
}

function renderSignalProviders() {
  const providers = [
    { name: "OpenWeather Adapter", detail: "Weather severity and storm signals mapped to destination regions." },
    { name: "TomTom Traffic Adapter", detail: "Traffic congestion scores influence dynamic shipment risk." },
    { name: "Road Closure Adapter", detail: "Road closure signals can be wired to DOT or mapping feeds." },
    { name: "Strike / News Adapter", detail: "Labor and disruption alerts are ingestible via news or incident APIs." },
  ];
  document.getElementById("signalProviders").innerHTML = providers.map((provider) => `
    <div class="feed-item">
      <strong>${provider.name}</strong>
      <span>${provider.detail}</span>
    </div>
  `).join("");
}

function renderNetworkGraph() {
  const graph = state.overview.network_graph;
  const container = document.getElementById("networkGraph");
  const warehouseNodes = graph.nodes.filter((node) => node.kind === "warehouse");
  const carrierNodes = graph.nodes.filter((node) => node.kind === "carrier");
  const regionNodes = graph.nodes.filter((node) => node.kind === "region");
  const positionMap = {};
  let nodeMarkup = "";

  function place(nodes, xPct) {
    nodeMarkup += nodes.map((node, index) => {
      const top = 16 + (index * (68 / Math.max(nodes.length - 1, 1)));
      positionMap[node.id] = { x: xPct, y: top };
      return `<div class="graph-node node-${node.kind}" style="left:${xPct}%; top:${top}%">${node.label}</div>`;
    }).join("");
  }

  place(warehouseNodes, 16);
  place(carrierNodes, 50);
  place(regionNodes, 84);

  const lines = graph.edges.slice(0, 24).map((edge) => {
    const source = positionMap[edge.source];
    const target = positionMap[edge.target];
    if (!source || !target) return "";
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const length = Math.sqrt(dx * dx + dy * dy);
    const angle = Math.atan2(dy, dx) * (180 / Math.PI);
    return `<div class="graph-line" style="left:${source.x}%; top:${source.y}%; width:${length}%; transform:rotate(${angle}deg)"></div>`;
  }).join("");

  container.innerHTML = `
    ${lines}
    ${nodeMarkup}
  `;
}

async function askCopilot(question) {
  if (!question) return;
  state.copilotOpen = true;
  renderCopilotDock();
  showLoader(true);
  const result = await fetchJSON("/api/copilot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const feed = document.getElementById("copilotFeed");
  feed.innerHTML = `
    <div class="feed-item"><strong>You asked</strong><span>${result.question}</span></div>
    <div class="feed-item"><strong>Control Tower Copilot</strong><span>${result.answer}</span></div>
  `;
  showLoader(false);
}

function populateFilters() {
  const filters = state.overview.filters;
  setupSelect("warehouseFilter", ["All", ...filters.warehouses]);
  setupSelect("carrierFilter", ["All", ...filters.carriers]);
  setupSelect("priorityFilter", ["All", ...filters.priorities]);
  setupSelect("scenarioType", [
    ["storm_region", "Storm in Region"],
    ["warehouse_strike", "Warehouse Strike"],
    ["carrier_underperformance", "Carrier Underperformance"],
    ["staffing_shortage", "Staffing Shortage"],
    ["backlog_spike", "Backlog Spike"],
  ], true);
  updateScenarioEntities();
}

function setupSelect(id, options, labelValuePairs = false) {
  document.getElementById(id).innerHTML = options.map((option) => {
    if (labelValuePairs) {
      return `<option value="${option[0]}">${option[1]}</option>`;
    }
    return `<option value="${option}">${option}</option>`;
  }).join("");
}

function updateScenarioEntities() {
  const type = document.getElementById("scenarioType").value;
  const filters = state.overview.filters;
  const entities = type === "storm_region" ? filters.regions : type === "carrier_underperformance" ? filters.carriers : filters.warehouses;
  setupSelect("scenarioEntity", entities);
}

function applyFilters() {
  const warehouse = document.getElementById("warehouseFilter").value;
  const carrier = document.getElementById("carrierFilter").value;
  const priority = document.getElementById("priorityFilter").value;
  const filtered = state.overview.top_shipments.filter((row) =>
    (warehouse === "All" || row.origin_warehouse === warehouse) &&
    (carrier === "All" || row.carrier === carrier) &&
    (priority === "All" || row.priority === priority)
  );
  state.shipments = filtered;
  renderActions(filtered);
  renderShipmentTable(filtered);
}

async function runQuickScenario(payload, index = null) {
  showLoader(true);
  const result = await fetchJSON("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.latestSimulation = {
    index,
    summaryMarkup: Object.entries(result.summary)
      .map(([key, value]) => `<div class="metric-item"><strong>${key.replaceAll("_", " ")}</strong><span>${value}</span></div>`)
      .join(""),
  };
  renderScenarioQuick();
  showLoader(false);
}

async function openShipmentModal(shipmentId) {
  showLoader(true);
  const detail = await fetchJSON(`/api/shipments/${shipmentId}`);
  document.getElementById("modalTitle").textContent = `${detail.shipment_id} | ${detail.destination}`;
  document.getElementById("modalBody").innerHTML = `
    <div class="modal-grid">
      <div class="metric-item"><strong>Risk</strong><span>${(detail.risk_probability * 100).toFixed(1)}% ${detail.risk_band}</span></div>
      <div class="metric-item"><strong>Recommended Action</strong><span>${detail.recommended_action}</span></div>
      <div class="metric-item"><strong>Service Level</strong><span>${detail.service_level}</span></div>
      <div class="metric-item"><strong>Priority</strong><span>${detail.priority}</span></div>
    </div>
    <div class="feed-item">
      <strong>Why this shipment is risky</strong>
      <span>${detail.risk_summary}</span>
    </div>
    <div class="check-item">
      <strong>External overlays</strong>
      <div>${detail.external_overlays.map((item) => `<span class="overlay-badge">${item}</span>`).join("") || "No active overlays"}</div>
    </div>
    <div class="check-item">
      <strong>Shipment lifecycle</strong>
      ${detail.shipment_lifecycle.map((stage) => `<div class="feed-item"><strong>${stage.stage}</strong><span>${stage.time}</span></div>`).join("")}
    </div>
    <div class="check-item">
      <strong>Driver contribution</strong>
      ${Object.entries(detail.reason_scores).map(([key, value]) => `
        <div class="driver-bar">
          <span>${key.replaceAll("_", " ")}</span>
          <strong style="max-width:${Math.min(value, 100)}%"></strong>
        </div>
      `).join("")}
    </div>
    <div class="modal-grid">
      ${Object.entries(detail.operational_snapshot).map(([key, value]) => `<div class="metric-item"><strong>${key.replaceAll("_", " ")}</strong><span>${value}</span></div>`).join("")}
    </div>
  `;
  document.getElementById("shipmentModal").classList.remove("hidden");
  showLoader(false);
}

async function runScenario() {
  showLoader(true);
  const payload = {
    scenario_type: document.getElementById("scenarioType").value,
    region_or_entity: document.getElementById("scenarioEntity").value,
    severity: Number(document.getElementById("scenarioSeverity").value),
  };
  const result = await fetchJSON("/api/simulate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  document.getElementById("scenarioSummary").innerHTML = Object.entries(result.summary)
    .map(([key, value]) => `<div class="metric-item"><strong>${key.replaceAll("_", " ")}</strong><span>${value}</span></div>`)
    .join("");
  document.getElementById("scenarioResults").innerHTML = result.impacted_shipments.slice(0, 10).map((row) => `
      <div class="feed-item">
        <strong>${row.shipment_id} | ${row.destination}</strong>
        <span>${row.origin_warehouse} via ${row.carrier} now at ${(row.risk_probability * 100).toFixed(1)}% risk. ${row.recommended_action}</span>
      </div>
    `).join("");
  showLoader(false);
}

function bindEvents() {
  document.getElementById("enterAppBtn").addEventListener("click", () => {
    document.getElementById("loginShell").classList.add("hidden");
    document.getElementById("appShell").classList.remove("hidden");
  });

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((panel) => panel.classList.remove("active"));
      button.classList.add("active");
      document.getElementById(panelMap[button.dataset.target]).classList.add("active");
      document.getElementById("pageTitle").textContent = button.textContent;
    });
  });

  document.getElementById("shipmentSearch").addEventListener("input", (event) => {
    const query = event.target.value.toLowerCase();
    renderShipmentTable(
      state.filteredShipments.filter((row) =>
        [row.shipment_id, row.order_id, row.carrier, row.destination, row.key_risk_driver].join(" ").toLowerCase().includes(query)
      )
    );
  });

  document.getElementById("shipmentTableBody").addEventListener("click", (event) => {
    const button = event.target.closest(".shipment-detail-btn");
    if (button) {
      openShipmentModal(button.dataset.id).catch((error) => {
        showLoader(false);
        document.getElementById("modalBody").innerHTML = `<div class="feed-item">Failed to load shipment detail: ${error.message}</div>`;
        document.getElementById("shipmentModal").classList.remove("hidden");
      });
    }
  });

  ["warehouseFilter", "carrierFilter", "priorityFilter"].forEach((id) => {
    document.getElementById(id).addEventListener("change", applyFilters);
  });

  document.getElementById("overviewPanel").addEventListener("click", (event) => {
    const riskFilter = event.target.closest("[data-risk-filter]");
    if (riskFilter) {
      state.overviewRiskFilter = riskFilter.dataset.riskFilter;
      renderRiskDistribution();
      renderExceptionsTable();
      return;
    }

    const actionSim = event.target.closest("[data-sim-action-index]");
    if (actionSim) {
      const index = Number(actionSim.dataset.simActionIndex);
      const action = state.overview.action_simulations[index] || state.overview.action_simulations[0];
      runQuickScenario(
        {
          scenario_type: index === 0 ? "carrier_underperformance" : index === 1 ? "staffing_shortage" : "storm_region",
          region_or_entity: action.target,
          severity: 4,
        },
        index
      ).catch((error) => {
        showLoader(false);
        document.getElementById("scenarioImpactSummary").innerHTML = `<div class="feed-item"><strong>Simulation error</strong><span>${error.message}</span></div>`;
      });
      return;
    }

    const scenarioChip = event.target.closest("[data-scenario-index]");
    if (scenarioChip) {
      runQuickScenario(
        {
          scenario_type: scenarioChip.dataset.scenarioType,
          region_or_entity: scenarioChip.dataset.scenarioEntity,
          severity: Number(scenarioChip.dataset.scenarioSeverity),
        },
        Number(scenarioChip.dataset.scenarioIndex)
      ).catch((error) => {
        showLoader(false);
        document.getElementById("scenarioImpactSummary").innerHTML = `<div class="feed-item"><strong>Simulation error</strong><span>${error.message}</span></div>`;
      });
      return;
    }

    const exceptionAction = event.target.closest(".exception-action-btn");
    if (exceptionAction) {
      const shipmentId = exceptionAction.dataset.id;
      const action = exceptionAction.dataset.exceptionAction;
      document.getElementById("scenarioImpactSummary").innerHTML = `
        <div class="metric-item"><strong>${action} queued</strong><span>${shipmentId} has been added to the intervention queue for operator review.</span></div>
      `;
      return;
    }

    const prompt = event.target.closest("[data-copilot-prompt]");
    if (prompt) {
      const question = prompt.dataset.copilotPrompt;
      state.copilotOpen = true;
      renderCopilotDock();
      document.getElementById("copilotInput").value = question;
      askCopilot(question).catch((error) => {
        showLoader(false);
        document.getElementById("copilotFeed").innerHTML = `<div class="feed-item"><strong>Copilot error</strong><span>${error.message}</span></div>`;
      });
      return;
    }

  });

  document.getElementById("actionsPanel").addEventListener("click", (event) => {
    const actionButton = event.target.closest(".action-btn");
    if (!actionButton) return;

    const kind = actionButton.dataset.actionKind;
    const label = actionButton.dataset.actionLabel;
    const target = actionButton.dataset.actionTarget;

    if (kind === "simulate_action" || kind === "simulate_decision") {
      runQuickScenario(
        {
          scenario_type: "carrier_underperformance",
          region_or_entity: target,
          severity: 4,
        },
        null
      ).then(() => {
        postActionFeedback(label, `${target} has been simulated and the updated impact is now reflected in the scenario summary.`);
      }).catch((error) => {
        showLoader(false);
        postActionFeedback("Simulation error", error.message);
      });
      return;
    }

    const messages = {
      acknowledge_alert: `${target} has been acknowledged and added to the operator watchlist.`,
      escalate_alert: `${target} has been escalated to the operations escalation queue.`,
      open_playbook: `${target} has opened the linked remediation playbook for action review.`,
      execute_decision: `${target} has been queued for execution and is awaiting operator confirmation.`,
      assign_owner: `${target} has been assigned to the current response owner queue.`,
      trigger_playbook: `${target} automation has been triggered for the current network state.`,
    };

    postActionFeedback(label, messages[kind] || `${target} action has been queued.`);
  });

  document.getElementById("copilotLauncher").addEventListener("click", () => {
    state.copilotOpen = !state.copilotOpen;
    renderCopilotDock();
    if (state.copilotOpen && !document.getElementById("copilotFeed").innerHTML.trim()) {
      document.getElementById("copilotFeed").innerHTML = `<div class="feed-item"><strong>Suggested question</strong><span>Why are delays increasing in the network?</span></div>`;
    }
  });

  document.getElementById("scenarioType").addEventListener("change", updateScenarioEntities);
  document.getElementById("runScenarioBtn").addEventListener("click", runScenario);
  document.getElementById("closeModalBtn").addEventListener("click", () => document.getElementById("shipmentModal").classList.add("hidden"));
  document.getElementById("closeCopilotBtn").addEventListener("click", () => {
    state.copilotOpen = false;
    renderCopilotDock();
  });
  document.getElementById("shipmentModal").addEventListener("click", (event) => {
    if (event.target.id === "shipmentModal") {
      document.getElementById("shipmentModal").classList.add("hidden");
    }
  });
  document.getElementById("copilotModal").addEventListener("click", (event) => {
    if (event.target.id === "copilotModal") {
      state.copilotOpen = false;
      renderCopilotDock();
    }
  });

  document.getElementById("copilotSendBtn").addEventListener("click", () => {
    askCopilot(document.getElementById("copilotInput").value).catch((error) => {
      showLoader(false);
      document.getElementById("copilotFeed").innerHTML = `<div class="feed-item"><strong>Copilot error</strong><span>${error.message}</span></div>`;
    });
  });
  document.getElementById("copilotInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      askCopilot(event.target.value).catch((error) => {
        showLoader(false);
        document.getElementById("copilotFeed").innerHTML = `<div class="feed-item"><strong>Copilot error</strong><span>${error.message}</span></div>`;
      });
    }
  });

  document.getElementById("resetDemoBtn").addEventListener("click", async () => {
    showLoader(true);
    await fetchJSON("/api/demo/reset", { method: "POST" });
    await initializeDashboard();
    showLoader(false);
  });

  document.getElementById("saveLlmSettingsBtn").addEventListener("click", () => {
    showLoader(true);
    saveLlmSettings().catch((error) => updateLlmStatus(error.message, true)).finally(() => showLoader(false));
  });

  document.getElementById("toggleLlmSettingsBtn").addEventListener("click", () => {
    document.getElementById("llmSettingsBody").classList.toggle("hidden");
  });

  document.getElementById("clearLlmSettingsBtn").addEventListener("click", () => {
    showLoader(true);
    clearLlmSettings().catch((error) => updateLlmStatus(error.message, true)).finally(() => showLoader(false));
  });

  document.getElementById("testLlmSettingsBtn").addEventListener("click", () => {
    showLoader(true);
    testLlmSettings().catch((error) => updateLlmStatus(error.message, true)).finally(() => showLoader(false));
  });

  document.getElementById("fileUpload").addEventListener("change", async (event) => {
    if (!event.target.files.length) return;
    const form = new FormData();
    form.append("file", event.target.files[0]);
    showLoader(true);
    await fetchJSON("/api/upload", { method: "POST", body: form });
    await initializeDashboard();
    showLoader(false);
  });
}

async function initializeDashboard() {
  showLoader(true);
  await loadLlmSettings();
  const overview = await fetchJSON("/api/overview");
  state.overview = overview;
  state.shipments = overview.top_shipments;
  state.filteredShipments = overview.top_shipments;
  renderGlobalStatus();
  renderKPIs(overview.kpis);
  renderExecutiveSummary();
  renderCommandSnapshot();
  renderRiskDistribution();
  renderAiActions();
  renderNetworkMap();
  renderScenarioQuick();
  renderExceptionsTable();
  renderReadiness();
  renderShipmentTable(overview.top_shipments);
  renderAlerts();
  renderRegionSeverityBlock();
  renderInsights();
  renderActionsPanel();
  renderAgentStatus();
  renderCopilotDock();
  renderSignalProviders();
  renderNetworkGraph();
  renderValues();
  populateFilters();
  renderCharts();
  document.getElementById("copilotFeed").innerHTML = `<div class="feed-item"><strong>Suggested question</strong><span>Why are delays increasing in the network?</span></div>`;
  showLoader(false);
}

bindEvents();
initializeDashboard().catch((error) => {
  showLoader(false);
  document.getElementById("executiveSummaryMini").textContent = `Dashboard failed to load: ${error.message}`;
});
