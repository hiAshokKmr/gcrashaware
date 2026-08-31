import os
import requests
from io import BytesIO
from urllib.parse import urlparse
from django.core.files.base import ContentFile
from celery import shared_task


@shared_task
def process_incident_media_async(media_id):
    """
    Asynchronous worker task to download high-volume crash images and traffic video
    streams from external feeds and stream them directly into S3 / Cloudflare R2 storage.
    """
    from .models import IncidentMedia

    try:
        media_obj = IncidentMedia.objects.get(id=media_id)
    except IncidentMedia.DoesNotExist:
        return f"IncidentMedia {media_id} does not exist."

    media_obj.download_status = 'DOWNLOADING'
    media_obj.save(update_fields=['download_status'])

    source_url = media_obj.source_url
    if not source_url:
        media_obj.download_status = 'FAILED'
        media_obj.error_message = 'No source URL provided.'
        media_obj.save(update_fields=['download_status', 'error_message'])
        return f"Failed: No source URL for Media {media_id}"

    try:
        # Stream download with 30s timeout to prevent worker blocking
        response = requests.get(source_url, stream=True, timeout=30)
        response.raise_for_status()

        # Determine file extension and filename
        parsed_url = urlparse(source_url)
        filename = os.path.basename(parsed_url.path)
        if not filename or '.' not in filename:
            ext = '.mp4' if media_obj.media_type == 'VIDEO' else '.jpg'
            filename = f"incident_{media_obj.incident_id}_{media_id}{ext}"

        # Stream content into memory buffer
        buffer = BytesIO()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                buffer.write(chunk)

        file_size = buffer.tell()
        buffer.seek(0)

        # Save to Django Storage (S3 / R2 / local media)
        media_obj.file.save(filename, ContentFile(buffer.read()), save=False)
        media_obj.file_size_bytes = file_size
        media_obj.download_status = 'COMPLETED'
        media_obj.error_message = None
        media_obj.save(update_fields=['file', 'file_size_bytes', 'download_status', 'error_message'])

        return f"Successfully processed Media {media_id} ({file_size} bytes)"

    except requests.RequestException as exc:
        media_obj.download_status = 'FAILED'
        media_obj.error_message = f"HTTP/Network error: {str(exc)}"
        media_obj.save(update_fields=['download_status', 'error_message'])
        return f"Download failed for Media {media_id}: {str(exc)}"
    except Exception as exc:
        media_obj.download_status = 'FAILED'
        media_obj.error_message = f"Unexpected error: {str(exc)}"
        media_obj.save(update_fields=['download_status', 'error_message'])
        return f"Processing failed for Media {media_id}: {str(exc)}"


@shared_task
def trigger_geo_campaign_async(incident_id):
    """
    Asynchronous task to notify n8n / Ad automators to create 5-10 mile radius campaigns.
    """
    from .models import Incident
    from .services import dispatch_n8n_incident_webhook

    try:
        incident = Incident.objects.get(incident_id=incident_id)
        dispatch_n8n_incident_webhook(incident)
        return f"Dispatched n8n trigger for Incident {incident_id}"
    except Incident.DoesNotExist:
        return f"Incident {incident_id} not found."
