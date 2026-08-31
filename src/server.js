const express = require('express');
const http = require('http');
const path = require('path');
const cors = require('cors');
const { WebSocketServer } = require('ws');
const config = require('./config');
const incidentService = require('./services/incidentService');
const adsService = require('./services/adsService');
const leadService = require('./services/leadService');
const vapiService = require('./services/vapiService');
const workflowService = require('./services/workflowService');
const { query } = require('./db/database');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server });

app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, '../public')));
app.use('/workflows', express.static(path.join(__dirname, '../workflows')));

// WebSocket handler
wss.on('connection', (ws) => {
  console.log('[WebSocket] Client connected to live telemetry stream');
  workflowService.registerWsClient(ws);
  
  // Send initial handshake with summary stats
  ws.send(JSON.stringify({
    type: 'CONNECTED',
    data: {
      serverTime: new Date().toISOString(),
      corridorsCount: config.CORRIDORS.length,
      trackedPhone: config.TRACKED_PHONE_NUMBER
    }
  }));
});

// ---------------- REST API ROUTES ----------------

// System Info
app.get('/api/status', async (req, res) => {
  try {
    const incidents = await incidentService.getAllIncidents();
    const campaigns = await adsService.getCampaigns();
    const leads = await leadService.getAllLeads();
    const emails = await leadService.getEmailLogs();

    res.json({
      status: 'ONLINE',
      platform: 'GCrashAware Georgia 10-Day POC',
      trackedPhone: config.TRACKED_PHONE_NUMBER,
      supportEmail: config.SUPPORT_EMAIL,
      metrics: {
        totalIncidents: incidents.length,
        activeIncidents: incidents.filter(i => i.active === 1).length,
        totalCampaigns: campaigns.length,
        totalLeads: leads.length,
        dispatchedEmails: emails.length
      },
      corridors: config.CORRIDORS
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Incidents
app.get('/api/incidents', async (req, res) => {
  try {
    const incidents = await incidentService.getAllIncidents(req.query.active === 'true');
    res.json(incidents);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/incidents/simulate', async (req, res) => {
  try {
    const presetIndex = req.body.presetIndex !== undefined ? parseInt(req.body.presetIndex) : null;
    const incident = await incidentService.generateRealisticIncident(presetIndex);
    res.json(incident);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/incidents/:id/deactivate', async (req, res) => {
  try {
    const result = await incidentService.deactivateIncident(req.params.id);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Campaigns
app.get('/api/campaigns', async (req, res) => {
  try {
    const campaigns = await adsService.getCampaigns(req.query.incidentId);
    res.json(campaigns);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/campaigns/:id/pause', async (req, res) => {
  try {
    const result = await adsService.pauseCampaign(req.params.id);
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Leads
app.get('/api/leads', async (req, res) => {
  try {
    const leads = await leadService.getAllLeads();
    res.json(leads);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/leads', async (req, res) => {
  try {
    const lead = await leadService.captureWebLead(req.body);
    res.status(201).json(lead);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Vapi Calls & AI Agent
app.get('/api/calls', async (req, res) => {
  try {
    const calls = await vapiService.getCallLogs();
    res.json(calls);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/calls/scenarios', (req, res) => {
  res.json(vapiService.getDemoCallScenarios());
});

app.get('/api/vapi/config', (req, res) => {
  res.json(config.VAPI_AGENT);
});

// Live Vapi Webhook Endpoint (Matches Vapi standard payload format)
app.post('/api/vapi/webhook', async (req, res) => {
  try {
    console.log('[Vapi Webhook] Received external payload:', JSON.stringify(req.body).slice(0, 150));
    const result = await vapiService.handleWebhookPayload(req.body);
    res.json({ status: 'ok', result });
  } catch (err) {
    console.error('Vapi Webhook Error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/api/vapi/simulate-call', async (req, res) => {
  try {
    const scenarios = vapiService.getDemoCallScenarios();
    const scenario = req.body.scenarioIndex !== undefined
      ? scenarios[req.body.scenarioIndex] || scenarios[0]
      : scenarios[0];

    const result = await vapiService.handleWebhookPayload({
      callerName: req.body.callerName || scenario.callerName,
      callerPhone: req.body.callerPhone || scenario.callerPhone,
      transcript: scenario.dialogue.map(d => `${d.speaker}: ${d.text}`).join('\n'),
      summary: scenario.summary,
      priority: scenario.priority,
      durationSeconds: 124
    });

    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Email Audit Logs
app.get('/api/emails', async (req, res) => {
  try {
    const emails = await leadService.getEmailLogs();
    res.json(emails);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Workflow Audit Logs
app.get('/api/workflow/logs', async (req, res) => {
  try {
    const logs = await query(`SELECT * FROM workflow_logs ORDER BY created_at DESC LIMIT 50`);
    res.json(logs);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 1-Click End-to-End Acceptance Demo
app.post('/api/demo/run-acceptance', async (req, res) => {
  try {
    const result = await workflowService.runFullAcceptanceDemo();
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// HTML Page Routes
app.get('/landing', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/landing.html'));
});

app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, '../public/index.html'));
});

server.listen(config.PORT, () => {
  console.log(`====================================================`);
  console.log(`GCrashAware 10-Day POC Platform running on port ${config.PORT}`);
  console.log(`Dashboard: http://localhost:${config.PORT}/`);
  console.log(`Landing Page: http://localhost:${config.PORT}/landing`);
  console.log(`====================================================`);
});
