import uuid
from django.db import models


class Incident(models.Model):
    """
    Represents an accident or traffic incident detected via traffic feeds (GDOT/511/n8n).
    Strictly used for geographic contextual ad targeting, not for personal victim scraping.
    """
    STATUS_CHOICES = [
        ('ACTIVE', 'Active Incident'),
        ('CAMPAIGN_TRIGGERED', 'Campaign Triggered'),
        ('CLOSED', 'Closed / Cleared'),
    ]

    incident_id = models.CharField(
        max_length=100,
        unique=True,
        primary_key=True,
        help_text="External unique incident identifier from traffic feed or n8n"
    )
    source = models.CharField(
        max_length=100,
        default='GDOT',
        help_text="Traffic feed source (e.g. GDOT, 511_GA, NaviGAtor)"
    )
    incident_type = models.CharField(
        max_length=150,
        default='Collision',
        help_text="Type of incident (e.g. Collision, Multi-car Accident, Vehicle Fire)"
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="GPS Latitude of the incident"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        help_text="GPS Longitude of the incident"
    )
    city_area = models.CharField(
        max_length=255,
        help_text="Highway corridor or municipal area (e.g. I-85 North near Spaghetti Junction)"
    )
    occurred_at = models.DateTimeField(
        help_text="Timestamp when the incident was reported"
    )
    target_radius_miles = models.IntegerField(
        default=5,
        help_text="Calculated contextual ad target radius in miles (5 to 10 miles)"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']
        indexes = [
            models.Index(fields=['status', 'occurred_at']),
            models.Index(fields=['latitude', 'longitude']),
        ]

    def __str__(self):
        return f"{self.incident_id} - {self.city_area} ({self.status})"


class IncidentMedia(models.Model):
    """
    Stores heavy crash media (HD traffic camera images, crash video streams)
    linked to an Incident. Processed asynchronously into S3/R2 storage.
    """
    MEDIA_TYPE_CHOICES = [
        ('IMAGE', 'Crash Image / Screenshot'),
        ('VIDEO', 'Traffic Camera Video Stream / MP4'),
    ]

    DOWNLOAD_STATUS_CHOICES = [
        ('PENDING', 'Pending Download'),
        ('DOWNLOADING', 'In Progress'),
        ('COMPLETED', 'Successfully Stored'),
        ('FAILED', 'Download Failed'),
    ]

    incident = models.ForeignKey(
        Incident,
        related_name='media_files',
        on_delete=models.CASCADE
    )
    media_type = models.CharField(
        max_length=20,
        choices=MEDIA_TYPE_CHOICES,
        default='IMAGE'
    )
    source_url = models.URLField(
        max_length=1000,
        help_text="Original public URL provided by GDOT / camera feed"
    )
    file = models.FileField(
        upload_to='crash_media/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Persisted file in S3 / Django media storage"
    )
    file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Size of the downloaded asset in bytes"
    )
    download_status = models.CharField(
        max_length=20,
        choices=DOWNLOAD_STATUS_CHOICES,
        default='PENDING'
    )
    error_message = models.TextField(
        blank=True,
        null=True,
        help_text="Error trace if download failed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Media {self.id} ({self.media_type}) for Incident {self.incident_id} [{self.download_status}]"


class GeoCampaign(models.Model):
    """
    Dynamic 5-10 mile radius ad campaign launched on Google Ads or Meta Ads.
    """
    PLATFORM_CHOICES = [
        ('GOOGLE_ADS', 'Google Ads (Search & Performance Max)'),
        ('META_ADS', 'Meta Ads (Facebook & Instagram Feed)'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'Pending Deployment'),
        ('ACTIVE', 'Active Serving'),
        ('PAUSED', 'Paused'),
        ('FAILED', 'Launch Failed'),
    ]

    incident = models.ForeignKey(
        Incident,
        related_name='campaigns',
        on_delete=models.CASCADE
    )
    platform = models.CharField(
        max_length=30,
        choices=PLATFORM_CHOICES
    )
    external_campaign_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Google/Meta external campaign ID"
    )
    ad_set_or_group_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Ad set or ad group ID"
    )
    budget_daily = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=50.00,
        help_text="Daily budget allocation in USD"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    raw_response = models.JSONField(
        null=True,
        blank=True,
        help_text="API response payload from ad network"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.platform} Campaign ({self.status}) - Incident {self.incident_id}"


class FormLead(models.Model):
    """
    Voluntary web intake submission from landing page with TCPA consent and TrustedForm audit.
    """
    lead_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    incident = models.ForeignKey(
        Incident,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='form_leads'
    )
    campaign = models.ForeignKey(
        GeoCampaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='form_leads'
    )
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(null=True, blank=True)
    preferred_contact = models.CharField(max_length=50, default='PHONE')
    message = models.TextField(blank=True)
    trustedform_cert_url = models.URLField(
        max_length=1000,
        null=True,
        blank=True,
        help_text="TrustedForm certificate token URL proving voluntary consumer consent"
    )
    user_consent = models.BooleanField(
        default=False,
        help_text="Explicit TCPA consent acknowledgment checkbox"
    )
    sent_to_support = models.BooleanField(
        default=False,
        help_text="Flag indicating whether handoff email was dispatched to support"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"FormLead: {self.full_name} ({self.phone_number})"


class CallLead(models.Model):
    """
    Inbound voice call lead processed by Vapi AI Assistant.
    Stores audio recording URL, full dialogue transcript, qualification summary, and handoff state.
    """
    vapi_call_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique call session ID from Vapi AI"
    )
    caller_phone = models.CharField(max_length=30)
    call_status = models.CharField(
        max_length=50,
        default='completed'
    )
    duration_seconds = models.IntegerField(default=0)
    summary = models.TextField(
        blank=True,
        help_text="AI-generated incident and injury triage summary"
    )
    transcript = models.TextField(
        blank=True,
        help_text="Complete dialogue transcript between AI assistant and caller"
    )
    recording_url = models.URLField(
        max_length=1000,
        null=True,
        blank=True,
        help_text="S3 / Vapi hosted audio recording MP3 URL"
    )
    priority = models.CharField(
        max_length=20,
        default='HIGH',
        help_text="Triage priority (CRITICAL, HIGH, MEDIUM, LOW)"
    )
    sent_to_support = models.BooleanField(
        default=False,
        help_text="Flag indicating whether handoff email was dispatched to support team"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"CallLead: {self.caller_phone} (Call: {self.vapi_call_id})"
