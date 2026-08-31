import logging
import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

SUPPORT_EMAIL_RECIPIENTS = getattr(
    settings,
    'SUPPORT_EMAIL_RECIPIENTS',
    ['support@example.com']
)
DEFAULT_FROM_EMAIL = getattr(
    settings,
    'DEFAULT_FROM_EMAIL',
    'alerts@georgiacrashhelp.com'
)
N8N_INCIDENT_WEBHOOK_URL = getattr(
    settings,
    'N8N_INCIDENT_WEBHOOK_URL',
    'http://localhost:5678/webhook/incident-ingest'
)


def send_lead_handoff_email(lead_instance):
    """
    Renders and dispatches a structured HTML alert email to the human sales/support team.
    Supports both FormLead and CallLead instances.
    """
    from .models import FormLead, CallLead

    is_form = isinstance(lead_instance, FormLead)
    is_call = isinstance(lead_instance, CallLead)

    if is_form:
        lead_type = "Web Intake Form"
        name = lead_instance.full_name
        phone = lead_instance.phone_number
        email = lead_instance.email or "Not Provided"
        location = lead_instance.incident.city_area if lead_instance.incident else "Direct Landing Page Ingest"
        details = lead_instance.message or "No additional notes"
        trustedform_url = lead_instance.trustedform_cert_url or "Verified via TCPA consent token"
        subject = f"[URGENT INTAKE] New Georgia Accident Form Lead: {name} ({location})"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; }}
          .container {{ max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
          .header {{ background: #0f172a; color: #f8fafc; padding: 18px 24px; }}
          .header h2 {{ margin: 0; font-size: 18px; color: #f59e0b; }}
          .content {{ padding: 24px; }}
          .section {{ margin-bottom: 18px; }}
          .label {{ font-weight: bold; color: #64748b; font-size: 12px; text-transform: uppercase; }}
          .value {{ font-size: 15px; color: #0f172a; margin-top: 2px; }}
          .badge {{ display: inline-block; background: #dcfce7; color: #166534; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
          .footer {{ background: #f8fafc; padding: 14px 24px; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        </style></head>
        <body>
          <div class="container">
            <div class="header">
              <h2>🚨 New Georgia Accident Intake (Web Form)</h2>
              <p style="margin: 4px 0 0 0; font-size: 13px; color: #94a3b8;">Voluntary Inbound Consultation Request</p>
            </div>
            <div class="content">
              <div class="section">
                <div class="label">Contact Name</div>
                <div class="value"><strong>{name}</strong></div>
              </div>
              <div class="section">
                <div class="label">Phone Number</div>
                <div class="value"><a href="tel:{phone}" style="color: #2563eb; font-weight: bold; font-size: 16px;">{phone}</a></div>
              </div>
              <div class="section">
                <div class="label">Email Address</div>
                <div class="value">{email}</div>
              </div>
              <div class="section">
                <div class="label">Incident Location</div>
                <div class="value">{location}</div>
              </div>
              <div class="section">
                <div class="label">Consumer Message / Notes</div>
                <div class="value" style="background:#f1f5f9; padding: 10px; border-radius: 6px;">{details}</div>
              </div>
              <div class="section">
                <div class="label">Compliance & TCPA Certificate</div>
                <div class="value">
                  <span class="badge">✓ TCPA Consent Verified</span><br>
                  <a href="{trustedform_url}" target="_blank" style="color: #0284c7; font-size: 13px;">View TrustedForm Certificate ↗</a>
                </div>
              </div>
            </div>
            <div class="footer">
              Action Required: Contact lead within 5 minutes for personal injury & roadside support intake.
            </div>
          </div>
        </body>
        </html>
        """

    elif is_call:
        lead_type = "Vapi AI Voice Call"
        name = "Inbound Phone Caller"
        phone = lead_instance.caller_phone
        subject = f"[URGENT INTAKE] New Vapi AI Voice Call: {phone} (Priority: {lead_instance.priority})"
        recording = lead_instance.recording_url or "Recording pending upload"
        summary = lead_instance.summary or "Summary not available"
        transcript = lead_instance.transcript or "Transcript not available"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><style>
          body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #1e293b; }}
          .container {{ max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; }}
          .header {{ background: #0f172a; color: #f8fafc; padding: 18px 24px; }}
          .header h2 {{ margin: 0; font-size: 18px; color: #38bdf8; }}
          .content {{ padding: 24px; }}
          .section {{ margin-bottom: 18px; }}
          .label {{ font-weight: bold; color: #64748b; font-size: 12px; text-transform: uppercase; }}
          .value {{ font-size: 15px; color: #0f172a; margin-top: 2px; }}
          .priority-tag {{ background: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px; }}
          .transcript-box {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto; white-space: pre-wrap; }}
          .footer {{ background: #f8fafc; padding: 14px 24px; font-size: 12px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        </style></head>
        <body>
          <div class="container">
            <div class="header">
              <h2>📞 Vapi AI Inbound Call Qualified</h2>
              <p style="margin: 4px 0 0 0; font-size: 13px; color: #94a3b8;">Call Duration: {lead_instance.duration_seconds}s | Priority: <span class="priority-tag">{lead_instance.priority}</span></p>
            </div>
            <div class="content">
              <div class="section">
                <div class="label">Caller Phone Number</div>
                <div class="value"><a href="tel:{phone}" style="color: #2563eb; font-weight: bold; font-size: 16px;">{phone}</a></div>
              </div>
              <div class="section">
                <div class="label">AI Triage Summary</div>
                <div class="value" style="background:#eff6ff; padding: 10px; border-radius: 6px; color:#1e40af;">{summary}</div>
              </div>
              <div class="section">
                <div class="label">Audio Recording</div>
                <div class="value"><a href="{recording}" target="_blank" style="color: #0284c7; font-weight: bold;">▶ Listen to Call Audio ↗</a></div>
              </div>
              <div class="section">
                <div class="label">Full Conversation Transcript</div>
                <div class="transcript-box">{transcript}</div>
              </div>
            </div>
            <div class="footer">
              Dispatched automatically by GCrashAware Vapi AI Engine.
            </div>
          </div>
        </body>
        </html>
        """
    else:
        logger.error("Unknown lead instance type provided to send_lead_handoff_email.")
        return False

    text_content = strip_tags(html_content)

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=DEFAULT_FROM_EMAIL,
            to=SUPPORT_EMAIL_RECIPIENTS
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        lead_instance.sent_to_support = True
        lead_instance.save(update_fields=['sent_to_support'])
        logger.info(f"Dispatched support handoff email for {lead_type}: {phone}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send support email for {lead_type}: {str(exc)}")
        return False


def dispatch_n8n_incident_webhook(incident_instance):
    """
    Pushes newly ingested incident data to an n8n webhook for automated
    Google Ads and Meta Ads 5-10 mile radius campaign creation.
    """
    payload = {
        'incident_id': incident_instance.incident_id,
        'source': incident_instance.source,
        'incident_type': incident_instance.incident_type,
        'latitude': float(incident_instance.latitude),
        'longitude': float(incident_instance.longitude),
        'city_area': incident_instance.city_area,
        'occurred_at': incident_instance.occurred_at.isoformat() if incident_instance.occurred_at else None,
        'target_radius_miles': incident_instance.target_radius_miles,
        'status': incident_instance.status,
    }

    try:
        response = requests.post(N8N_INCIDENT_WEBHOOK_URL, json=payload, timeout=10)
        logger.info(f"n8n webhook triggered for incident {incident_instance.incident_id}: status {response.status_code}")
        return response.status_code in [200, 201, 202]
    except requests.RequestException as exc:
        logger.warning(f"n8n webhook request failed for incident {incident_instance.incident_id}: {str(exc)}")
        return False
