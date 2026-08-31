from django.contrib import admin
from .models import Incident, IncidentMedia, GeoCampaign, FormLead, CallLead


class IncidentMediaInline(admin.TabularInline):
    model = IncidentMedia
    extra = 0
    readonly_fields = ('created_at', 'file_size_bytes')


class GeoCampaignInline(admin.TabularInline):
    model = GeoCampaign
    extra = 0


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ('incident_id', 'city_area', 'incident_type', 'status', 'occurred_at', 'target_radius_miles')
    list_filter = ('status', 'incident_type', 'source')
    search_fields = ('incident_id', 'city_area')
    inlines = [IncidentMediaInline, GeoCampaignInline]


@admin.register(IncidentMedia)
class IncidentMediaAdmin(admin.ModelAdmin):
    list_display = ('id', 'incident', 'media_type', 'download_status', 'file_size_bytes', 'created_at')
    list_filter = ('download_status', 'media_type')
    search_fields = ('incident__incident_id', 'source_url')


@admin.register(GeoCampaign)
class GeoCampaignAdmin(admin.ModelAdmin):
    list_display = ('id', 'incident', 'platform', 'status', 'budget_daily', 'created_at')
    list_filter = ('platform', 'status')
    search_fields = ('incident__incident_id', 'external_campaign_id')


@admin.register(FormLead)
class FormLeadAdmin(admin.ModelAdmin):
    list_display = ('lead_id', 'full_name', 'phone_number', 'user_consent', 'sent_to_support', 'created_at')
    list_filter = ('user_consent', 'sent_to_support', 'created_at')
    search_fields = ('full_name', 'phone_number', 'email')


@admin.register(CallLead)
class CallLeadAdmin(admin.ModelAdmin):
    list_display = ('vapi_call_id', 'caller_phone', 'priority', 'call_status', 'duration_seconds', 'sent_to_support', 'created_at')
    list_filter = ('priority', 'call_status', 'sent_to_support')
    search_fields = ('vapi_call_id', 'caller_phone', 'summary')
