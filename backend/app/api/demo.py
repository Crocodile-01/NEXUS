"""
NEXUS Interactive Demo — Standalone HTML user interface for testing and
demonstrating Website Reconnaissance and Intelligence Engine 1.0 capabilities.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["Demo"])

DEMO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NEXUS — Intelligence Engine Demo</title>
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --accent: #58a6ff;
      --accent-hover: #79c0ff;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --success: #3fb950;
      --warning: #d29922;
      --danger: #f85149;
      --badge-bg: #21262d;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    header {
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .logo {
      font-size: 24px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .logo span { color: var(--accent); }
    .badge-mode {
      background: #1f2937;
      color: #93c5fd;
      border: 1px solid #3b82f6;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
    }
    .card-title {
      font-size: 16px;
      font-weight: 600;
      color: #fff;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .form-grid {
      display: grid;
      grid-template-columns: 1fr auto auto auto auto;
      gap: 12px;
      align-items: end;
    }
    @media (max-width: 900px) {
      .form-grid { grid-template-columns: 1fr; }
    }
    label {
      display: block;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    input[type="text"], select, input[type="number"] {
      width: 100%;
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: #fff;
      padding: 10px 12px;
      font-size: 14px;
      outline: none;
    }
    input[type="text"]:focus, select:focus, input[type="number"]:focus {
      border-color: var(--accent);
    }
    button {
      background: var(--accent);
      color: #0d1117;
      border: none;
      font-weight: 600;
      border-radius: 6px;
      padding: 10px 20px;
      font-size: 14px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: background-color 0.2s;
    }
    button:hover { background: var(--accent-hover); }
    button:disabled { background: var(--border); color: var(--text-muted); cursor: not-allowed; }
    .examples {
      margin-top: 10px;
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
      font-size: 13px;
      color: var(--text-muted);
    }
    .chip {
      background: var(--badge-bg);
      border: 1px solid var(--border);
      color: var(--accent);
      padding: 2px 8px;
      border-radius: 12px;
      cursor: pointer;
      font-size: 12px;
    }
    .chip:hover { border-color: var(--accent); }
    .status-bar {
      display: none;
      padding: 12px 16px;
      border-radius: 6px;
      margin-bottom: 20px;
      font-size: 14px;
    }
    .status-bar.loading {
      background: #1f2937;
      border: 1px solid #3b82f6;
      color: #93c5fd;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .status-bar.error {
      background: #3c1618;
      border: 1px solid var(--danger);
      color: #fca5a5;
    }
    .spinner {
      width: 18px;
      height: 18px;
      border: 2px solid rgba(147, 197, 253, 0.3);
      border-top-color: #93c5fd;
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 20px;
    }
    .metric-card {
      background: #0d1117;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
    }
    .metric-label { font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
    .metric-val { font-size: 20px; font-weight: 700; color: #fff; }
    .timing-breakdown {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
      font-size: 12px;
    }
    .timing-pill {
      background: #21262d;
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 2px 8px;
      color: #8b949e;
    }
    .timing-pill span { color: #fff; font-weight: 600; }
    .tag-grid {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .tech-tag {
      background: #1c2128;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 12px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
    }
    .tech-cat {
      font-size: 10px;
      text-transform: uppercase;
      background: #238636;
      color: #fff;
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 700;
    }
    .tech-conf { font-size: 11px; color: var(--text-muted); }
    .findings-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      margin-top: 8px;
    }
    .findings-table th, .findings-table td {
      border: 1px solid var(--border);
      padding: 8px 12px;
      text-align: left;
    }
    .findings-table th {
      background: #0d1117;
      color: var(--text-muted);
      font-weight: 600;
    }
    .badge-conf {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .badge-fact { background: #1f3a24; color: #3fb950; border: 1px solid #238636; }
    .badge-inference { background: #382c16; color: #d29922; border: 1px solid #9e6a03; }
    .badge-unverified { background: #3a1d1d; color: #f85149; border: 1px solid #da3633; }
    .badge-corroborated { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; font-size: 10px; margin-left: 6px; padding: 1px 5px; border-radius: 3px; }
    .chain-box {
      background: #0d1117;
      border: 1px solid #30363d;
      border-left: 3px solid #58a6ff;
      padding: 8px 12px;
      margin-bottom: 8px;
      border-radius: 4px;
      font-family: monospace;
      font-size: 12px;
      color: #79c0ff;
    }
    .gap-item {
      padding: 6px 12px;
      background: #1c2128;
      border-left: 3px solid #d29922;
      margin-bottom: 6px;
      border-radius: 4px;
      font-size: 13px;
    }
    .tab-nav {
      display: flex;
      border-bottom: 1px solid var(--border);
      margin-bottom: 16px;
      gap: 4px;
      overflow-x: auto;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      font-size: 14px;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      white-space: nowrap;
    }
    .tab-btn.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
      font-weight: 600;
    }
    pre {
      background: #0d1117;
      border: 1px solid var(--border);
      padding: 12px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 12px;
      color: #e6edf3;
      max-height: 500px;
    }
    #resultsSection { display: none; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="logo">
        <span>⚡ NEXUS</span> Website Intelligence & Intelligence Engine
      </div>
      <div>
        <span class="badge-mode">Mode: PASSIVE_PUBLIC</span>
      </div>
    </header>

    <div class="card">
      <div class="card-title">🔍 Target Entity & Intelligence Research</div>
      <form id="investigateForm" onsubmit="event.preventDefault(); runInvestigation();">
        <div class="form-grid">
          <div>
            <label for="targetInput">Target (URL, Domain, or Name)</label>
            <input type="text" id="targetInput" placeholder="https://www.python.org" required value="https://www.python.org" />
          </div>
          <div>
            <label for="engineModeSelect">Investigation Engine</label>
            <select id="engineModeSelect">
              <option value="intelligence" selected>Intelligence Engine 1.0 (Multi-Source)</option>
              <option value="website">Website Recon (Vertical Slice)</option>
            </select>
          </div>
          <div>
            <label for="maxDepthInput">Max Depth</label>
            <input type="number" id="maxDepthInput" min="1" max="4" value="2" />
          </div>
          <div>
            <label for="maxQueriesInput">Max Queries</label>
            <input type="number" id="maxQueriesInput" min="3" max="30" value="15" />
          </div>
          <div>
            <label>&nbsp;</label>
            <button type="submit" id="submitBtn">
              <span id="btnText">Investigate</span>
            </button>
          </div>
        </div>
      </form>

      <div class="examples">
        <span>Quick presets:</span>
        <span class="chip" onclick="setTarget('https://www.python.org')">python.org</span>
        <span class="chip" onclick="setTarget('https://www.djangoproject.com')">djangoproject.com</span>
        <span class="chip" onclick="setTarget('https://example.com')">example.com</span>
        <span class="chip" onclick="setTarget('https://www.wikipedia.org')">wikipedia.org</span>
      </div>
    </div>

    <div id="statusBar" class="status-bar"></div>

    <div id="resultsSection">
      <!-- Metrics overview -->
      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-label">Status</div>
          <div class="metric-val" id="metricStatus" style="color: var(--success);">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Canonical Domain</div>
          <div class="metric-val" id="metricDomain" style="font-size: 16px;">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Corroborated Findings</div>
          <div class="metric-val" id="metricCorroborated" style="color: var(--accent);">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Entities Discovered</div>
          <div class="metric-val" id="metricEntities">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Relationships Discovered</div>
          <div class="metric-val" id="metricRelationships">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Sources Consulted</div>
          <div class="metric-val" id="metricSources" style="font-size: 16px;">-</div>
        </div>
      </div>

      <!-- Tab Navigation -->
      <div class="tab-nav">
        <button class="tab-btn active" onclick="switchTab('summary')">Executive Intelligence</button>
        <button class="tab-btn" onclick="switchTab('findings')">Findings & Corroboration</button>
        <button class="tab-btn" onclick="switchTab('graph')">Relationship Chains</button>
        <button class="tab-btn" onclick="switchTab('tech')">Technology Stack</button>
        <button class="tab-btn" onclick="switchTab('gaps')">Research Gaps</button>
        <button class="tab-btn" onclick="switchTab('raw')">Raw JSON</button>
      </div>

      <!-- Tab 1: Executive Summary -->
      <div id="tabSummary" class="card">
        <div class="card-title">📝 Executive Summary & Intelligence Synthesis</div>
        <p id="summaryText" style="margin-bottom: 16px; font-size: 14px; line-height: 1.6;"></p>

        <div class="card-title" style="margin-top: 16px;">🏢 Organization Profile</div>
        <div style="font-size: 13px; display: grid; grid-template-columns: 140px 1fr; gap: 8px;">
          <span style="color: var(--text-muted);">Name:</span><span id="orgName" style="font-weight: 600;"></span>
          <span style="color: var(--text-muted);">Website:</span><span id="orgUrl"></span>
          <span style="color: var(--text-muted);">Description:</span><span id="orgDesc"></span>
          <span style="color: var(--text-muted);">Aliases:</span><span id="orgAliases"></span>
        </div>
      </div>

      <!-- Tab 2: Findings -->
      <div id="tabFindings" class="card" style="display: none;">
        <div class="card-title">🛡️ Key Findings & Corroboration Provenance</div>
        <table class="findings-table">
          <thead>
            <tr>
              <th style="width: 45%;">Claim</th>
              <th style="width: 15%;">Classification</th>
              <th style="width: 10%;">Confidence</th>
              <th style="width: 30%;">Why / Corroborating Sources</th>
            </tr>
          </thead>
          <tbody id="findingsBody"></tbody>
        </table>
      </div>

      <!-- Tab 3: Relationship Graph & Chains -->
      <div id="tabGraph" class="card" style="display: none;">
        <div class="card-title">🔗 Discovered Multi-Hop Relationship Chains</div>
        <div id="chainsContainer" style="margin-bottom: 16px;"></div>
        <div class="card-title" style="margin-top: 16px;">🌐 Entity Relationships</div>
        <div id="relationshipsList" style="font-size: 13px;"></div>
      </div>

      <!-- Tab 4: Technologies -->
      <div id="tabTech" class="card" style="display: none;">
        <div class="card-title">⚙️ Detected Technologies</div>
        <div class="tag-grid" id="techList" style="margin-bottom: 16px;"></div>
        <div class="card-title" style="margin-top: 16px;">🌐 Digital Infrastructure & Subdomains</div>
        <div id="infrastructureList" style="font-size: 13px;"></div>
      </div>

      <!-- Tab 5: Research Gaps -->
      <div id="tabGaps" class="card" style="display: none;">
        <div class="card-title">⚠️ Identified Research Gaps & Unverified Dimensions</div>
        <div id="gapsList"></div>
      </div>

      <!-- Tab 6: Raw JSON -->
      <div id="tabRaw" class="card" style="display: none;">
        <div class="card-title">📦 Complete API Response</div>
        <pre id="rawJson"></pre>
      </div>
    </div>
  </div>

  <script>
    function setTarget(url) {
      document.getElementById('targetInput').value = url;
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('#tabSummary, #tabFindings, #tabGraph, #tabTech, #tabGaps, #tabRaw').forEach(el => el.style.display = 'none');
      
      const tabMap = {
        'summary': 'tabSummary',
        'findings': 'tabFindings',
        'graph': 'tabGraph',
        'tech': 'tabTech',
        'gaps': 'tabGaps',
        'raw': 'tabRaw'
      };
      
      document.getElementById(tabMap[tabId]).style.display = 'block';
      event.target.classList.add('active');
    }

    async function runInvestigation() {
      const target = document.getElementById('targetInput').value.trim();
      const engineMode = document.getElementById('engineModeSelect').value;
      const maxDepth = parseInt(document.getElementById('maxDepthInput').value, 10) || 2;
      const maxQueries = parseInt(document.getElementById('maxQueriesInput').value, 10) || 15;
      
      const submitBtn = document.getElementById('submitBtn');
      const btnText = document.getElementById('btnText');
      const statusBar = document.getElementById('statusBar');
      const resultsSection = document.getElementById('resultsSection');
      
      submitBtn.disabled = true;
      btnText.textContent = 'Investigating...';
      statusBar.className = 'status-bar loading';
      statusBar.innerHTML = '<div class="spinner"></div><span>Formulating research questions, orchestrating multi-source collection, expanding entities, and verifying corroboration...</span>';
      statusBar.style.display = 'flex';
      resultsSection.style.display = 'none';

      try {
        let endpoint = '/api/v1/investigations/intelligence';
        let payload = {
          target: target,
          target_type: "domain",
          max_depth: maxDepth,
          max_source_queries: maxQueries,
          allow_expansion: true
        };

        if (engineMode === 'website') {
          endpoint = '/api/v1/investigations/website';
          payload = {
            target: target,
            max_pages: maxDepth,
            enrich: true
          };
        }

        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
        }

        const data = await response.json();
        renderResults(data, engineMode);
        statusBar.style.display = 'none';
        resultsSection.style.display = 'block';
      } catch (err) {
        statusBar.className = 'status-bar error';
        statusBar.innerHTML = `<strong>Investigation Failed:</strong> ${err.message}`;
        statusBar.style.display = 'block';
      } finally {
        submitBtn.disabled = false;
        btnText.textContent = 'Investigate';
      }
    }

    function renderResults(data, mode) {
      document.getElementById('metricStatus').textContent = (data.status || 'COMPLETED').toUpperCase();
      document.getElementById('metricStatus').style.color = data.status === 'completed' ? 'var(--success)' : 'var(--danger)';
      document.getElementById('metricDomain').textContent = data.canonical_domain || data.target;
      document.getElementById('metricCorroborated').textContent = data.corroborated_findings_count || (data.findings_count || 0);
      document.getElementById('metricEntities').textContent = data.entities_count || 0;
      document.getElementById('metricRelationships').textContent = data.relationships_count || 0;
      document.getElementById('metricSources').textContent = (data.sources_consulted || []).length;

      const r = data.report || {};
      document.getElementById('summaryText').textContent = r.executive_intelligence || r.executive_summary || 'No summary available.';
      
      const org = r.target_profile || r.organization_profile || {};
      document.getElementById('orgName').textContent = org.name || '-';
      document.getElementById('orgUrl').textContent = org.website_url || '-';
      document.getElementById('orgDesc').textContent = org.description || 'N/A';
      document.getElementById('orgAliases').textContent = (org.aliases || []).join(', ') || 'None observed';

      // Discovered Chains
      const chainsContainer = document.getElementById('chainsContainer');
      chainsContainer.innerHTML = '';
      const chains = org.discovered_relationship_chains || [];
      if (chains.length > 0) {
        chains.forEach(ch => {
          chainsContainer.innerHTML += `<div class="chain-box">${ch}</div>`;
        });
      } else {
        chainsContainer.innerHTML = '<span style="color: var(--text-muted);">No multi-hop chains observed.</span>';
      }

      // Relationships
      const relsList = document.getElementById('relationshipsList');
      relsList.innerHTML = '';
      const rels = r.relationship_intelligence || r.relationships || [];
      if (rels.length > 0) {
        rels.slice(0, 15).forEach(rel => {
          const s = rel.subject || rel.source_entity;
          const p = rel.predicate || rel.relationship_type;
          const o = rel.object || rel.target_entity;
          relsList.innerHTML += `<div style="padding: 4px 0; border-bottom: 1px solid #21262d;"><strong>${s}</strong> → <em>${p}</em> → <strong>${o}</strong> <span style="color: var(--text-muted); font-size: 11px;">(${(rel.confidence * 100).toFixed(0)}% conf)</span></div>`;
        });
      }

      // Findings
      const findingsBody = document.getElementById('findingsBody');
      findingsBody.innerHTML = '';
      const findings = r.key_findings || r.findings || [];
      findings.forEach(f => {
        let badgeClass = 'badge-unverified';
        const clsVal = (f.classification && f.classification.value) ? f.classification.value : f.classification;
        if (clsVal === 'FACT') badgeClass = 'badge-fact';
        else if (clsVal === 'SUPPORTED_INFERENCE') badgeClass = 'badge-inference';

        const corroborationTag = f.is_corroborated ? '<span class="badge-corroborated">CORROBORATED</span>' : '';
        const whyNote = f.why || f.supporting_snippet || 'N/A';

        findingsBody.innerHTML += `
          <tr>
            <td><strong>${f.claim}</strong></td>
            <td><span class="badge-conf ${badgeClass}">${clsVal}</span>${corroborationTag}</td>
            <td>${((f.confidence_score || f.confidence || 0) * 100).toFixed(0)}%</td>
            <td style="color: var(--text-muted); font-size: 12px;">${whyNote}</td>
          </tr>
        `;
      });

      // Technologies
      const techList = document.getElementById('techList');
      techList.innerHTML = '';
      const techs = r.technology_intelligence || r.technologies || [];
      if (techs.length > 0) {
        techs.forEach(t => {
          techList.innerHTML += `
            <div class="tech-tag">
              <span class="tech-cat">${t.category}</span>
              <strong>${t.name}</strong>
              <span class="tech-conf">${(t.confidence * 100).toFixed(0)}%</span>
            </div>
          `;
        });
      }

      // Digital Infrastructure
      const infraList = document.getElementById('infrastructureList');
      infraList.innerHTML = '';
      const infra = r.digital_infrastructure || {};
      const subs = infra.subdomains || [];
      if (subs.length > 0) {
        infraList.innerHTML = `<strong>Observed Subdomains (${subs.length}):</strong> ` + subs.join(', ');
      } else {
        infraList.innerHTML = '<span style="color: var(--text-muted);">No public subdomains recorded.</span>';
      }

      // Research Gaps
      const gapsList = document.getElementById('gapsList');
      gapsList.innerHTML = '';
      const gaps = r.research_gaps || [];
      if (gaps.length > 0) {
        gaps.forEach(g => {
          gapsList.innerHTML += `<div class="gap-item">⚠️ ${g}</div>`;
        });
      } else {
        gapsList.innerHTML = '<div style="color: var(--success);">No major research gaps identified.</div>';
      }

      // Raw JSON
      document.getElementById('rawJson').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
"""


@router.get("/demo", response_class=HTMLResponse, summary="Serve interactive demo UI")
async def get_demo_ui():
    return HTMLResponse(content=DEMO_HTML, status_code=200)
