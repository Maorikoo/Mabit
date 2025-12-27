import requests
from django.core.files.base import ContentFile

def download_media(url: str, filename: str):
    try:
        # Adding a UA sometimes helps with media endpoints
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return ContentFile(response.content, name=filename)
    except Exception:
        return None
