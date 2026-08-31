const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const fs = require('fs');

const dataDir = path.join(__dirname, '../../data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, 'gcrashaware.db');
const db = new sqlite3.Database(dbPath);

const initPromise = new Promise((resolve, reject) => {
  db.serialize(() => {
    // Incidents Table
    db.run(`
      CREATE TABLE IF NOT EXISTS incidents (
        id TEXT PRIMARY KEY,
        source TEXT,
        highway TEXT,
        corridor TEXT,
        description TEXT,
        severity TEXT,
        lat REAL,
        lng REAL,
        radius_miles REAL,
        active INTEGER DEFAULT 1,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Dynamic Ad Campaigns Table (Google & Meta)
    db.run(`
      CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY,
        incident_id TEXT,
        platform TEXT,
        campaign_name TEXT,
        status TEXT,
        target_lat REAL,
        target_lng REAL,
        radius_miles REAL,
        headline TEXT,
        body TEXT,
        daily_budget REAL,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(incident_id) REFERENCES incidents(id)
      )
    `);

    // Inbound Leads Table
    db.run(`
      CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY,
        type TEXT,
        name TEXT,
        phone TEXT,
        email TEXT,
        incident_location TEXT,
        details TEXT,
        tcpa_consent INTEGER DEFAULT 1,
        trusted_form_cert TEXT,
        status TEXT DEFAULT 'New',
        qualification_score INTEGER DEFAULT 85,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Vapi AI Call Records & Transcripts
    db.run(`
      CREATE TABLE IF NOT EXISTS call_logs (
        id TEXT PRIMARY KEY,
        lead_id TEXT,
        caller_phone TEXT,
        duration_seconds INTEGER,
        status TEXT,
        recording_url TEXT,
        transcript TEXT,
        summary TEXT,
        needs_immediate_911 INTEGER DEFAULT 0,
        priority TEXT DEFAULT 'Medium',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Notification / Support Handoff Email Log
    db.run(`
      CREATE TABLE IF NOT EXISTS email_logs (
        id TEXT PRIMARY KEY,
        recipient TEXT,
        subject TEXT,
        body TEXT,
        lead_id TEXT,
        status TEXT,
        sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);

    // Workflow Engine Audit Log
    db.run(`
      CREATE TABLE IF NOT EXISTS workflow_logs (
        id TEXT PRIMARY KEY,
        workflow_name TEXT,
        event_type TEXT,
        payload TEXT,
        status TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `, (err) => {
      if (err) {
        console.error('Error initializing tables:', err);
        reject(err);
      } else {
        console.log('Database tables initialized successfully.');
        resolve();
      }
    });
  });
});

async function query(sql, params = []) {
  await initPromise;
  return new Promise((resolve, reject) => {
    db.all(sql, params, (err, rows) => {
      if (err) reject(err);
      else resolve(rows);
    });
  });
}

async function run(sql, params = []) {
  await initPromise;
  return new Promise((resolve, reject) => {
    db.run(sql, params, function (err) {
      if (err) reject(err);
      else resolve({ id: this.lastID, changes: this.changes });
    });
  });
}

module.exports = {
  db,
  initPromise,
  query,
  run
};
