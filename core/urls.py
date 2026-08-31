from django.urls import path
from .views import (
    IncidentIngestView,
    VapiWebhookView,
    FormLeadIntakeView,
    dashboard_view,
    landing_page_view
)

app_name = 'core'

urlpatterns = [
    # GCrashAware Mission Control Dashboard
    path('', dashboard_view, name='dashboard'),

    # Public Georgia Roadside Legal Intake Landing Page
    path('landing/', landing_page_view, name='landing_page'),

    # REST API Endpoints & Webhooks
    path('api/v1/incidents/ingest/', IncidentIngestView.as_view(), name='incident_ingest'),
    path('api/v1/webhooks/vapi/', VapiWebhookView.as_view(), name='vapi_webhook'),
    path('api/v1/leads/form/', FormLeadIntakeView.as_view(), name='form_lead_intake'),
]
