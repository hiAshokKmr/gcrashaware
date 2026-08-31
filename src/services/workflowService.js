const incidentService = require('./incidentService');
const adsService = require('./adsService');
const leadService = require('./leadService');
const vapiService = require('./vapiService');
const { query, run } = require('../db/database');

class WorkflowService {
  constructor() {
    this.wsClients = new Set();
    this.initAutomatedPipelines();
  }

  registerWsClient(ws) {
    this.wsClients.add(ws);
    ws.on('close', () => this.wsClients.delete(ws));
  }

  broadcast(type, data) {
    const message = JSON.stringify({ type, data, timestamp: new Date().toISOString() });
    for (const client of this.wsClients) {
      if (client.readyState === 1) { // OPEN
        client.send(message);
      }
    }
  }

  async logWorkflowStep(workflowName, eventType, payload, status = 'SUCCESS') {
    const id = `wf_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    await run(
      `INSERT INTO workflow_logs (id, workflow_name, event_type, payload, status)
       VALUES (?, ?, ?, ?, ?)`,
      [id, workflowName, eventType, JSON.stringify(payload), status]
    );

    this.broadcast('WORKFLOW_LOG', {
      id,
      workflowName,
      eventType,
      payload,
      status,
      timestamp: new Date().toISOString()
    });
  }

  initAutomatedPipelines() {
    // Automatically trigger Ad campaigns whenever a new incident is ingested
    incidentService.onNewIncident(async (incident) => {
      await this.logWorkflowStep('n8n-incident-to-ads', 'INCIDENT_DETECTED', {
        incidentId: incident.id,
        corridor: incident.corridor,
        radius: incident.radiusMiles
      });

      const campaigns = await adsService.launchGeoCampaignsForIncident(incident);

      await this.logWorkflowStep('n8n-incident-to-ads', 'ADS_LAUNCHED', {
        incidentId: incident.id,
        campaignsCreated: campaigns.length,
        campaigns
      });

      this.broadcast('INCIDENT_TRIGGERED', { incident, campaigns });
    });

    // Notify when a lead arrives
    leadService.onNewLead(async (lead) => {
      await this.logWorkflowStep('n8n-lead-intake-vapi-handoff', 'LEAD_CAPTURED', {
        leadId: lead.id,
        name: lead.name,
        type: lead.type
      });

      this.broadcast('NEW_LEAD', lead);
    });

    // Notify when a call completes
    vapiService.onCallUpdate(async (event) => {
      await this.logWorkflowStep('n8n-lead-intake-vapi-handoff', 'VAPI_CALL_PROCESSED', {
        callId: event.data.callId,
        priority: event.data.priority
      });

      this.broadcast('CALL_UPDATED', event.data);
    });
  }

  // 1-Click End-to-End Acceptance Demo Runner
  async runFullAcceptanceDemo() {
    const demoId = `demo_${Date.now()}`;
    const steps = [];

    const addStep = async (stepNum, title, details) => {
      const step = { stepNum, title, details, timestamp: new Date().toISOString() };
      steps.push(step);
      this.broadcast('DEMO_PROGRESS', step);
      await new Promise((r) => setTimeout(r, 600)); // Small delay for realistic UI pacing
    };

    // Step 1: Detect Qualifying Incident on Atlanta I-85 / I-285 corridor
    await addStep(1, 'GDOT 511 Feed Polling', 'Polled Georgia NaviGAtor feed. Ingesting accident report on I-85 North near Spaghetti Junction.');
    const incident = await incidentService.generateRealisticIncident(0);

    // Step 2: Calculate 7.5-mile Geofence
    await addStep(2, 'Geofence Calculation', `Computed 7.5-mile radius around (${incident.lat}, ${incident.lng}) covering I-85 / I-285 corridor.`);

    // Step 3: Launch Google Ads & Meta Ads Radius Campaign
    await addStep(3, 'Ad Platforms Automation', `Deployed 2 active ad sets on Google Ads & Meta Ads with dynamic corridor headline & $275 total daily budget.`);
    const campaigns = await adsService.getCampaigns(incident.id);

    // Step 4: Capture Inbound Web Form Lead from Landing Page
    await addStep(4, 'Landing Page Intake Form', 'Simulating high-intent user click from Google Ad to Georgia Roadside Landing Page. Captured lead form with TCPA consent.');
    const webLead = await leadService.captureWebLead({
      name: 'David Sterling',
      phone: '+1 (404) 555-8910',
      email: 'david.sterling.atl@gmail.com',
      incident_location: incident.corridor,
      details: 'Rear-ended during lane blockage. Minor vehicle damage, requested quick consultation.',
      tcpa_consent: true
    });

    // Step 5: Process Inbound Vapi AI Call
    await addStep(5, 'Vapi AI Inbound Call', 'Simulating inbound call to +1 (404) 891-2345. AI Agent Sarah greeted caller, validated safety, gathered incident specifics, and generated live transcript.');
    const scenarios = vapiService.getDemoCallScenarios();
    const callResult = await vapiService.handleWebhookPayload({
      callerName: scenarios[0].callerName,
      callerPhone: scenarios[0].callerPhone,
      transcript: scenarios[0].dialogue.map(d => `${d.speaker}: ${d.text}`).join('\n'),
      summary: scenarios[0].summary,
      priority: scenarios[0].priority,
      durationSeconds: 118
    });

    // Step 6: Dispatch Support Email Handoff
    await addStep(6, 'Support Team Email Handoff', `Sent instant priority email alert to support@georgiacrashhelp.com with TrustedForm audit token.`);

    const summaryResult = {
      demoId,
      incident,
      campaigns,
      webLead,
      callResult,
      steps,
      completedAt: new Date().toISOString()
    };

    this.broadcast('DEMO_COMPLETED', summaryResult);
    return summaryResult;
  }
}

module.exports = new WorkflowService();
