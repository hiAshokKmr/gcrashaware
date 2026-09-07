from django.contrib import admin
from django.utils.html import format_html
import json
from .models import Incident, IncidentMedia, GeoCampaign, FormLead, CallLead, WebsiteVisitor, WorkflowStatus


class CustomAdminBase(admin.ModelAdmin):
    """Base ModelAdmin that automatically injects the colorful admin theme CSS stylesheet."""
    class Media:
        css = {
            'all': ('css/admin_custom.css',)
        }


class IncidentMediaInline(admin.TabularInline):
    model = IncidentMedia
    extra = 0
    readonly_fields = ('created_at', 'file_size_bytes')


class GeoCampaignInline(admin.TabularInline):
    model = GeoCampaign
    extra = 0


@admin.register(Incident)
class IncidentAdmin(CustomAdminBase):
    list_display = ('incident_id', 'city_area', 'incident_type', 'status', 'occurred_at', 'target_radius_miles')
    list_filter = ('status', 'incident_type', 'source')
    search_fields = ('incident_id', 'city_area')
    inlines = [IncidentMediaInline, GeoCampaignInline]



@admin.register(IncidentMedia)
class IncidentMediaAdmin(CustomAdminBase):
    list_display = ('id', 'incident', 'media_type', 'download_status', 'file_size_bytes', 'created_at')
    list_filter = ('download_status', 'media_type')
    search_fields = ('incident__incident_id', 'source_url')


@admin.register(GeoCampaign)
class GeoCampaignAdmin(CustomAdminBase):
    list_display = ('id', 'incident', 'platform', 'status', 'budget_daily', 'created_at')
    list_filter = ('platform', 'status')
    search_fields = ('incident__incident_id', 'external_campaign_id')


@admin.register(FormLead)
class FormLeadAdmin(CustomAdminBase):
    list_display = ('lead_id', 'full_name', 'phone_number', 'user_consent', 'sent_to_support', 'created_at')
    list_filter = ('user_consent', 'sent_to_support', 'created_at')
    search_fields = ('full_name', 'phone_number', 'email')


@admin.register(CallLead)
class CallLeadAdmin(CustomAdminBase):
    list_display = ('vapi_call_id', 'caller_phone', 'priority', 'call_status', 'duration_seconds', 'audio_player', 'sent_to_support', 'created_at')
    list_filter = ('priority', 'call_status', 'sent_to_support')
    search_fields = ('vapi_call_id', 'caller_phone', 'summary', 'transcript')
    readonly_fields = ('audio_player_preview', 'created_at')

    def audio_player(self, obj):
        if obj.recording_url:
            return format_html(
                '<a href="{}" target="_blank" style="font-weight:bold; color:#0284c7;">▶ Open Recording ↗</a>',
                obj.recording_url
            )
        return "No Recording"
    audio_player.short_description = "Audio Recording"

    def audio_player_preview(self, obj):
        if obj.recording_url:
            return format_html(
                '<audio controls style="width: 100%; max-width: 400px;"><source src="{}" type="audio/mpeg"><source src="{}" type="audio/wav">Your browser does not support audio element.</audio>',
                obj.recording_url, obj.recording_url
            )
        return "No audio recording URL available."
    audio_player_preview.short_description = "Listen to Call Audio"


