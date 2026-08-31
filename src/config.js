// Configuration for GCrashAware Georgia / Metro Atlanta POC
module.exports = {
  PORT: process.env.PORT || 3000,
  DEFAULT_RADIUS_MILES: 7.5,
  INCIDENT_POLL_INTERVAL_MS: 15000,
  SUPPORT_EMAIL: process.env.SUPPORT_EMAIL || 'support@georgiacrashhelp.com',
  TRACKED_PHONE_NUMBER: process.env.TRACKED_PHONE_NUMBER || '+1 (404) 891-2345',
  
  // Georgia Highway Corridors & Metro Atlanta Anchor Coordinates
  CORRIDORS: [
    { name: 'I-85 North (Gwinnett/Buford Hwy)', lat: 33.9189, lng: -84.2542, highway: 'I-85' },
    { name: 'I-85 South (Airport/College Park)', lat: 33.6558, lng: -84.4444, highway: 'I-85' },
    { name: 'I-75 North (Cobb/Marietta)', lat: 33.9526, lng: -84.5499, highway: 'I-75' },
    { name: 'I-75 South (Clayton/Morrow)', lat: 33.5843, lng: -84.3396, highway: 'I-75' },
    { name: 'I-285 Perimeter West (Cobb/Fulton)', lat: 33.8052, lng: -84.4983, highway: 'I-285' },
    { name: 'I-285 Perimeter East (DeKalb/Tucker)', lat: 33.8447, lng: -84.2592, highway: 'I-285' },
    { name: 'I-20 East (Decatur/Lithonia)', lat: 33.7225, lng: -84.2255, highway: 'I-20' },
    { name: 'I-20 West (Six Flags/Douglasville)', lat: 33.7547, lng: -84.5518, highway: 'I-20' },
    { name: 'GA-400 North (Sandy Springs/Alpharetta)', lat: 34.0255, lng: -84.3512, highway: 'GA-400' },
    { name: 'Downtown Connector (I-75/85 Midtown)', lat: 33.7749, lng: -84.3888, highway: 'I-75/85' }
  ],

  // Predefined Ad Templates for Google & Meta
  AD_TEMPLATES: {
    google: {
      headlinePart1: "Georgia Highway Incident Assistance",
      headlinePart2: "24/7 Roadside & Legal Advice",
      description1: "Involved in an accident on {corridor}? Know your Georgia legal rights & rapid response options.",
      description2: "Free instant consultation with local Atlanta injury & roadside specialists. Call {phone} now.",
      cpcBid: 4.50,
      dailyBudget: 150.00
    },
    meta: {
      headline: "Accident Support for {corridor} Motorists",
      body: "Immediate guidance following a collision in Metro Atlanta. Free case evaluation and towing coordination. Speak with a Georgia advocate today.",
      callToAction: "CALL_NOW",
      dailyBudget: 125.00
    }
  },

  // Vapi AI Script Definition & Qualification Checklist
  VAPI_AGENT: {
    assistantName: "Georgia Rapid Response Assistant (Sarah)",
    voice: "jennifer",
    firstMessage: "Thank you for calling Georgia Incident Support. My name is Sarah. I'm an AI assistant on a recorded line. Are you or anyone at the scene in need of emergency medical attention, or is everyone safe?",
    systemPrompt: `You are Sarah, a compassionate, professional intake coordinator for Georgia Accident & Roadside Assistance.
Your primary goals:
1. Confirm if emergency services (911) are needed immediately. If yes, instruct them to hang up and dial 911.
2. Inquire about the accident location in Georgia (highway corridor or intersection like I-85, I-285, I-75).
3. Gather basic details: vehicle drivability, injuries, whether police report was filed.
4. Assure them of help, explain next steps for medical / legal / towing support, and confirm their contact number for human specialist handoff.
5. Summarize the call and flag priority (High/Medium/Low).`,
    qualificationCriteria: [
      "No active life threat (or 911 already notified)",
      "Incident occurred in Georgia jurisdiction",
      "Vehicle damaged or personal discomfort reported",
      "Seeking legal representation, insurance claim advice, or towing assistance",
      "Willing to receive specialist callback"
    ]
  }
};
