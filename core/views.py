import logging
from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Incident, IncidentMedia, FormLead, CallLead
from .serializers import IncidentIngestSerializer, FormLeadSerializer, CallLeadSerializer
from .tasks import process_incident_media_async, trigger_geo_campaign_async
from .services import send_lead_handoff_email

logger = logging.getLogger(__name__)


class IncidentIngestView(APIView):
    """
    POST /api/v1/incidents/ingest/
    Receives JSON incident feeds from n8n or traffic APIs.
    Saves incident, enqueues heavy crash images/videos for asynchronous background download,
    and returns HTTP 201 instantly to avoid webhook timeouts.
    """
    def post(self, request, *args, **kwargs):
        serializer = IncidentIngestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        incident = serializer.save()

        # Enqueue async Celery/Django-Q tasks for each media asset
        pending_media = getattr(incident, 'pending_media', [])
        for media_obj in pending_media:
            try:
                process_incident_media_async.delay(media_obj.id)
            except Exception as e:
                # Direct synchronous fallback if Celery worker is offline
                logger.warning(f"Celery .delay failed, calling inline: {e}")
                process_incident_media_async(media_obj.id)

        # Trigger async geo-campaign / n8n workflow
        try:
            trigger_geo_campaign_async.delay(incident.incident_id)
        except Exception:
            trigger_geo_campaign_async(incident.incident_id)

        return Response(
            {
                'status': 'success',
                'message': 'Incident ingested successfully. Media processing enqueued.',
                'incident_id': incident.incident_id,
                'media_enqueued': len(pending_media),
                'target_radius_miles': incident.target_radius_miles
            },
            status=status.HTTP_201_CREATED
        )


class VapiWebhookView(APIView):
    """
    POST /api/v1/webhooks/vapi/
    Receives end-of-call callbacks from Vapi AI.
    Parses transcript, summary, audio recording URL, saves CallLead, and triggers email handoff.
    """
    def post(self, request, *args, **kwargs):
        data = request.data
        logger.info(f"Vapi Webhook Received: {data.get('type') or data.get('message', {}).get('type')}")

        # Normalize Vapi payload structure
        message_data = data.get('message', {})
        call_data = message_data.get('call', {}) or data.get('call', {}) or data

        vapi_call_id = call_data.get('id') or data.get('vapi_call_id') or f"call_{data.get('id', 'unknown')}"
        customer_phone = (
            call_data.get('customer', {}).get('number') or
            data.get('callerPhone') or
            data.get('customer_phone') or
            '+1 (404) 555-0100'
        )

        transcript = (
            call_data.get('transcript') or
            data.get('transcript') or
            message_data.get('transcript') or
            ''
        )
        summary = (
            call_data.get('summary') or
            data.get('summary') or
            message_data.get('summary') or
            'Incident intake call completed via Vapi AI.'
        )
        recording_url = (
            call_data.get('recordingUrl') or
            data.get('recording_url') or
            ''
        )
        duration_seconds = int(
            call_data.get('duration') or
            data.get('duration_seconds') or
            0
        )

        # Priority calculation based on keywords
        summary_lower = summary.lower()
        if 'urgent' in summary_lower or 'injury' in summary_lower or 'hospital' in summary_lower:
            priority = 'CRITICAL'
        elif 'lawyer' in summary_lower or 'attorney' in summary_lower or 'tow' in summary_lower:
            priority = 'HIGH'
        else:
            priority = 'MEDIUM'

        call_lead, created = CallLead.objects.update_or_create(
            vapi_call_id=vapi_call_id,
            defaults={
                'caller_phone': customer_phone,
                'call_status': 'COMPLETED',
                'duration_seconds': duration_seconds,
                'summary': summary,
                'transcript': transcript,
                'recording_url': recording_url,
                'priority': priority
            }
        )

        # Send instant email handoff to support team
        send_lead_handoff_email(call_lead)

        return Response(
            {
                'status': 'success',
                'message': 'Vapi call logged and support handoff dispatched.',
                'lead_id': call_lead.id,
                'priority': priority
            },
            status=status.HTTP_200_OK
        )


class FormLeadIntakeView(APIView):
    """
    POST /api/v1/leads/form/
    Public API endpoint for voluntary landing page lead submissions.
    Validates TCPA user consent, captures TrustedForm certificate token, saves FormLead, and alerts support.
    """
    def post(self, request, *args, **kwargs):
        serializer = FormLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        form_lead = serializer.save()

        # Send instant email handoff to support team
        send_lead_handoff_email(form_lead)

        return Response(
            {
                'status': 'success',
                'message': 'Lead submitted successfully. Legal coordinator alerted.',
                'lead_id': str(form_lead.lead_id),
                'trustedform_cert_url': form_lead.trustedform_cert_url
            },
            status=status.HTTP_201_CREATED
        )


def dashboard_view(request):
    """
    GET / or /dashboard/
    Renders GCrashAware Mission Control Dashboard (Atlanta radar, active ad campaigns, Vapi station, and CRM).
    """
    return render(request, 'core/dashboard.html')


def landing_page_view(request):
    """
    GET /landing/ or /claim-assistance/
    Renders public Georgia Legal & Roadside Assistance intake view.
    """
    return render(request, 'core/landing_page.html')