@admin.register(WebsiteVisitor)
class WebsiteVisitorAdmin(CustomAdminBase):
    list_display = (
        'visitor_short_id',
        'visit_type_badge',
        'ip_address',
        'location_badge',
        'device_type',
        'browser',
        'utm_campaign',
        'clicks_count',
        'visited_at',
        'last_activity_at'
    )
    list_filter = (
        'is_returning',
        'device_type',
        'region_state',
        'country',
        'utm_source',
        'utm_campaign',
        'visited_at'
    )
    search_fields = (
        'visitor_id',
        'session_id',
        'ip_address',
        'city',
        'region_state',
        'utm_campaign',
        'user_agent',
        'interaction_summary'
    )
    readonly_fields = (
        'visitor_id',
        'session_id',
        'visit_number',
        'is_returning',
        'visited_at',
        'last_activity_at',
        'clicked_elements_formatted'
    )

    def visitor_short_id(self, obj):
        return obj.visitor_id[:10] + '...' if len(obj.visitor_id) > 10 else obj.visitor_id
    visitor_short_id.short_description = "Visitor ID"

    def visit_type_badge(self, obj):
        if obj.is_returning:
            return format_html(
                '<span style="background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">Returning (#{visit})</span>',
                visit=obj.visit_number
            )
        return format_html(
            '<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">New Visitor</span>'
        )
    visit_type_badge.short_description = "Visit Type"

    def location_badge(self, obj):
        loc = f"{obj.city}, {obj.region_state}" if obj.city or obj.region_state else (obj.country or 'Unknown')
        if obj.latitude and obj.longitude:
            map_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html(
                '📍 <a href="{}" target="_blank" style="color: #0284c7; font-weight: 500;">{} ↗</a>',
                map_url, loc
            )
        return loc
    location_badge.short_description = "Location"

    def clicks_count(self, obj):
        count = len(obj.clicked_elements) if isinstance(obj.clicked_elements, list) else 0
        if count > 0:
            return format_html(
                '<span style="background:#e0f2fe; color:#0369a1; padding:2px 8px; border-radius:12px; font-weight:bold;">{} clicks</span>',
                count
            )
        return "0 clicks"
    clicks_count.short_description = "Clicks"

    def clicked_elements_formatted(self, obj):
        if not obj.clicked_elements:
            return "No clicks recorded yet."
        formatted = json.dumps(obj.clicked_elements, indent=2)
        return format_html(
            '<pre style="background:#0f172a; color:#38bdf8; padding:12px; border-radius:6px; max-height:400px; overflow:auto;">{}</pre>',
            formatted
        )
    clicked_elements_formatted.short_description = "Click Stream & Action Logs"


@admin.register(WorkflowStatus)
class WorkflowStatusAdmin(CustomAdminBase):
    list_display = (
        'id',
        'workflow_badge',
        'stage_badge',
        'status_badge',
        'incident_link',
        'execution_time_badge',
        'created_at',
    )
    list_filter = (
        'workflow_name',
        'status',
        'stage',
        'created_at',
    )
    search_fields = (
        'incident__incident_id',
        'stage',
        'error_message',
        'workflow_name',
    )
    readonly_fields = (
        'created_at',
        'payload_preview',
    )

    def workflow_badge(self, obj):
        colors = {
            'INCIDENT_POLLER': ('#e0e7ff', '#3730a3'),
            'AD_CAMPAIGN_TRIGGER': ('#fef3c7', '#92400e'),
            'FORM_LEAD_INTAKE': ('#dbeafe', '#1e40af'),
            'VAPI_CALL_HANDOFF': ('#f3e8ff', '#6b21a8'),
        }
        bg, fg = colors.get(obj.workflow_name, ('#f1f5f9', '#475569'))
        return format_html(
            '<span style="background:{}; color:{}; padding:3px 9px; border-radius:12px; font-weight:700; font-size:11px;">{}</span>',
            bg, fg, obj.get_workflow_name_display()
        )
    workflow_badge.short_description = "Workflow"

    def stage_badge(self, obj):
        return format_html(
            '<span style="font-weight:600; color:#334155;">{}</span>',
            obj.get_stage_display()
        )
    stage_badge.short_description = "Stage / Milestone"

    def status_badge(self, obj):
        if obj.status == 'SUCCESS':
            return format_html('<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">✓ SUCCESS</span>')
        elif obj.status == 'FAILED':
            return format_html('<span style="background:#fee2e2; color:#b91c1c; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">✗ FAILED</span>')
        elif obj.status == 'WARNING':
            return format_html('<span style="background:#ffedd5; color:#c2410c; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">⚠ WARNING</span>')
        return format_html('<span style="background:#f1f5f9; color:#64748b; padding:2px 8px; border-radius:10px; font-weight:bold; font-size:11px;">⏳ IN PROGRESS</span>')
    status_badge.short_description = "Status"

    def incident_link(self, obj):
        if obj.incident:
            return format_html(
                '<a href="/admin/core/incident/{}/change/" style="color:#0284c7; font-weight:600;">{}</a>',
                obj.incident.incident_id, obj.incident.incident_id
            )
        return "—"
    incident_link.short_description = "Incident Link"

    def execution_time_badge(self, obj):
        if obj.execution_time_ms > 0:
            return format_html('<span style="color:#64748b; font-size:11px;">{} ms</span>', obj.execution_time_ms)
        return "—"
    execution_time_badge.short_description = "Execution"

    def payload_preview(self, obj):
        if not obj.payload_snapshot:
            return "No payload metadata."
        formatted = json.dumps(obj.payload_snapshot, indent=2)
        return format_html(
            '<pre style="background:#0f172a; color:#38bdf8; padding:12px; border-radius:6px; max-height:400px; overflow:auto;">{}</pre>',
            formatted
        )
    payload_preview.short_description = "Audit Payload Snapshot"



