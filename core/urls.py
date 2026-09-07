from django.urls import path
from .views import (
    IncidentIngestView,
    VapiWebhookView,
    FormLeadIntakeView,
    WebsiteVisitorAPIView,
    WebsiteVisitorDetailView,
    WorkflowStatusAPIView,
    landing_page_view
)

app_name = 'core'

urlpatterns = [
    # Public Georgia Roadside Legal Intake Landing Page (Form + Vapi AI Voice)
    path('', landing_page_view, name='home'),
    path('claim-assistance/', landing_page_view, name='claim_assistance'),

    # REST API Endpoints & Webhooks
    path('api/v1/incidents/ingest/', IncidentIngestView.as_view(), name='incident_ingest'),
    path('api/v1/webhooks/vapi/', VapiWebhookView.as_view(), name='vapi_webhook'),
    path('api/v1/leads/form/', FormLeadIntakeView.as_view(), name='form_lead_intake'),

    # Automation Workflow Status & Execution Audit Logs API
    path('api/v1/workflows/status/', WorkflowStatusAPIView.as_view(), name='workflow_status'),

    # Visitor & Interaction Tracking APIs
    path('api/v1/visitors/', WebsiteVisitorAPIView.as_view(), name='visitor_tracking'),
    path('api/v1/visitors/<str:visitor_id>/', WebsiteVisitorDetailView.as_view(), name='visitor_detail'),
]

