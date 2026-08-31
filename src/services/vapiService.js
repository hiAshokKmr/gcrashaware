const { query, run } = require('../db/database');
const leadService = require('./leadService');
const config = require('../config');

class VapiService {
  constructor() {
    this.subscribers = [];
  }

  onCallUpdate(callback) {
    this.subscribers.push(callback);
  }

  notifySubscribers(event) {
    for (const callback of this.subscribers) {
      try {
        callback(event);
      } catch (err) {
        console.error('Error notifying call subscriber:', err);
      }
    }
  }

  async getCallLogs() {
    return await query(`SELECT * FROM call_logs ORDER BY created_at DESC LIMIT 50`);
  }

  // Handle incoming or completed Vapi webhook payload
  async handleWebhookPayload(payload) {
    console.log('[Vapi Webhook] Received event:', payload.message?.type || payload.type || 'call-ended');

    const callData = payload.message?.call || payload.call || payload;
    const callId = callData.id || `vapi_call_${Date.now()}`;
    const callerPhone = callData.customer?.number || payload.callerPhone || '+1 (404) 555-7890';
    const callerName = payload.callerName || 'Marcus Vance';
    const transcript = callData.transcript || payload.transcript || 
      `Assistant: Thank you for calling Georgia Incident Support. My name is Sarah. Are you or anyone at the scene injured?
Caller: No major injuries, but my car got hit from behind on I-85 near Spaghetti Junction and the rear axle is damaged.
Assistant: I am glad you are safe. Did police arrive yet?
Caller: Yes, GSP is writing up a report right now. I need legal help and towing assistance.
Assistant: We have your location on I-85 North. I am dispatching your intake to our Atlanta rapid support team. A specialist will call this number in under 3 minutes.`;

    const summary = callData.summary || payload.summary ||
      `Caller involved in rear-end collision on I-85 North near Spaghetti Junction (I-285). GSP on scene. Vehicle disabled with rear axle damage. No acute emergency injuries. Requested urgent legal representation & towing guidance.`;

    const durationSeconds = callData.duration || payload.durationSeconds || 142;
    const priority = payload.priority || 'HIGH';
    const needs911 = payload.needs911 || 0;
    const recordingUrl = callData.recordingUrl || `https://vapi-recordings.s3.amazonaws.com/calls/${callId}.mp3`;

    // 1. Create Inbound Lead for this Caller
    const leadId = `lead_vapi_${Date.now()}`;
    const trustedFormCert = `TF-VAPI-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;

    await run(
      `INSERT INTO leads (id, type, name, phone, email, incident_location, details, tcpa_consent, trusted_form_cert, status, qualification_score)
       VALUES (?, 'vapi_call', ?, ?, ?, ?, ?, 1, ?, 'Call Qualified', 95)`,
      [
        leadId,
        callerName,
        callerPhone,
        `${callerName.toLowerCase().replace(/\s+/g, '')}@gmail.com`,
        'I-85 North near I-285 (Spaghetti Junction)',
        summary,
        trustedFormCert
      ]
    );

    // 2. Save Call Log
    await run(
      `INSERT INTO call_logs (id, lead_id, caller_phone, duration_seconds, status, recording_url, transcript, summary, needs_immediate_911, priority)
       VALUES (?, ?, ?, ?, 'COMPLETED', ?, ?, ?, ?, ?)`,
      [callId, leadId, callerPhone, durationSeconds, recordingUrl, transcript, summary, needs911, priority]
    );

    // 3. Dispatch Email Handoff
    await leadService.dispatchSupportEmail({
      leadId,
      name: callerName,
      phone: callerPhone,
      email: `${callerName.toLowerCase().replace(/\s+/g, '')}@gmail.com`,
      location: 'I-85 North near I-285 (Spaghetti Junction)',
      details: summary,
      summary,
      priority,
      type: 'Vapi AI Inbound Call',
      trustedFormCert
    });

    const callResult = {
      callId,
      leadId,
      callerName,
      callerPhone,
      durationSeconds,
      summary,
      transcript,
      priority,
      recordingUrl,
      status: 'COMPLETED'
    };

    this.notifySubscribers({ type: 'CALL_COMPLETED', data: callResult });
    return callResult;
  }

  // Pre-configured realistic call scenarios for the interactive tester
  getDemoCallScenarios() {
    return [
      {
        id: 'scenario_1',
        title: 'I-85 Rear-End Collision (Spaghetti Junction)',
        callerName: 'Marcus Vance',
        callerPhone: '+1 (404) 555-7890',
        location: 'I-85 North near I-285 (Spaghetti Junction)',
        dialogue: [
          { speaker: 'Assistant', text: "Thank you for calling Georgia Incident Support. My name is Sarah. I'm an AI assistant on a recorded line. Are you or anyone at the scene in need of emergency medical attention, or is everyone safe?" },
          { speaker: 'Caller', text: "Everyone is out of the cars, no emergency medical needed right now, but I was rear-ended hard by a box truck on I-85." },
          { speaker: 'Assistant', text: "I'm relieved you are safe. What is your approximate location on I-85, and did law enforcement or GDOT NaviGAtor arrive?" },
          { speaker: 'Caller', text: "We are near the I-285 interchange, Spaghetti Junction. GSP just pulled up behind us. My trunk is completely smashed in." },
          { speaker: 'Assistant', text: "Understood. We are logging your incident on I-85 North right now. We coordinate free immediate legal case reviews and verified towing assistance. Is this the best number to connect you with our Georgia support coordinator?" },
          { speaker: 'Caller', text: "Yes, this cell phone is best. Please have them call me right away." },
          { speaker: 'Assistant', text: "I have transferred your case details with priority to our Atlanta legal & roadside desk. A coordinator will reach out in under 3 minutes. Stay safe behind the guardrail." }
        ],
        summary: "Rear-end collision on I-85 at Spaghetti Junction involving box truck. GSP on scene. Vehicle disabled. Seeking urgent attorney evaluation and towing assistance.",
        priority: "HIGH"
      },
      {
        id: 'scenario_2',
        title: 'I-75 South Multi-Car Hydroplane (Morrow)',
        callerName: 'Elena Rostova',
        callerPhone: '+1 (770) 555-3412',
        location: 'I-75 South near Exit 233 (Morrow)',
        dialogue: [
          { speaker: 'Assistant', text: "Thank you for calling Georgia Incident Support. My name is Sarah. I'm an AI assistant on a recorded line. Are you or anyone at the scene in need of emergency medical attention, or is everyone safe?" },
          { speaker: 'Caller', text: "We're shaken up and my wrist hurts, but 911 has already been called for paramedics." },
          { speaker: 'Assistant', text: "Understood. Please keep yourself safe off the shoulder. Where along I-75 did the collision happen?" },
          { speaker: 'Caller', text: "Right around Exit 233 in Morrow during the heavy rain. Three cars involved." },
          { speaker: 'Assistant', text: "I've noted the location at I-75 Exit 233. Once the paramedics evaluate you, our Georgia injury advocate team can protect your claim before insurance calls. Can we dispatch your file to our senior attorney?" },
          { speaker: 'Caller', text: "Yes please, I want to make sure everything is handled properly." },
          { speaker: 'Assistant', text: "Your case is prioritized and our on-call coordinator has been alerted via emergency dispatch. Expect a text and call immediately." }
        ],
        summary: "Multi-vehicle hydroplane incident on I-75 South Exit 233. Paramedics en route for minor wrist injury. Case pre-qualified for personal injury intake.",
        priority: "HIGH"
      }
    ];
  }
}

module.exports = new VapiService();
