"""
NEXUS Interactive Demo — Standalone HTML user interface for testing and
demonstrating Website / Domain Intelligence capabilities.
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
  <title>NEXUS — Website Intelligence Demo</title>
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
      grid-template-columns: 1fr auto auto auto;
      gap: 12px;
      align-items: end;
    }
    @media (max-width: 768px) {
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
    .checkbox-group {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 0;
      font-size: 14px;
      cursor: pointer;
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
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 20px;
      font-size: 14px;
    }
    .status-bar.loading { display: flex; align-items: center; gap: 12px; background: #1c2738; border: 1px solid #2b4c7e; color: #79c0ff; }
    .status-bar.error { display: block; background: #351515; border: 1px solid #6e2525; color: #ff7b72; }
    .spinner {
      border: 2px solid rgba(121, 192, 255, 0.2);
      border-left-color: var(--accent);
      border-radius: 50%;
      width: 18px;
      height: 18px;
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
    .badge-high { background: #238636; color: #fff; }
    .badge-inferred { background: #9e6a03; color: #fff; }
    .badge-unverified { background: #6e7681; color: #fff; }
    .tab-nav {
      display: flex;
      border-bottom: 1px solid var(--border);
      margin-bottom: 16px;
      gap: 8px;
    }
    .tab-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      padding: 8px 16px;
      font-size: 14px;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      border-radius: 0;
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
        <span>⚡ NEXUS</span> Website Intelligence
      </div>
      <div>
        <span class="badge-mode">Mode: PASSIVE_PUBLIC</span>
      </div>
    </header>

    <div class="card">
      <div class="card-title">🔍 Target Website / Domain Research</div>
      <form id="investigateForm" onsubmit="event.preventDefault(); runInvestigation();">
        <div class="form-grid">
          <div>
            <label for="targetInput">Target URL or Domain</label>
            <input type="text" id="targetInput" placeholder="https://www.python.org" required value="https://www.python.org" />
          </div>
          <div>
            <label for="maxPagesInput">Max Pages (1–10)</label>
            <input type="number" id="maxPagesInput" min="1" max="10" value="2" />
          </div>
          <div>
            <label>&nbsp;</label>
            <label class="checkbox-group">
              <input type="checkbox" id="enrichInput" checked />
              <span>OSINT Enrichment</span>
            </label>
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
        <span class="chip" onclick="setTarget('https://www.python.org', 2, true)">python.org</span>
        <span class="chip" onclick="setTarget('https://www.djangoproject.com', 2, true)">djangoproject.com</span>
        <span class="chip" onclick="setTarget('https://example.com', 1, false)">example.com</span>
        <span class="chip" onclick="setTarget('https://www.wikipedia.org', 1, true)">wikipedia.org</span>
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
          <div class="metric-label">Pages Crawled</div>
          <div class="metric-val" id="metricEvidence">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Entities Discovered</div>
          <div class="metric-val" id="metricEntities">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Verified Findings</div>
          <div class="metric-val" id="metricFindings">-</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Execution Time</div>
          <div class="metric-val" id="metricTotalTime" style="color: var(--accent);">-</div>
        </div>
      </div>

      <!-- Timing Pills -->
      <div class="card" style="padding: 12px 16px;">
        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 6px; font-weight: 600;">LIFECYCLE TIMINGS</div>
        <div class="timing-breakdown" id="timingContainer"></div>
      </div>

      <!-- Tab Navigation -->
      <div class="tab-nav">
        <button class="tab-btn active" onclick="switchTab('summary')">Executive Summary</button>
        <button class="tab-btn" onclick="switchTab('tech')">Technologies</button>
        <button class="tab-btn" onclick="switchTab('findings')">Findings & Confidence</button>
        <button class="tab-btn" onclick="switchTab('entities')">Entities & Relationships</button>
        <button class="tab-btn" onclick="switchTab('raw')">Raw JSON</button>
      </div>

      <!-- Tab 1: Executive Summary -->
      <div id="tabSummary" class="card">
        <div class="card-title">📝 Executive Summary</div>
        <p id="summaryText" style="margin-bottom: 16px; font-size: 14px;"></p>

        <div class="card-title" style="margin-top: 16px;">🏢 Organization Profile</div>
        <div style="font-size: 13px; display: grid; grid-template-columns: 140px 1fr; gap: 8px;">
          <span style="color: var(--text-muted);">Organization:</span><span id="orgName" style="font-weight: 600;"></span>
          <span style="color: var(--text-muted);">Website:</span><span id="orgUrl"></span>
          <span style="color: var(--text-muted);">Description:</span><span id="orgDesc"></span>
          <span style="color: var(--text-muted);">Sources:</span><span id="orgSources"></span>
        </div>
      </div>

      <!-- Tab 2: Technologies -->
      <div id="tabTech" class="card" style="display: none;">
        <div class="card-title">⚙️ Detected Technologies</div>
        <div class="tag-grid" id="techList"></div>
      </div>

      <!-- Tab 3: Findings -->
      <div id="tabFindings" class="card" style="display: none;">
        <div class="card-title">🛡️ Verified Findings & Provenance</div>
        <table class="findings-table">
          <thead>
            <tr>
              <th>Claim</th>
              <th>Classification</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody id="findingsBody"></tbody>
        </table>
      </div>

      <!-- Tab 4: Entities & Relationships -->
      <div id="tabEntities" class="card" style="display: none;">
        <div class="card-title">👥 Discovered Entities</div>
        <div id="entitiesList" style="margin-bottom: 16px; font-size: 13px;"></div>
        <div class="card-title">🔗 Discovered Relationships</div>
        <div id="relationshipsList" style="font-size: 13px;"></div>
      </div>

      <!-- Tab 5: Raw JSON -->
      <div id="tabRaw" class="card" style="display: none;">
        <div class="card-title">📦 Complete API Response</div>
        <pre id="rawJson"></pre>
      </div>
    </div>
  </div>

  <script>
    function setTarget(url, maxPages, enrich) {
      document.getElementById('targetInput').value = url;
      document.getElementById('maxPagesInput').value = maxPages;
      document.getElementById('enrichInput').checked = enrich;
    }

    function switchTab(tabId) {
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      document.querySelectorAll('#tabSummary, #tabTech, #tabFindings, #tabEntities, #tabRaw').forEach(el => el.style.display = 'none');
      
      const tabMap = {
        'summary': 'tabSummary',
        'tech': 'tabTech',
        'findings': 'tabFindings',
        'entities': 'tabEntities',
        'raw': 'tabRaw'
      };
      
      document.getElementById(tabMap[tabId]).style.display = 'block';
      event.target.classList.add('active');
    }

    async function runInvestigation() {
      const target = document.getElementById('targetInput').value.trim();
      const maxPages = parseInt(document.getElementById('maxPagesInput').value, 10) || 2;
      const enrich = document.getElementById('enrichInput').checked;
      
      const submitBtn = document.getElementById('submitBtn');
      const btnText = document.getElementById('btnText');
      const statusBar = document.getElementById('statusBar');
      const resultsSection = document.getElementById('resultsSection');
      
      submitBtn.disabled = true;
      btnText.textContent = 'Investigating...';
      statusBar.className = 'status-bar loading';
      statusBar.innerHTML = '<div class="spinner"></div><span>Crawling target, extracting DOM evidence, passively detecting tech stack, and querying public OSINT...</span>';
      statusBar.style.display = 'flex';
      resultsSection.style.display = 'none';

      try {
        const response = await fetch('/api/v1/investigations/website', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            target: target,
            max_pages: maxPages,
            enrich: enrich
          })
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({ detail: response.statusText }));
          throw new Error(errData.detail || `Server returned HTTP ${response.status}`);
        }

        const data = await response.json();
        renderResults(data);
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

    function renderResults(data) {
      document.getElementById('metricStatus').textContent = data.status.toUpperCase();
      document.getElementById('metricStatus').style.color = data.status === 'completed' ? 'var(--success)' : 'var(--danger)';
      document.getElementById('metricDomain').textContent = data.canonical_domain;
      document.getElementById('metricEvidence').textContent = data.evidence_count;
      document.getElementById('metricEntities').textContent = data.entities_count;
      document.getElementById('metricFindings').textContent = data.findings_count;
      
      const timings = data.timings || {};
      document.getElementById('metricTotalTime').textContent = `${(timings.total_ms || 0).toFixed(0)} ms`;

      // Timings pills
      document.getElementById('timingContainer').innerHTML = `
        <div class="timing-pill">Validation: <span>${timings.target_validation_ms || 0} ms</span></div>
        <div class="timing-pill">Crawl & Fetch: <span>${timings.crawl_ms || 0} ms</span></div>
        <div class="timing-pill">DOM & Entity Extraction: <span>${timings.extraction_ms || 0} ms</span></div>
        <div class="timing-pill">OSINT Enrichment: <span>${timings.enrichment_ms || 0} ms</span></div>
        <div class="timing-pill">Total Duration: <span>${timings.total_ms || 0} ms</span></div>
      `;

      // Report content
      const r = data.report || {};
      document.getElementById('summaryText').textContent = r.executive_summary || 'No summary available.';
      
      const org = r.organization_profile || {};
      document.getElementById('orgName').textContent = org.name || '-';
      document.getElementById('orgUrl').textContent = org.website_url || '-';
      document.getElementById('orgDesc').textContent = org.description || 'N/A';
      document.getElementById('orgSources').textContent = (r.sources_consulted || []).join(', ') || 'Direct DOM';

      // Technologies
      const techList = document.getElementById('techList');
      techList.innerHTML = '';
      if (r.technologies && r.technologies.length > 0) {
        r.technologies.forEach(t => {
          techList.innerHTML += `
            <div class="tech-tag">
              <span class="tech-cat">${t.category}</span>
              <strong>${t.name}</strong>
              <span class="tech-conf">${(t.confidence * 100).toFixed(0)}% conf</span>
            </div>
          `;
        });
      } else {
        techList.innerHTML = '<span style="color: var(--text-muted);">No explicit technologies detected.</span>';
      }

      // Findings
      const findingsBody = document.getElementById('findingsBody');
      findingsBody.innerHTML = '';
      if (r.findings && r.findings.length > 0) {
        r.findings.forEach(f => {
          let badgeClass = 'badge-conf badge-high';
          if (f.classification === 'INFERRED') badgeClass = 'badge-conf badge-inferred';
          if (f.classification === 'UNVERIFIED') badgeClass = 'badge-conf badge-unverified';
          findingsBody.innerHTML += `
            <tr>
              <td>${f.claim}</td>
              <td><span class="${badgeClass}">${f.classification}</span></td>
              <td>${(f.confidence_score * 100).toFixed(0)}%</td>
            </tr>
          `;
        });
      } else {
        findingsBody.innerHTML = '<tr><td colspan="3" style="color: var(--text-muted);">No findings produced.</td></tr>';
      }

      // Entities
      const entitiesList = document.getElementById('entitiesList');
      entitiesList.innerHTML = '';
      if (r.people_and_organizations && r.people_and_organizations.length > 0) {
        r.people_and_organizations.slice(0, 15).forEach(e => {
          entitiesList.innerHTML += `<div style="padding: 4px 0;">• <strong>${e.name}</strong> <span style="color: var(--text-muted);">(${e.entity_type}${e.role_or_title ? ' - ' + e.role_or_title : ''})</span></div>`;
        });
      } else {
        entitiesList.innerHTML = '<span style="color: var(--text-muted);">No entities extracted.</span>';
      }

      // Relationships
      const relationshipsList = document.getElementById('relationshipsList');
      relationshipsList.innerHTML = '';
      if (r.relationships && r.relationships.length > 0) {
        r.relationships.slice(0, 15).forEach(rel => {
          relationshipsList.innerHTML += `<div style="padding: 4px 0;">• <strong>${rel.source_entity}</strong> → <em>${rel.relationship_type}</em> → <strong>${rel.target_entity}</strong> <span style="color: var(--text-muted);">(${rel.supporting_evidence || ''})</span></div>`;
        });
      } else {
        relationshipsList.innerHTML = '<span style="color: var(--text-muted);">No relationships extracted.</span>';
      }

      // Raw JSON
      document.getElementById('rawJson').textContent = JSON.stringify(data, null, 2);
    }
  </script>
</body>
</html>
"""


@router.get("/demo", response_class=HTMLResponse, summary="Interactive Website Intelligence Demo UI")
@router.get("/demo/", response_class=HTMLResponse, include_in_schema=False)
async def demo_page() -> HTMLResponse:
    """Serve standalone interactive HTML demonstration for Website Intelligence."""
    return HTMLResponse(content=DEMO_HTML)
