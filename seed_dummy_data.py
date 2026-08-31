#!/usr/bin/env python
"""
Seed script to populate realistic dummy data across all 5 Django models for GCrashAware.
Run with: python seed_dummy_data.py
"""
import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gcrashaware.settings')
django.setup()

from core.models import Incident, IncidentMedia, GeoCampaign, FormLead, CallLead


def seed():
    print("[*] Seeding GCrashAware Database with realistic Georgia incident and lead dummy data...\n")

    # 1. Create Incidents
    inc1, created = Incident.objects.update_or_create(
        incident_id="INC-GA-85-20260831-01",
        defaults={
            "source": "GDOT_NaviGAtor_511",
            "incident_type": "Multi-car Collision",
            "latitude": 33.918900,
            "longitude": -84.254200,
            "city_area": "I-85 North near Spaghetti Junction (I-285 Interchange)",
            "occurred_at": timezone.now() - timedelta(minutes=45),
            "target_radius_miles": 7,
            "status": "CAMPAIGN_TRIGGERED"
        }
    )
    print(f"[+] Created/Updated Incident: {inc1.incident_id} ({inc1.city_area})")

    inc2, created = Incident.objects.update_or_create(
        incident_id="INC-GA-75-20260831-02",
        defaults={
            "source": "GDOT_NaviGAtor_511",
            "incident_type": "Hydroplane Incident on Exit Ramp",
            "latitude": 33.584300,
            "longitude": -84.339600,
            "city_area": "I-75 South near Exit 233 (Morrow / Clayton County)",
            "occurred_at": timezone.now() - timedelta(minutes=20),
            "target_radius_miles": 6,
            "status": "ACTIVE"
        }
    )
    print(f"[+] Created/Updated Incident: {inc2.incident_id} ({inc2.city_area})")

    # 2. Create IncidentMedia for Incident 1
    m1, _ = IncidentMedia.objects.get_or_create(
        incident=inc1,
        source_url="https://images.unsplash.com/photo-1590362891991-f776e747a588?w=800",
        defaults={
            "media_type": "IMAGE",
            "download_status": "COMPLETED",
            "file_size_bytes": 482910
        }
    )
    m2, _ = IncidentMedia.objects.get_or_create(
        incident=inc1,
        source_url="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        defaults={
            "media_type": "VIDEO",
            "download_status": "PENDING",
            "file_size_bytes": None
        }
    )
    print(f"[+] Created IncidentMedia records for {inc1.incident_id}")

    # 3. Create GeoCampaigns
    c1, _ = GeoCampaign.objects.get_or_create(
        incident=inc1,
        platform="GOOGLE_ADS",
        defaults={
            "external_campaign_id": "gads_ga85_7mi_98234",
            "ad_set_or_group_id": "grp_accident_relief_01",
            "budget_daily": 150.00,
            "status": "ACTIVE",
            "raw_response": {
                "headline": "I-85 Incident Assistance - 24/7 Roadside & Legal Intake",
                "clicks": 14,
                "impressions": 185
            }
        }
    )
    c2, _ = GeoCampaign.objects.get_or_create(
        incident=inc1,
        platform="META_ADS",
        defaults={
            "external_campaign_id": "meta_ga85_7mi_11209",
            "ad_set_or_group_id": "adset_spaghetti_jct_01",
            "budget_daily": 125.00,
            "status": "ACTIVE",
            "raw_response": {
                "headline": "Accident Relief for I-85 / I-285 Motorists",
                "clicks": 28,
                "impressions": 490
            }
        }
    )
    print(f"[+] Created GeoCampaigns for {inc1.incident_id}")

    # 4. Create FormLead
    lead1, _ = FormLead.objects.get_or_create(
        phone_number="+1 (404) 555-8910",
        defaults={
            "incident": inc1,
            "campaign": c1,
            "full_name": "Marcus Vance",
            "email": "marcus.vance@gmail.com",
            "preferred_contact": "PHONE",
            "message": "Rear-ended by box truck on I-85 North near exit 95. Trunk smashed in, seeking injury representation and approved tow yard coordination.",
            "trustedform_cert_url": "https://cert.trustedform.com/7b3f91a2e4c0d18f09234bcf90123",
            "user_consent": True,
            "sent_to_support": True
        }
    )
    print(f"[+] Created FormLead: {lead1.full_name} ({lead1.phone_number})")

    # 5. Create CallLead
    call1, _ = CallLead.objects.get_or_create(
        vapi_call_id="vapi_session_88192039",
        defaults={
            "caller_phone": "+1 (770) 555-3412",
            "call_status": "COMPLETED",
            "duration_seconds": 138,
            "priority": "HIGH",
            "summary": "Multi-car collision on I-75 South near Exit 233. Paramedics on scene evaluating minor wrist sprain. Vehicle non-drivable. Requested urgent legal consult before speaking with insurance adjusters.",
            "transcript": (
                "Assistant (Sarah): Thank you for calling Georgia Incident Support. My name is Sarah. I'm an AI assistant on a recorded line. Is anyone at the scene in need of emergency medical attention?\n"
                "Caller: No, paramedics are already here checking our wrists. I was rear-ended on I-75 Exit 233.\n"
                "Assistant: I am glad you are being looked after. Did law enforcement arrive?\n"
                "Caller: Yes, GSP is writing up the incident report right now. My car cannot be driven.\n"
                "Assistant: Understood. I am logging your case on I-75 South. I am dispatching your intake to our senior legal and roadside coordinator right away.\n"
                "Caller: Thank you, please have them call this cell phone."
            ),
            "recording_url": "https://vapi-recordings.s3.amazonaws.com/calls/vapi_session_88192039.mp3",
            "sent_to_support": True
        }
    )
    print(f"[+] Created CallLead: {call1.caller_phone} (Session: {call1.vapi_call_id})")

    print("\n[SUCCESS] Seeding completed successfully! All 5 models populated.")


if __name__ == '__main__':
    seed()
