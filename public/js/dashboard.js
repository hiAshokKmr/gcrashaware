// Mission Control Dashboard JavaScript
let socket = null;
let currentIncidents = [];
let currentCampaigns = [];
let currentLeads = [];
let currentEmails = [];
let activeCorridorIndex = 0;

document.addEventListener('DOMContentLoaded', () => {
  initRadarCanvas();
  initWebSocket();
  fetchInitialData();
  window.addEventListener('resize', () => drawAtlantaRadar());
});

// WebSocket Telemetry Connection
function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}`;
  socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    console.log('[WebSocket] Connected to GCrashAware Telemetry Stream');
  };

  socket.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleSocketMessage(msg);
    } catch (err) {
      console.error('Error handling socket message:', err);
    }
  };

  socket.onclose = () => {
    console.warn('[WebSocket] Disconnected. Reconnecting in 3s...');
    setTimeout(initWebSocket, 3000);
  };
}

function handleSocketMessage(msg) {
  if (msg.type === 'INCIDENT_TRIGGERED') {
    fetchInitialData();
  } else if (msg.type === 'NEW_LEAD' || msg.type === 'CALL_UPDATED') {
    fetchInitialData();
  } else if (msg.type === 'DEMO_PROGRESS') {
    highlightPipelineStep(msg.data.stepNum, msg.data.title, msg.data.details);
  } else if (msg.type === 'DEMO_COMPLETED') {
    document.getElementById('pipelineStatusText').innerHTML = '<span style="color:var(--accent-green);">✓ 10-Day Acceptance Demo Completed Successfully</span>';
    fetchInitialData();
  }
}

// Initial Data Fetching
async function fetchInitialData() {
  try {
    const [statusRes, incRes, campRes, leadsRes, emailsRes] = await Promise.all([
      fetch('/api/status').then(r => r.json()),
      fetch('/api/incidents').then(r => r.json()),
      fetch('/api/campaigns').then(r => r.json()),
      fetch('/api/leads').then(r => r.json()),
      fetch('/api/emails').then(r => r.json())
    ]);

    currentIncidents = incRes;
    currentCampaigns = campRes;
    currentLeads = leadsRes;
    currentEmails = emailsRes;

    updateMetrics(statusRes.metrics);
    renderCampaigns(currentCampaigns);
    renderLeads(currentLeads);
    renderEmails(currentEmails);
    drawAtlantaRadar();
  } catch (err) {
    console.error('Error fetching initial data:', err);
  }
}

function updateMetrics(metrics) {
  if (!metrics) return;
  document.getElementById('metricIncidents').textContent = metrics.activeIncidents || 0;
  document.getElementById('metricCampaigns').textContent = metrics.totalCampaigns || 0;
  document.getElementById('metricLeads').textContent = metrics.totalLeads || 0;
  document.getElementById('metricCalls').textContent = currentLeads.filter(l => l.type === 'vapi_call').length;
  document.getElementById('metricEmails').textContent = metrics.dispatchedEmails || 0;
  document.getElementById('campaignsCountBadge').textContent = `${metrics.totalCampaigns || 0} active`;
}

// Render Campaigns List
function renderCampaigns(campaigns) {
  const container = document.getElementById('adCampaignList');
  if (!campaigns || campaigns.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); font-size:0.82rem; text-align:center; padding:20px;">No active campaigns. Trigger an incident to generate geo ad sets.</p>`;
    return;
  }

  container.innerHTML = campaigns.slice(0, 4).map(c => `
    <div class="ad-card">
      <div class="ad-card-header">
        <span class="ad-platform-tag ${c.platform === 'Google Ads' ? 'tag-google' : 'tag-meta'}">${c.platform}</span>
        <span style="font-size:0.72rem; color:var(--accent-green); font-weight:700;">● ${c.status} (${c.radius_miles} mi)</span>
      </div>
      <div class="ad-headline">${c.headline}</div>
      <div class="ad-body">${c.body}</div>
      <div class="ad-metrics">
        <span>Budget: <strong>$${c.daily_budget}/day</strong></span>
        <span>Impressions: <strong>${c.impressions}</strong></span>
        <span>Clicks: <strong>${c.clicks}</strong></span>
      </div>
    </div>
  `).join('');
}

// Render Leads Table
function renderLeads(leads) {
  const tbody = document.getElementById('leadsTableBody');
  if (!leads || leads.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:24px;">No leads recorded yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = leads.map(lead => {
    const isVapi = lead.type === 'vapi_call';
    const typeBadge = isVapi
      ? `<span class="status-badge status-call">📞 Vapi Voice Call</span>`
      : `<span class="status-badge status-new">📝 Web Intake Form</span>`;

    const timeStr = new Date(lead.created_at || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return `
      <tr>
        <td>${typeBadge}</td>
        <td><strong>${lead.name}</strong></td>
        <td>${lead.phone}</td>
        <td>${lead.incident_location}</td>
        <td>
          <span style="font-family:monospace; font-size:0.7rem; color:var(--accent-blue);">${lead.trusted_form_cert || 'Verified'}</span>
        </td>
        <td><span class="status-badge status-urgent">${lead.status || 'New'}</span></td>
        <td style="color:var(--text-muted);">${timeStr}</td>
      </tr>
    `;
  }).join('');
}

