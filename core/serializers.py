from rest_framework import serializers
from .models import Incident, IncidentMedia, GeoCampaign, FormLead, CallLead, WebsiteVisitor, WorkflowStatus


class MediaInputSerializer(serializers.Serializer):
    media_type = serializers.ChoiceField(choices=['IMAGE', 'VIDEO'], default='IMAGE')
    source_url = serializers.URLField(max_length=1000)


class IncidentIngestSerializer(serializers.ModelSerializer):
    media = MediaInputSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Incident
        fields = [
            'incident_id',
            'source',
            'incident_type',
            'latitude',
            'longitude',
            'city_area',
            'occurred_at',
            'target_radius_miles',
            'status',
            'media'
        ]

    def create(self, validated_data):
        media_data = validated_data.pop('media', [])
        incident, _ = Incident.objects.update_or_create(
            incident_id=validated_data.get('incident_id'),
            defaults=validated_data
        )

        created_media_objs = []
        for item in media_data:
            media_obj = IncidentMedia.objects.create(
                incident=incident,
                media_type=item.get('media_type', 'IMAGE'),
                source_url=item.get('source_url'),
                download_status='PENDING'
            )
            created_media_objs.append(media_obj)

        incident.pending_media = created_media_objs
        return incident


class FormLeadSerializer(serializers.ModelSerializer):
    xxTrustedFormCertUrl = serializers.URLField(
        required=False,
        allow_null=True,
        allow_blank=True,
        write_only=True
    )

    class Meta:
        model = FormLead
        fields = [
            'lead_id',
            'incident',
            'campaign',
            'full_name',
            'phone_number',
            'email',
            'preferred_contact',
            'message',
            'trustedform_cert_url',
            'xxTrustedFormCertUrl',
            'user_consent',
            'created_at'
        ]
        read_only_fields = ['lead_id', 'created_at']

    def validate_user_consent(self, value):
        if not value:
            raise serializers.ValidationError("Explicit TCPA consent is required to submit this form.")
        return value

    def create(self, validated_data):
        # Map TrustedForm token field if submitted under xxTrustedFormCertUrl
        cert_url = validated_data.pop('xxTrustedFormCertUrl', None)
        if cert_url and not validated_data.get('trustedform_cert_url'):
            validated_data['trustedform_cert_url'] = cert_url

        return super().create(validated_data)


class CallLeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallLead
        fields = [
            'id',
            'vapi_call_id',
            'caller_phone',
            'call_status',
            'duration_seconds',
            'summary',
            'transcript',
            'recording_url',
            'priority',
            'sent_to_support',
            'created_at'
        ]


class WebsiteVisitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteVisitor
        fields = '__all__'
        read_only_fields = ['visited_at', 'last_activity_at']


class VisitorClickEventSerializer(serializers.Serializer):
    """
    Serializer to ingest click interactions and append to a visitor's clicked_elements stream.
    """
    element_id = serializers.CharField(required=False, allow_blank=True, default='')
    element_tag = serializers.CharField(required=False, allow_blank=True, default='')
    element_text = serializers.CharField(required=False, allow_blank=True, default='')
    element_classes = serializers.CharField(required=False, allow_blank=True, default='')
    action_type = serializers.CharField(required=False, default='CLICK')
    page_url = serializers.URLField(required=False, allow_blank=True, default='')
    metadata = serializers.DictField(required=False, default=dict)


class WorkflowStatusSerializer(serializers.ModelSerializer):
    workflow_display = serializers.CharField(source='get_workflow_name_display', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = WorkflowStatus
        fields = [
            'id',
            'workflow_name',
            'workflow_display',
            'stage',
            'stage_display',
            'status',
            'incident',
            'campaign',
            'form_lead',
            'call_lead',
            'execution_time_ms',
            'error_message',
            'payload_snapshot',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


