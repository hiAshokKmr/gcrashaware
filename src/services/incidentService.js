const { query, run } = require('../db/database');
const config = require('../config');

// Calculate bounding box and circle properties for a given lat, lng and radius in miles
function calculateGeofence(lat, lng, radiusMiles = config.DEFAULT_RADIUS_MILES) {
  // 1 degree latitude ~ 69 miles
  const latDelta = radiusMiles / 69.0;
  // 1 degree longitude ~ 69 miles * cos(lat)
  const lngDelta = radiusMiles / (69.0 * Math.cos(lat * (Math.PI / 180)));

  return {
    center: { lat, lng },
    radiusMiles,
    radiusMeters: Math.round(radiusMiles * 1609.34),
    bbox: {
      minLat: Number((lat - latDelta).toFixed(5)),
      maxLat: Number((lat + latDelta).toFixed(5)),
      minLng: Number((lng - lngDelta).toFixed(5)),
      maxLng: Number((lng + lngDelta).toFixed(5))
    }
  };
}

class IncidentService {
  constructor() {
    this.subscribers = [];
  }

  onNewIncident(callback) {
    this.subscribers.push(callback);
  }

  notifySubscribers(incident) {
    for (const callback of this.subscribers) {
      try {
        callback(incident);
      } catch (err) {
        console.error('Error notifying incident subscriber:', err);
      }
    }
  }

  async getAllIncidents(activeOnly = false) {
    const sql = activeOnly
      ? `SELECT * FROM incidents WHERE active = 1 ORDER BY timestamp DESC`
      : `SELECT * FROM incidents ORDER BY timestamp DESC LIMIT 50`;
    return await query(sql);
  }

  async getIncidentById(id) {
    const rows = await query(`SELECT * FROM incidents WHERE id = ?`, [id]);
    return rows.length ? rows[0] : null;
  }

  async createIncident(incidentData) {
    const id = incidentData.id || `inc_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    const source = incidentData.source || 'GDOT_511_NaviGAtor';
    const highway = incidentData.highway || 'I-85';
    const corridor = incidentData.corridor || 'I-85 North near Pleasant Hill Rd';
    const description = incidentData.description || 'Multi-vehicle collision blocking 2 right lanes';
    const severity = incidentData.severity || 'HIGH';
    const lat = incidentData.lat || 33.9189;
    const lng = incidentData.lng || -84.2542;
    const radiusMiles = incidentData.radiusMiles || config.DEFAULT_RADIUS_MILES;

    // Check deduplication: if active incident on same corridor within last 30 minutes
    const existing = await query(
      `SELECT * FROM incidents WHERE corridor = ? AND active = 1 AND datetime(timestamp) > datetime('now', '-30 minutes')`,
      [corridor]
    );

    if (existing.length > 0) {
      console.log(`[Deduplication] Incident on ${corridor} already actively tracked (ID: ${existing[0].id}).`);
      return existing[0];
    }

    await run(
      `INSERT INTO incidents (id, source, highway, corridor, description, severity, lat, lng, radius_miles, active)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)`,
      [id, source, highway, corridor, description, severity, lat, lng, radiusMiles]
    );

    const newIncident = {
      id,
      source,
      highway,
      corridor,
      description,
      severity,
      lat,
      lng,
      radiusMiles,
      geofence: calculateGeofence(lat, lng, radiusMiles),
      active: 1,
      timestamp: new Date().toISOString()
    };

    console.log(`[GDOT Feed] New Qualifying Incident Ingested: ${corridor} (${highway})`);
    this.notifySubscribers(newIncident);
    return newIncident;
  }

  async deactivateIncident(id) {
    await run(`UPDATE incidents SET active = 0 WHERE id = ?`, [id]);
    return { id, active: 0 };
  }

  // Trigger a realistic random or specified highway incident for Georgia demo
  async generateRealisticIncident(presetIndex = null) {
    const corridors = config.CORRIDORS;
    const selected = presetIndex !== null && corridors[presetIndex]
      ? corridors[presetIndex]
      : corridors[Math.floor(Math.random() * corridors.length)];

    const incidentDescriptions = [
      'Multi-vehicle accident blocking center lanes. Emergency units en route.',
      'Overturned truck causing severe rubbernecking and lane closures.',
      'Rear-end collision on exit ramp with vehicle fluid spill.',
      'Stalled vehicle and multi-car pileup during rush hour merge.'
    ];

    const severities = ['MEDIUM', 'HIGH', 'CRITICAL'];
    const desc = incidentDescriptions[Math.floor(Math.random() * incidentDescriptions.length)];
    const severity = severities[Math.floor(Math.random() * severities.length)];

    // Add tiny coordinate variance (+/- 0.008) for realism
    const latOffset = (Math.random() - 0.5) * 0.015;
    const lngOffset = (Math.random() - 0.5) * 0.015;

    return await this.createIncident({
      source: 'GDOT_511_NaviGAtor_Live',
      highway: selected.highway,
      corridor: selected.name,
      description: desc,
      severity,
      lat: Number((selected.lat + latOffset).toFixed(5)),
      lng: Number((selected.lng + lngOffset).toFixed(5)),
      radiusMiles: config.DEFAULT_RADIUS_MILES
    });
  }
}

module.exports = new IncidentService();
