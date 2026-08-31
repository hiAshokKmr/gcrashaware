// Integration Test Suite for GCrashAware 10-Day POC
const incidentService = require('../services/incidentService');
const adsService = require('../services/adsService');
const leadService = require('../services/leadService');
const vapiService = require('../services/vapiService');
const workflowService = require('../services/workflowService');
const { query } = require('../db/database');

async function runTests() {
  console.log('🧪 Starting GCrashAware POC Integration Test Suite...\n');
  let passed = 0;
  let failed = 0;

  function assert(condition, name) {
    if (condition) {
      console.log(`✅ PASS: ${name}`);
      passed++;
    } else {
      console.error(`❌ FAIL: ${name}`);
      failed++;
    }
  }

  try {
    // 1. Test Incident Generation & Geofence Calculation
    console.log('[Test 1] Testing GDOT Incident Poller & Geofencing...');
    const incident = await incidentService.generateRealisticIncident(0);
    assert(incident && incident.id && incident.highway === 'I-85', 'Incident created on I-85 corridor');
    assert(incident.geofence && incident.geofence.radiusMiles === 7.5, '7.5-mile geofence computed correctly');
    assert(incident.geofence.bbox && incident.geofence.bbox.minLat < incident.lat, 'Bounding box latitude delta valid');

    // 2. Test Deduplication
    console.log('\n[Test 2] Testing Incident Deduplication...');
    const duplicate = await incidentService.createIncident({
      corridor: incident.corridor,
      highway: incident.highway,
      lat: incident.lat,
      lng: incident.lng
    });
    assert(duplicate.id === incident.id, 'Deduplication prevented duplicate active incident creation');

    // 3. Test Ad Campaigns Creation
    console.log('\n[Test 3] Testing Dynamic Google & Meta Ads Launch...');
    const campaigns = await adsService.launchGeoCampaignsForIncident(incident);
    assert(campaigns.length === 2, 'Created 2 ad sets (Google Ads + Meta Ads)');
    assert(campaigns[0].platform === 'Google Ads' && campaigns[1].platform === 'Meta Ads', 'Ad platforms configured properly');

    // 4. Test Inbound Web Lead Intake
    console.log('\n[Test 4] Testing Landing Page Web Lead Form Intake...');
    const lead = await leadService.captureWebLead({
      name: 'Integration Test Motorist',
      phone: '+1 (404) 555-9988',
      email: 'testmotorist@example.com',
      incident_location: 'I-85 North near Spaghetti Junction',
      details: 'Test accident report for verification',
      tcpa_consent: true
    });
    assert(lead && lead.id && lead.status === 'New', 'Web lead recorded in SQLite');
    assert(lead.trusted_form_cert && lead.trusted_form_cert.startsWith('TF-CERT-'), 'TrustedForm compliance certificate generated');

    // 5. Test Support Email Handoff
    console.log('\n[Test 5] Testing Support Email Dispatch...');
    const emails = await leadService.getEmailLogs();
    assert(emails.length > 0, 'Support handoff email logged in database');
    assert(emails[0].recipient === 'support@georgiacrashhelp.com', 'Handoff routed to configured support desk');

    // 6. Test Vapi AI Voice Webhook Simulation
    console.log('\n[Test 6] Testing Vapi AI Voice Inbound Webhook & Transcription...');
    const vapiResult = await vapiService.handleWebhookPayload({
      callerName: 'Test Caller Elena',
      callerPhone: '+1 (770) 555-1234',
      transcript: 'Assistant: Are you safe? Caller: Yes, but rear-ended on I-75 Exit 233.',
      summary: 'Accident intake test summary on I-75 South',
      priority: 'HIGH',
      durationSeconds: 95
    });
    assert(vapiResult && vapiResult.callId, 'Vapi call recorded and transcribed');
    assert(vapiResult.priority === 'HIGH', 'Call priority tagged as HIGH');

    // 7. Test 1-Click Acceptance Demo Full Cycle
    console.log('\n[Test 7] Testing 1-Click End-to-End Acceptance Demo Engine...');
    const demoResult = await workflowService.runFullAcceptanceDemo();
    assert(demoResult && demoResult.steps && demoResult.steps.length === 6, 'All 6 acceptance demo pipeline steps completed');

    console.log(`\n========================================`);
    console.log(`🏁 Test Summary: ${passed} Passed, ${failed} Failed`);
    console.log(`========================================\n`);

    if (failed > 0) {
      process.exit(1);
    } else {
      process.exit(0);
    }
  } catch (err) {
    console.error('Unexpected error during tests:', err);
    process.exit(1);
  }
}

runTests();
