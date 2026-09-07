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


class WebsiteVisitor(models.Model):
    """
    Session-based website visitor tracking model.
    Maintains a persistent visitor_id across months/years while creating separate
    session rows for each distinct 30-minute visit with full click-stream logs.
    """
    visitor_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Persistent visitor UUID across sessions"
    )
    session_id = models.CharField(
        max_length=150,
        unique=True,
        db_index=True,
        help_text="Unique browsing session identifier (30-min window)"
    )
    visit_number = models.PositiveIntegerField(
        default=1,
        help_text="Sequential visit counter (1 = First Visit, 2 = Second Visit, etc.)"
    )
    is_returning = models.BooleanField(
        default=False,
        help_text="Indicates whether this visit is from a returning visitor"
    )
    incident = models.ForeignKey(
        Incident,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visitors',
        help_text="Highway crash incident linked via ad click / UTM params"
    )
    campaign = models.ForeignKey(
        GeoCampaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='visitors',
        help_text="Associated GeoCampaign"
    )

    # Network & IP Geolocation
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Public IP address of the visitor"
    )
    country = models.CharField(max_length=100, blank=True, default='')
    region_state = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="State or province (e.g. Georgia, GA)"
    )
    city = models.CharField(max_length=150, blank=True, default='')
    postal_code = models.CharField(max_length=30, blank=True, default='')
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Estimated latitude from IP geolocation"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Estimated longitude from IP geolocation"
    )
    timezone = models.CharField(max_length=100, blank=True, default='')
    isp = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Internet Service Provider / Carrier (e.g. AT&T, Verizon)"
    )

    # Device & Browser Intelligence
    device_type = models.CharField(
        max_length=50,
        default='UNKNOWN',
        help_text="Device category: MOBILE, DESKTOP, TABLET, BOT"
    )
    browser = models.CharField(max_length=100, blank=True, default='')
    os = models.CharField(max_length=100, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')
    screen_resolution = models.CharField(max_length=50, blank=True, default='')
    language = models.CharField(max_length=50, blank=True, default='')

    # Navigation & Traffic Source
    page_url = models.URLField(max_length=1000, blank=True, default='', help_text="Full visited URL")
    page_path = models.CharField(max_length=255, blank=True, default='/')
    referrer = models.URLField(max_length=1000, blank=True, default='', help_text="Referrer source URL")
    utm_source = models.CharField(max_length=100, blank=True, default='')
    utm_medium = models.CharField(max_length=100, blank=True, default='')
    utm_campaign = models.CharField(max_length=150, blank=True, default='')
    utm_term = models.CharField(max_length=150, blank=True, default='')
    utm_content = models.CharField(max_length=150, blank=True, default='')
    gclid = models.CharField(max_length=255, blank=True, default='', help_text="Google Ads Click ID")
    fbclid = models.CharField(max_length=255, blank=True, default='', help_text="Meta Ads Click ID")

    # Click-stream & Interaction Logs
    clicked_elements = models.JSONField(
        default=list,
        blank=True,
        help_text="Chronological list of clicked elements, CTA buttons, and user actions in this session"
    )
    interaction_summary = models.TextField(
        blank=True,
        default='',
        help_text="Summary of notable user actions in this session"
    )

    # Timestamps
    visited_at = models.DateTimeField(auto_now_add=True, help_text="Session start timestamp")
    last_activity_at = models.DateTimeField(auto_now=True, help_text="Most recent activity timestamp in this session")

    class Meta:
        ordering = ['-visited_at']
        indexes = [
            models.Index(fields=['visitor_id', '-visited_at']),
            models.Index(fields=['session_id']),
            models.Index(fields=['ip_address', 'visited_at']),
            models.Index(fields=['region_state', 'city']),
            models.Index(fields=['device_type']),
        ]

    def __str__(self):
        loc = f"{self.city}, {self.region_state}" if self.city or self.region_state else "Unknown Location"
        visit_tag = f"Visit #{self.visit_number}" if self.is_returning else "New Visitor"
        return f"{visit_tag} ({self.visitor_id[:8]}) [{self.device_type}] {loc} - {self.visited_at.strftime('%b %d, %H:%M')}"


class WorkflowStatus(models.Model):
    """
    Tracks end-to-end automation execution, step-by-step state transitions, 
    and diagnostic error logs across all 4 POC workflows:
      1. Incident Poller (GDOT / 511 feed ingestion & geo radius calculation)
      2. Ad Campaign Trigger (Google Ads & Meta Ads template deployment)
      3. Form Lead Intake (Landing page intake, TrustedForm cert, & email handoff)
      4. Vapi Voice AI Handoff (Call transcript, audio recording, & support dispatch)
    """
    WORKFLOW_CHOICES = [
        ('INCIDENT_POLLER', '1. Incident Poller & Geo Target'),
        ('AD_CAMPAIGN_TRIGGER', '2. Ad Campaign Trigger (Google / Meta)'),
        ('FORM_LEAD_INTAKE', '3. Form Lead Intake & Consent'),
        ('VAPI_CALL_HANDOFF', '4. Vapi AI Voice Call Handoff'),
    ]

    STAGE_CHOICES = [
        ('INCIDENT_DETECTED', 'Incident Detected & Ingested'),
        ('GEO_RADIUS_CALCULATED', '5-10 Mile Radius Assigned'),
        ('CAMPAIGN_LIVE', 'Ad Campaign Live & Serving'),
        ('LEAD_CAPTURED', 'Lead Captured & Validated'),
        ('SENT_TO_SUPPORT', 'Email Dispatched to Support Team'),
        ('EXECUTION_FAILED', 'Execution Error Encountered'),
    ]

    STATUS_CHOICES = [
        ('SUCCESS', 'Success / Verified'),
        ('IN_PROGRESS', 'In Progress / Queued'),
        ('FAILED', 'Failed / Error'),
        ('WARNING', 'Warning / Partial'),
    ]

    workflow_name = models.CharField(
        max_length=60,
        choices=WORKFLOW_CHOICES,
        db_index=True,
        help_text="The automated workflow pipeline executing this step"
    )
    stage = models.CharField(
        max_length=60,
        choices=STAGE_CHOICES,
        help_text="Specific lifecycle milestone reached"
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default='SUCCESS',
        db_index=True,
        help_text="Execution health status"
    )

    # Entity Relations
    incident = models.ForeignKey(
        Incident,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_statuses',
        help_text="Associated crash incident"
    )
    campaign = models.ForeignKey(
        GeoCampaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_statuses',
        help_text="Associated Google/Meta geo campaign"
    )
    form_lead = models.ForeignKey(
        FormLead,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_statuses',
        help_text="Associated landing page form submission"
    )
    call_lead = models.ForeignKey(
        CallLead,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='workflow_statuses',
        help_text="Associated Vapi AI phone call"
    )

    # Diagnostic & Audit Metrics
    execution_time_ms = models.IntegerField(
        default=0,
        help_text="Duration of this workflow step in milliseconds"
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Exception trace or API error details if failed"
    )
    payload_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text="Input parameters, response payloads, or audit metadata"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Exact timestamp of this workflow execution step"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Workflow Status'
        verbose_name_plural = 'Workflow Statuses'
        indexes = [
            models.Index(fields=['workflow_name', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        incident_label = f" [Incident: {self.incident_id}]" if self.incident_id else ""
        return f"[{self.workflow_name}] {self.stage} -> {self.status}{incident_label}"

    @classmethod
    def log_event(
        cls,
        workflow_name,
        stage,
        status='SUCCESS',
        incident=None,
        campaign=None,
        form_lead=None,
        call_lead=None,
        execution_time_ms=0,
        error_message=None,
        payload_snapshot=None
    ):
        """
        Helper method to log workflow events across API endpoints and tasks cleanly.
        """
        return cls.objects.create(
            workflow_name=workflow_name,
            stage=stage,
            status=status,
            incident=incident,
            campaign=campaign,
            form_lead=form_lead,
            call_lead=call_lead,
            execution_time_ms=execution_time_ms,
            error_message=error_message,
            payload_snapshot=payload_snapshot or {}
        )



