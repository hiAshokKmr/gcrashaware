import uuid
import logging
from django.shortcuts import render
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Incident, GeoCampaign, FormLead, CallLead, WebsiteVisitor, WorkflowStatus
from .serializers import (
    IncidentIngestSerializer,
    FormLeadSerializer,
    CallLeadSerializer,
    WebsiteVisitorSerializer,
    VisitorClickEventSerializer,
    WorkflowStatusSerializer
)
from .tasks import process_incident_media_async, trigger_geo_campaign_async
from .services import (
    send_lead_handoff_email,
    get_client_ip,
    parse_user_agent_details,
    fetch_ip_geolocation
)

logger = logging.getLogger(__name__)


class IncidentIngestView(APIView):
    """
    POST /api/v1/incidents/ingest/
    Receives JSON incident feeds from n8n or traffic APIs.
    """
    def get(self, request, *args, **kwargs):
        return Response({
            'status': 'online',
            'endpoint': 'Incident Ingestion API',
            'method': 'POST',
            'description': 'Send JSON incident payloads with media URLs array to ingest highway collisions.'
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = IncidentIngestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        incident = serializer.save()

        # Log Workflow Status: Incident Detected & 5-10 Mile Target Computed
        WorkflowStatus.log_event(
            workflow_name='INCIDENT_POLLER',
            stage='INCIDENT_DETECTED',
            status='SUCCESS',
            incident=incident,
            payload_snapshot={
                'source': incident.source,
                'city_area': incident.city_area,
                'target_radius_miles': incident.target_radius_miles,
                'gps': [float(incident.latitude), float(incident.longitude)]
            }
        )
        WorkflowStatus.log_event(
            workflow_name='AD_CAMPAIGN_TRIGGER',
            stage='GEO_RADIUS_CALCULATED',
            status='SUCCESS',
            incident=incident,
            payload_snapshot={
                'target_radius_miles': incident.target_radius_miles,
                'platforms': ['GOOGLE_ADS', 'META_ADS']
            }
        )

        # Enqueue async Celery/Django-Q tasks for each media asset
        pending_media = getattr(incident, 'pending_media', [])
        for media_obj in pending_media:
            try:
                process_incident_media_async.delay(media_obj.id)
            except Exception as e:
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
    Receives end-of-call callbacks from Vapi AI or the landing page interactive voice station.
    """
    def get(self, request, *args, **kwargs):
        return Response({
            'status': 'online',
            'endpoint': 'Vapi AI Webhook Receiver',
            'method': 'POST',
            'description': 'Ready to receive Vapi AI end-of-call-report webhooks and dispatch support handoffs.'
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        data = request.data
        logger.info(f"Vapi Webhook Received: {data.get('type') or data.get('message', {}).get('type')}")

        # Normalize Vapi payload structure
        message_data = data.get('message', {})
        call_data = message_data.get('call', {}) or data.get('call', {}) or data

        vapi_call_id = call_data.get('id') or data.get('vapi_call_id') or f"call_{data.get('id', 'session_')}"
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

        defaults_data = {
            'caller_phone': customer_phone,
            'call_status': 'COMPLETED',
            'duration_seconds': duration_seconds,
            'summary': summary,
            'transcript': transcript,
            'priority': priority
        }
        if recording_url:
            defaults_data['recording_url'] = recording_url

        call_lead, created = CallLead.objects.update_or_create(
            vapi_call_id=vapi_call_id,
            defaults=defaults_data
        )

        # Log Workflow Status: Vapi Call Lead Captured
        WorkflowStatus.log_event(
            workflow_name='VAPI_CALL_HANDOFF',
            stage='LEAD_CAPTURED',
            status='SUCCESS',
            call_lead=call_lead,
            payload_snapshot={
                'vapi_call_id': vapi_call_id,
                'caller_phone': customer_phone,
                'duration_seconds': duration_seconds,
                'priority': priority,
                'has_recording': bool(recording_url)
            }
        )

        # Send instant email handoff to support team
        email_sent = send_lead_handoff_email(call_lead)

        # Log Workflow Status: Support Handoff Email Sent
        WorkflowStatus.log_event(
            workflow_name='VAPI_CALL_HANDOFF',
            stage='SENT_TO_SUPPORT',
            status='SUCCESS' if email_sent else 'WARNING',
            call_lead=call_lead,
            payload_snapshot={
                'recipient': 'support@gcrashaware.com',
                'email_dispatched': email_sent
            }
        )

        return Response(
            {
                'status': 'success',
                'message': 'Vapi call logged and support handoff dispatched.',
                'lead_id': call_lead.id,
                'priority': priority,
                'summary': summary
            },
            status=status.HTTP_200_OK
        )


class FormLeadIntakeView(APIView):
    """
    POST /api/v1/leads/form/
    Public API endpoint for voluntary landing page lead submissions.
    """
    def get(self, request, *args, **kwargs):
        return Response({
            'status': 'online',
            'endpoint': 'Form Lead Intake API',
            'method': 'POST',
            'description': 'Accepts consumer form submissions with TCPA consent and TrustedForm tokens.'
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = FormLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        form_lead = serializer.save()

        # Log Workflow Status: Form Lead Captured & Validated
        WorkflowStatus.log_event(
            workflow_name='FORM_LEAD_INTAKE',
            stage='LEAD_CAPTURED',
            status='SUCCESS',
            form_lead=form_lead,
            incident=form_lead.incident,
            campaign=form_lead.campaign,
            payload_snapshot={
                'lead_id': str(form_lead.lead_id),
                'full_name': form_lead.full_name,
                'has_trustedform': bool(form_lead.trustedform_cert_url),
                'user_consent': form_lead.user_consent
            }
        )

        # Send instant email handoff to support team
        email_sent = send_lead_handoff_email(form_lead)

        # Log Workflow Status: Sent to Support
        WorkflowStatus.log_event(
            workflow_name='FORM_LEAD_INTAKE',
            stage='SENT_TO_SUPPORT',
            status='SUCCESS' if email_sent else 'WARNING',
            form_lead=form_lead,
            incident=form_lead.incident,
            campaign=form_lead.campaign,
            payload_snapshot={
                'recipient': 'support@gcrashaware.com',
                'email_dispatched': email_sent
            }
        )

        return Response(
            {
                'status': 'success',
                'message': 'Lead submitted successfully. Legal coordinator alerted.',
                'lead_id': str(form_lead.lead_id),
                'trustedform_cert_url': form_lead.trustedform_cert_url
            },
            status=status.HTTP_201_CREATED
        )


def landing_page_view(request):
    """
    GET / or /claim-assistance/
    Renders the public Georgia Legal & Roadside Assistance Landing Page with integrated Form & Vapi AI Voice.
    Automatically captures and logs non-admin visitor intelligence with 30-minute session segmentation.
    """
    is_admin = request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)
    visitor_id = request.COOKIES.get('gcrash_visitor_id') or str(uuid.uuid4())
    session_id = request.COOKIES.get('gcrash_session_id')
    is_new_session = not session_id

    if not session_id:
        session_id = f"sess_{uuid.uuid4().hex[:16]}"

    if not is_admin:
        try:
            ip = get_client_ip(request)
            ua_str = request.META.get('HTTP_USER_AGENT', '')
            ua_info = parse_user_agent_details(ua_str)
            geo = fetch_ip_geolocation(ip)

            # Check if linked to an incident via query params or UTM
            incident_id = request.GET.get('incident_id') or request.GET.get('incident')
            incident_obj = None
            if incident_id:
                incident_obj = Incident.objects.filter(incident_id=incident_id).first()

            if is_new_session:
                # Count previous visits to determine returning visitor status
                prior_visits = WebsiteVisitor.objects.filter(visitor_id=visitor_id).count()
                WebsiteVisitor.objects.create(
                    visitor_id=visitor_id,
                    session_id=session_id,
                    visit_number=prior_visits + 1,
                    is_returning=(prior_visits > 0),
                    incident=incident_obj,
                    ip_address=ip,
                    country=geo.get('country', ''),
                    region_state=geo.get('region_state', ''),
                    city=geo.get('city', ''),
                    postal_code=geo.get('postal_code', ''),
                    latitude=geo.get('latitude'),
                    longitude=geo.get('longitude'),
                    timezone=geo.get('timezone', ''),
                    isp=geo.get('isp', ''),
                    device_type=ua_info.get('device_type', 'UNKNOWN'),
                    browser=ua_info.get('browser', ''),
                    os=ua_info.get('os', ''),
                    user_agent=ua_str,
                    page_url=request.build_absolute_uri(),
                    page_path=request.path,
                    referrer=request.META.get('HTTP_REFERER', ''),
                    utm_source=request.GET.get('utm_source', ''),
                    utm_medium=request.GET.get('utm_medium', ''),
                    utm_campaign=request.GET.get('utm_campaign', ''),
                    utm_term=request.GET.get('utm_term', ''),
                    utm_content=request.GET.get('utm_content', ''),
                    gclid=request.GET.get('gclid', ''),
                    fbclid=request.GET.get('fbclid', '')
                )
            else:
                # Update existing active session timestamp
                WebsiteVisitor.objects.filter(session_id=session_id).update(
                    last_activity_at=timezone.now()
                )
        except Exception as exc:
            logger.warning(f"Failed to auto-log visitor: {exc}")

    response = render(request, 'core/landing_page.html', {
        'is_admin': is_admin,
        'visitor_id': visitor_id,
        'session_id': session_id
    })

    if not is_admin:
        # Long-term visitor cookie (1 year)
        response.set_cookie('gcrash_visitor_id', visitor_id, max_age=365*24*60*60, samesite='Lax')
        # 30-minute session cookie (sliding window)
        response.set_cookie('gcrash_session_id', session_id, max_age=1800, samesite='Lax')

    return response



class WebsiteVisitorAPIView(APIView):
    """
    GET /api/v1/visitors/
    List, search, filter website visitors and query aggregated traffic metrics.

    POST /api/v1/visitors/
    Registers/updates a visitor session, enriches with IP geolocation,
    device analysis, UTM tracking, and initial click-stream data.
    """
    def get(self, request, *args, **kwargs):
        queryset = WebsiteVisitor.objects.all().select_related('incident', 'campaign')

        # Filters
        device = request.query_params.get('device_type')
        if device:
            queryset = queryset.filter(device_type__iexact=device)

        region = request.query_params.get('region_state')
        if region:
            queryset = queryset.filter(region_state__icontains=region)

        city = request.query_params.get('city')
        if city:
            queryset = queryset.filter(city__icontains=city)

        incident_id = request.query_params.get('incident_id')
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)

        utm_source = request.query_params.get('utm_source')
        if utm_source:
            queryset = queryset.filter(utm_source__icontains=utm_source)

        is_returning = request.query_params.get('is_returning')
        if is_returning is not None:
            queryset = queryset.filter(is_returning=is_returning.lower() == 'true')

        limit = min(int(request.query_params.get('limit', 100)), 500)
        total_count = queryset.count()
        visitors = queryset[:limit]

        serializer = WebsiteVisitorSerializer(visitors, many=True)
        return Response({
            'status': 'success',
            'total_count': total_count,
            'limit': limit,
            'visitors': serializer.data
        }, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        # Ignore visits from admin/staff sessions
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return Response({
                'status': 'ignored',
                'message': 'Admin/Staff browser session tracking ignored.'
            }, status=status.HTTP_200_OK)

        data = request.data.copy()

        visitor_id = data.get('visitor_id') or request.COOKIES.get('gcrash_visitor_id') or str(uuid.uuid4())
        session_id = data.get('session_id') or request.COOKIES.get('gcrash_session_id') or f"sess_{uuid.uuid4().hex[:16]}"
        data['visitor_id'] = visitor_id
        data['session_id'] = session_id

        # Auto-detect IP address if not supplied
        ip = data.get('ip_address') or get_client_ip(request)
        data['ip_address'] = ip

        # Auto-parse User-Agent for device, browser, OS if not supplied
        ua_str = data.get('user_agent') or request.META.get('HTTP_USER_AGENT', '')
        data['user_agent'] = ua_str
        ua_info = parse_user_agent_details(ua_str)
        if not data.get('device_type') or data.get('device_type') == 'UNKNOWN':
            data['device_type'] = ua_info['device_type']
        if not data.get('browser'):
            data['browser'] = ua_info['browser']
        if not data.get('os'):
            data['os'] = ua_info['os']

        # Auto-fetch IP Geolocation if city/region not provided
        if not data.get('city') or not data.get('region_state'):
            geo = fetch_ip_geolocation(ip)
            for k, v in geo.items():
                if not data.get(k) and v is not None:
                    data[k] = v

        # Referrer and page path fallback
        if not data.get('referrer'):
            data['referrer'] = request.META.get('HTTP_REFERER', '')
        if not data.get('page_path'):
            data['page_path'] = request.path

        # Link Incident if incident_id provided in data or UTM
        incident_id = data.get('incident_id') or data.get('incident') or request.query_params.get('incident_id')
        incident_obj = None
        if incident_id:
            incident_obj = Incident.objects.filter(incident_id=incident_id).first()

        # Check for initial clicked element payload
        initial_click = data.pop('click_event', None)
        clicked_list = data.get('clicked_elements', [])
        if initial_click:
            initial_click['timestamp'] = timezone.now().isoformat()
            clicked_list.append(initial_click)

        # Prior visits calculation
        prior_visits = WebsiteVisitor.objects.filter(visitor_id=visitor_id).exclude(session_id=session_id).count()

        # Create or update visitor session record
        visitor, created = WebsiteVisitor.objects.update_or_create(
            session_id=session_id,
            defaults={
                'visitor_id': visitor_id,
                'visit_number': prior_visits + 1,
                'is_returning': (prior_visits > 0),
                'incident': incident_obj,
                'ip_address': data.get('ip_address'),
                'country': data.get('country', ''),
                'region_state': data.get('region_state', ''),
                'city': data.get('city', ''),
                'postal_code': data.get('postal_code', ''),
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'timezone': data.get('timezone', ''),
                'isp': data.get('isp', ''),
                'device_type': data.get('device_type', 'UNKNOWN'),
                'browser': data.get('browser', ''),
                'os': data.get('os', ''),
                'user_agent': data.get('user_agent', ''),
                'screen_resolution': data.get('screen_resolution', ''),
                'language': data.get('language', ''),
                'page_url': data.get('page_url', ''),
                'page_path': data.get('page_path', '/'),
                'referrer': data.get('referrer', ''),
                'utm_source': data.get('utm_source', ''),
                'utm_medium': data.get('utm_medium', ''),
                'utm_campaign': data.get('utm_campaign', ''),
                'utm_term': data.get('utm_term', ''),
                'utm_content': data.get('utm_content', ''),
                'gclid': data.get('gclid', ''),
                'fbclid': data.get('fbclid', ''),
                'clicked_elements': clicked_list,
                'interaction_summary': data.get('interaction_summary', '')
            }
        )

        return Response({
            'status': 'success',
            'created': created,
            'visitor_id': visitor.visitor_id,
            'session_id': visitor.session_id,
            'visit_number': visitor.visit_number,
            'is_returning': visitor.is_returning,
            'device_type': visitor.device_type,
            'location': {
                'city': visitor.city,
                'region_state': visitor.region_state,
                'country': visitor.country,
                'latitude': float(visitor.latitude) if visitor.latitude else None,
                'longitude': float(visitor.longitude) if visitor.longitude else None,
            },
            'visited_at': visitor.visited_at
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WebsiteVisitorDetailView(APIView):
    """
    GET /api/v1/visitors/<identifier>/
    Retrieve full profile and click stream for a specific session_id or visitor_id.

    POST /api/v1/visitors/<identifier>/
    Appends a new click event / interaction to the active visitor session.
    """
    def get(self, request, visitor_id, *args, **kwargs):
        # Look up by session_id first, then fallback to latest session of visitor_id
        visitor = WebsiteVisitor.objects.filter(session_id=visitor_id).select_related('incident', 'campaign').first()
        if not visitor:
            visitor = WebsiteVisitor.objects.filter(visitor_id=visitor_id).select_related('incident', 'campaign').order_by('-visited_at').first()

        if not visitor:
            return Response({'error': 'Visitor or session not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = WebsiteVisitorSerializer(visitor)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, visitor_id, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
            return Response({'status': 'ignored', 'message': 'Admin click event ignored'}, status=status.HTTP_200_OK)

        # Look up by session_id first, then fallback to most recent session of visitor_id
        visitor = WebsiteVisitor.objects.filter(session_id=visitor_id).first()
        if not visitor:
            visitor = WebsiteVisitor.objects.filter(visitor_id=visitor_id).order_by('-visited_at').first()

        if not visitor:
            return Response({'error': 'Visitor or session not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = VisitorClickEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        event_data = serializer.validated_data
        event_data['timestamp'] = timezone.now().isoformat()

        # Append to clicked_elements list
        clicked = list(visitor.clicked_elements or [])
        clicked.append(event_data)
        visitor.clicked_elements = clicked

        # Update interaction summary if meaningful action
        element_text = event_data.get('element_text', '')
        action = event_data.get('action_type', 'CLICK')
        summary_note = f"{action}: {element_text}" if element_text else f"{action} on {event_data.get('element_tag', 'element')}"
        if visitor.interaction_summary:
            visitor.interaction_summary += f" | {summary_note}"
        else:
            visitor.interaction_summary = summary_note

        visitor.save(update_fields=['clicked_elements', 'interaction_summary', 'last_activity_at'])

        return Response({
            'status': 'success',
            'message': 'Click event logged successfully',
            'session_id': visitor.session_id,
            'total_clicks': len(visitor.clicked_elements),
            'last_event': event_data
        }, status=status.HTTP_200_OK)


class WorkflowStatusAPIView(APIView):
    """
    GET /api/v1/workflows/status/
    List, filter, and inspect end-to-end automation workflow logs and error states.
    """
    def get(self, request, *args, **kwargs):
        queryset = WorkflowStatus.objects.all().select_related('incident', 'campaign', 'form_lead', 'call_lead')

        workflow_name = request.query_params.get('workflow_name')
        if workflow_name:
            queryset = queryset.filter(workflow_name__iexact=workflow_name)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status__iexact=status_param)

        incident_id = request.query_params.get('incident_id')
        if incident_id:
            queryset = queryset.filter(incident_id=incident_id)

        limit = min(int(request.query_params.get('limit', 50)), 200)
        total_count = queryset.count()
        logs = queryset[:limit]

        serializer = WorkflowStatusSerializer(logs, many=True)
        return Response({
            'status': 'success',
            'total_count': total_count,
            'limit': limit,
            'workflow_logs': serializer.data
        }, status=status.HTTP_200_OK)



