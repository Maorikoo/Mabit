from datetime import datetime
from django.utils import timezone
from instagram_scraper.models import InstagramUser, InstagramStory
from .media_downloader import download_media

def save_stories(username: str, stories: list[dict], log_callback=None):
    if not stories:
        return 0

    user = InstagramUser.objects.get(username=username)
    saved = 0
    
    for story in stories:
        story_id = story["story_id"]

        if InstagramStory.objects.filter(story_id=story_id).exists():
            continue
        saved += 1

        ts_str = story["timestamp"]  # "dd.mm.yy_HH.MM"
        ts_dt = datetime.strptime(ts_str, "%d.%m.%y_%H.%M")
        tz = timezone.get_current_timezone()
        ts_dt = timezone.make_aware(ts_dt, tz)


        ext = "jpg" if story["media_type"] == "image" else "mp4"
        filename = f"{user.username}-{ts_str}-{story_id}.{ext}"

        # Log download start
        if log_callback:
            log_callback(f"downloaded {filename}")

        file = download_media(story["media_url"], filename)
        if not file:
            continue

        InstagramStory.objects.create(
            username=user,      # ✅ FK field name in your model
            story_id=story_id,
            media_url=story["media_url"],
            media_type=story["media_type"],
            timestamp=ts_dt,
            media_file=file,
        )

    return saved
