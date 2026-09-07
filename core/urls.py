from django.urls import path
from .views import (
    IncidentIngestView,
    VapiWebhookView,
    FormLeadIntakeView,
    landing_page_view
)

app_name = 'core'

urlpatterns = [
    # Public Georgia Roadside Legal Intake Landing Page (Form + Vapi AI Voice)
    path('', landing_page_view, name='home'),
    path('landing/', landing_page_view, name='landing_page'),

    # REST API Endpoints & Webhooks
    path('api/v1/incidents/ingest/', IncidentIngestView.as_view(), name='incident_ingest'),
    path('api/v1/webhooks/vapi/', VapiWebhookView.as_view(), name='vapi_webhook'),
    path('api/v1/leads/form/', FormLeadIntakeView.as_view(), name='form_lead_intake'),
]
