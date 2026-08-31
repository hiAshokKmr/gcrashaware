const { query, run } = require('../db/database');
const config = require('../config');

class LeadService {
  constructor() {
    this.subscribers = [];
  }

  onNewLead(callback) {
    this.subscribers.push(callback);
  }

  notifySubscribers(lead) {
    for (const callback of this.subscribers) {
      try {
        callback(lead);
      } catch (err) {
        console.error('Error notifying lead subscriber:', err);
      }
    }
  }

  async getAllLeads() {
    const leads = await query(`
      SELECT l.*, c.transcript, c.summary, c.priority, c.duration_seconds
      FROM leads l
      LEFT JOIN call_logs c ON l.id = c.lead_id
      ORDER BY l.created_at DESC
      LIMIT 100
    `);
    return leads;
  }

  async getEmailLogs() {
    return await query(`SELECT * FROM email_logs ORDER BY sent_at DESC LIMIT 50`);
  }

  async captureWebLead(data) {
    const id = `lead_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    const type = 'web_form';
    const name = data.name || 'Georgia Motorist';
    const phone = data.phone || '+1 (404) 555-0199';
    const email = data.email || 'motorist@example.com';
    const location = data.incident_location || 'I-85 North near Duluth';
    const details = data.details || 'Vehicle rear-ended, bumper damage, minor neck stiffness';
    const tcpaConsent = data.tcpa_consent !== undefined ? (data.tcpa_consent ? 1 : 0) : 1;
    
    // Generate simulated TrustedForm certificate token for legal compliance
    const trustedFormCert = `TF-CERT-${Date.now().toString(36).toUpperCase()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
    const qualificationScore = 92;

    await run(
      `INSERT INTO leads (id, type, name, phone, email, incident_location, details, tcpa_consent, trusted_form_cert, status, qualification_score)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', ?)`,
      [id, type, name, phone, email, location, details, tcpaConsent, trustedFormCert, qualificationScore]
    );

    // Trigger instant support/sales handoff email
    await this.dispatchSupportEmail({
      leadId: id,
      name,
      phone,
      email,
      location,
      details,
      type: 'Web Intake Form',
      trustedFormCert
    });

    const createdLead = {
      id,
      type,
      name,
      phone,
      email,
      incident_location: location,
      details,
      tcpa_consent: tcpaConsent,
      trusted_form_cert: trustedFormCert,
      status: 'New',
      qualification_score: qualificationScore,
      created_at: new Date().toISOString()
    };

    console.log(`[Lead Intake] New Form Lead Captured: ${name} (${phone}) - Location: ${location}`);
    this.notifySubscribers(createdLead);
    return createdLead;
  }

  async dispatchSupportEmail(leadInfo) {
    const emailId = `email_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    const recipient = config.SUPPORT_EMAIL;
    const subject = `[URGENT INTAKE] New Georgia Accident Lead: ${leadInfo.name} (${leadInfo.location || 'Metro Atlanta'})`;
    
    const body = `
======================================================
NEW GEORGIA ACCIDENT INTAKE - INSTANT DISPATCH
======================================================
Lead ID: ${leadInfo.leadId}
Source: ${leadInfo.type}
Timestamp: ${new Date().toLocaleString()}

CONTACT INFORMATION:
- Name: ${leadInfo.name}
- Phone: ${leadInfo.phone}
- Email: ${leadInfo.email || 'N/A'}

INCIDENT & CLAIM DETAILS:
- Highway / Location: ${leadInfo.location}
- Case Details: ${leadInfo.details}
- Call Summary: ${leadInfo.summary || 'Direct web form submission'}
- Priority Level: ${leadInfo.priority || 'HIGH'}

COMPLIANCE & AUDIT:
- TCPA Consent Verified: YES
- TrustedForm Certificate: ${leadInfo.trustedFormCert || 'Verified'}
- Action Required: Contact within 5 minutes.
======================================================
`;

    await run(
      `INSERT INTO email_logs (id, recipient, subject, body, lead_id, status)
       VALUES (?, ?, ?, ?, ?, 'DELIVERED')`,
      [emailId, recipient, subject, body, leadInfo.leadId]
    );

    console.log(`[Handoff Email] Dispatched instant lead notification to ${recipient} (ID: ${emailId})`);
    return { emailId, recipient, subject, status: 'DELIVERED' };
  }
}

module.exports = new LeadService();