// Render Dispatched Emails
function renderEmails(emails) {
  const container = document.getElementById('emailLogsList');
  if (!emails || emails.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); font-size:0.82rem; text-align:center; padding:20px;">No support handoff emails dispatched yet.</p>`;
    return;
  }

  container.innerHTML = emails.slice(0, 3).map(e => `
    <div class="email-log-item">
      <div class="email-log-header">
        <span>To: <strong>${e.recipient}</strong></span>
        <span>${new Date(e.sent_at).toLocaleTimeString()}</span>
      </div>
      <div class="email-subject">${e.subject}</div>
      <div class="email-preview-box">${e.body}</div>
    </div>
  `).join('');
}

// Radar Canvas Rendering (Metro Atlanta Highway Network)
function initRadarCanvas() {
  const canvas = document.getElementById('atlantaRadarCanvas');
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
}

function drawAtlantaRadar() {
  const canvas = document.getElementById('atlantaRadarCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.getBoundingClientRect().width;
  const h = canvas.getBoundingClientRect().height;

  ctx.clearRect(0, 0, w, h);

  const cx = w / 2;
  const cy = h / 2;

  // Background Grid & Radar Sweep Rings
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.08)';
  ctx.lineWidth = 1;

  for (let r = 40; r <= 160; r += 40) {
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Crosshairs
  ctx.beginPath();
  ctx.moveTo(cx, 10); ctx.lineTo(cx, h - 10);
  ctx.moveTo(10, cy); ctx.lineTo(w - 10, cy);
  ctx.stroke();

  // Draw I-285 Perimeter Loop (Ellipse)
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.4)';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.ellipse(cx, cy, 95, 75, 0, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
  ctx.font = '10px Inter';
  ctx.fillText('I-285 Perimeter', cx + 60, cy - 65);

  // Draw I-85 Diagonal (NE to SW)
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(cx - 130, cy + 110);
  ctx.lineTo(cx + 130, cy - 110);
  ctx.stroke();
  ctx.fillText('I-85 North (Gwinnett)', cx + 75, cy - 115);

  // Draw I-75 (NW to SE)
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.35)';
  ctx.beginPath();
  ctx.moveTo(cx - 120, cy - 110);
  ctx.lineTo(cx + 110, cy + 110);
  ctx.stroke();
  ctx.fillText('I-75 (Marietta / Cobb)', cx - 115, cy - 115);

  // Draw GA-400 (North from Perimeter)
  ctx.strokeStyle = 'rgba(245, 158, 11, 0.35)';
  ctx.beginPath();
  ctx.moveTo(cx, cy - 75);
  ctx.lineTo(cx + 10, cy - 135);
  ctx.stroke();
  ctx.fillText('GA-400 (Alpharetta)', cx + 15, cy - 130);

  // Downtown Connector Center
  ctx.fillStyle = '#38bdf8';
  ctx.beginPath();
  ctx.arc(cx, cy, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillText('Downtown Atlanta', cx - 45, cy + 16);

  // Draw Active Incidents and 7.5-mile Geofences
  const activeInc = currentIncidents.filter(i => i.active === 1);
  activeInc.forEach((inc, idx) => {
    // Map GPS roughly to canvas relative to Atlanta center (33.75, -84.38)
    const latDiff = (inc.lat - 33.75) * 850;
    const lngDiff = (inc.lng - (-84.38)) * 850;

    const ix = cx + lngDiff;
    const iy = cy - latDiff;

    // Draw 7.5-mile Geofence Radius Circle
    ctx.strokeStyle = 'rgba(245, 158, 11, 0.5)';
    ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(ix, iy, 42, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Incident Marker Dot
    ctx.fillStyle = '#ef4444';
    ctx.beginPath();
    ctx.arc(ix, iy, 6, 0, Math.PI * 2);
    ctx.fill();

    // Label
    ctx.fillStyle = '#fef08a';
    ctx.font = 'bold 10px Inter';
    ctx.fillText(`🚨 ${inc.corridor || 'Incident'} (7.5 mi radius)`, ix + 10, iy - 6);
  });
}

// Actions & Handlers
async function triggerSimulatedIncident() {
  const sel = document.getElementById('corridorSelect');
  const presetIndex = sel ? parseInt(sel.value) : 0;

  try {
    const res = await fetch('/api/incidents/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ presetIndex })
    });
    const incident = await res.json();
    fetchInitialData();
  } catch (err) {
    alert('Failed to simulate incident: ' + err.message);
  }
}

function changeActiveCorridor(val) {
  activeCorridorIndex = parseInt(val);
  triggerSimulatedIncident();
}

