const { query, run } = require('../db/database');
const config = require('../config');

class AdsService {
  async getCampaigns(incidentId = null) {
    if (incidentId) {
      return await query(`SELECT * FROM campaigns WHERE incident_id = ? ORDER BY created_at DESC`, [incidentId]);
    }
    return await query(`SELECT * FROM campaigns ORDER BY created_at DESC LIMIT 50`);
  }

  async launchGeoCampaignsForIncident(incident) {
    const campaignsCreated = [];
    const radius = incident.radius_miles || config.DEFAULT_RADIUS_MILES;
    const corridorName = incident.corridor || 'Metro Atlanta Highway';

    // 1. Create Google Ads Campaign Template
    const googleId = `gads_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    const googleHeadline = `${incident.highway || 'Georgia'} Incident Support`;
    const googleBody = config.AD_TEMPLATES.google.description1
      .replace('{corridor}', corridorName);

    await run(
      `INSERT INTO campaigns (id, incident_id, platform, campaign_name, status, target_lat, target_lng, radius_miles, headline, body, daily_budget, impressions, clicks)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        googleId,
        incident.id,
        'Google Ads',
        `Search_Radius_${incident.highway || 'GA'}_${radius}mi_${incident.id.slice(-4)}`,
        'ACTIVE_SERVING',
        incident.lat,
        incident.lng,
        radius,
        googleHeadline,
        googleBody,
        config.AD_TEMPLATES.google.dailyBudget,
        Math.floor(Math.random() * 45) + 10,
        Math.floor(Math.random() * 8) + 1
      ]
    );

    // 2. Create Meta (Facebook / Instagram) Ads Campaign Template
    const metaId = `meta_${Date.now()}_${Math.floor(Math.random() * 1000)}`;
    const metaHeadline = config.AD_TEMPLATES.meta.headline.replace('{corridor}', corridorName);
    const metaBody = config.AD_TEMPLATES.meta.body;

    await run(
      `INSERT INTO campaigns (id, incident_id, platform, campaign_name, status, target_lat, target_lng, radius_miles, headline, body, daily_budget, impressions, clicks)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [
        metaId,
        incident.id,
        'Meta Ads',
        `Social_Feed_${incident.highway || 'GA'}_${radius}mi_${incident.id.slice(-4)}`,
        'ACTIVE_SERVING',
        incident.lat,
        incident.lng,
        radius,
        metaHeadline,
        metaBody,
        config.AD_TEMPLATES.meta.dailyBudget,
        Math.floor(Math.random() * 120) + 30,
        Math.floor(Math.random() * 15) + 2
      ]
    );

    campaignsCreated.push(
      { id: googleId, platform: 'Google Ads', status: 'ACTIVE_SERVING', radius_miles: radius, headline: googleHeadline },
      { id: metaId, platform: 'Meta Ads', status: 'ACTIVE_SERVING', radius_miles: radius, headline: metaHeadline }
    );

    console.log(`[Ads Engine] Launched ${campaignsCreated.length} Geo-Targeted Campaigns for incident ${incident.id} (${radius} mi radius)`);
    return campaignsCreated;
  }

  async pauseCampaign(campaignId) {
    await run(`UPDATE campaigns SET status = 'PAUSED' WHERE id = ?`, [campaignId]);
    return { id: campaignId, status: 'PAUSED' };
  }
}

module.exports = new AdsService();