// Vapi Voice Station Interactive Simulation
async function executeVapiSimulation() {
  const scenarioIndex = parseInt(document.getElementById('vapiScenarioSelect').value || '0');
  const transcriptWin = document.getElementById('transcriptWindow');
  const summaryBox = document.getElementById('callSummaryBox');
  const summaryText = document.getElementById('callSummaryText');

  transcriptWin.innerHTML = '<div style="color:var(--accent-amber); text-align:center;">Connecting inbound call to Sarah (AI Assistant)...</div>';
  summaryBox.style.display = 'none';

  try {
    const scenariosRes = await fetch('/api/calls/scenarios');
    const scenarios = await scenariosRes.json();
    const scenario = scenarios[scenarioIndex] || scenarios[0];

    // Animate dialogue step-by-step
    transcriptWin.innerHTML = '';
    for (const d of scenario.dialogue) {
      await new Promise(r => setTimeout(r, 800));
      const msgDiv = document.createElement('div');
      msgDiv.className = 'transcript-message';
      const isAssistant = d.speaker.toLowerCase() === 'assistant';
      msgDiv.innerHTML = `
        <span class="transcript-speaker ${isAssistant ? 'assistant' : 'caller'}">${d.speaker} (${isAssistant ? 'AI Agent' : scenario.callerName})</span>
        <span class="transcript-text">${d.text}</span>
      `;
      transcriptWin.appendChild(msgDiv);
      transcriptWin.scrollTop = transcriptWin.scrollHeight;
    }

    // Call complete webhook dispatch
    const res = await fetch('/api/vapi/simulate-call', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenarioIndex })
    });
    const result = await res.json();

    summaryBox.style.display = 'block';
    summaryText.innerHTML = `<strong>Priority: ${result.priority}</strong> - ${result.summary}<br><span style="font-size:0.75rem; color:var(--accent-blue);">Dispatched to support@georgiacrashhelp.com</span>`;
    fetchInitialData();
  } catch (err) {
    alert('Voice simulation error: ' + err.message);
  }
}

// 1-Click Acceptance Demo Runner
async function runAcceptanceDemo() {
  const btn = document.getElementById('runDemoBtn');
  const statusText = document.getElementById('pipelineStatusText');
  btn.disabled = true;
  btn.innerHTML = '<span>Executing 10-Day POC Acceptance Cycle...</span>';

  // Reset steps
  for (let i = 1; i <= 6; i++) {
    const el = document.getElementById(`step${i}`);
    if (el) {
      el.className = 'step-card';
    }
  }

  try {
    const res = await fetch('/api/demo/run-acceptance', { method: 'POST' });
    const result = await res.json();

    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
      <span>Run 10-Day POC Acceptance Demo</span>`;
  } catch (err) {
    alert('Acceptance demo failed: ' + err.message);
    btn.disabled = false;
  }
}

function highlightPipelineStep(stepNum, title, details) {
  const statusText = document.getElementById('pipelineStatusText');
  statusText.innerHTML = `<span style="color:var(--accent-amber);">▶ Executing Step ${stepNum}: ${title}</span>`;

  for (let i = 1; i < stepNum; i++) {
    const el = document.getElementById(`step${i}`);
    if (el) el.className = 'step-card completed';
  }

  const activeEl = document.getElementById(`step${stepNum}`);
  if (activeEl) activeEl.className = 'step-card active';
}

// n8n Modal Inspector
async function openN8nModal() {
  document.getElementById('n8nModal').classList.add('active');
  showWorkflowCode(1);
}

function closeN8nModal() {
  document.getElementById('n8nModal').classList.remove('active');
}

async function showWorkflowCode(tabIndex) {
  const codeBlock = document.getElementById('n8nCodeBlock');
  const tab1 = document.getElementById('tabWorkflow1');
  const tab2 = document.getElementById('tabWorkflow2');

  if (tabIndex === 1) {
    tab1.style.background = 'rgba(56,189,248,0.2)'; tab1.style.color = '#fff';
    tab2.style.background = 'rgba(255,255,255,0.05)'; tab2.style.color = 'var(--text-secondary)';
    try {
      const res = await fetch('/workflows/n8n-incident-to-ads.json');
      const json = await res.json();
      codeBlock.textContent = JSON.stringify(json, null, 2);
    } catch {
      codeBlock.textContent = '// n8n Blueprint: GDOT Incident -> Geofence -> Google/Meta Ads API';
    }
  } else {
    tab2.style.background = 'rgba(56,189,248,0.2)'; tab2.style.color = '#fff';
    tab1.style.background = 'rgba(255,255,255,0.05)'; tab1.style.color = 'var(--text-secondary)';
    try {
      const res = await fetch('/workflows/n8n-lead-intake-vapi-handoff.json');
      const json = await res.json();
      codeBlock.textContent = JSON.stringify(json, null, 2);
    } catch {
      codeBlock.textContent = '// n8n Blueprint: Web Intake & Vapi Webhook -> Compliance -> Email Handoff';
    }
  }
}
