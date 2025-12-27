from django.utils import timezone
from instagram_scraper.models import InstagramUser
from .media_downloader import download_media

def save_profile(username: str, profile_data: dict):
    is_private = (profile_data.get("status") == "private")
    profile_pic_url = profile_data.get("profile_pic_url")

    user, created = InstagramUser.objects.get_or_create(
        username=username,
        defaults={
            "is_private": is_private,
            "last_scraped": timezone.now(),
        }
    )

    # Always update these
    user.is_private = is_private
    user.last_scraped = timezone.now()

    # Replace profile pic only if we got one
    if profile_pic_url:
        filename = f"{username}_profile.jpg"
        file_content = download_media(profile_pic_url, filename)

        if file_content:
            # ✅ delete previous file so we don't accumulate files
            if user.profile_pic and user.profile_pic.name:
                user.profile_pic.delete(save=False)

            # ✅ save new file (same filename is fine; storage will handle it)
            user.profile_pic.save(filename, file_content, save=False)

    user.save()
    return user

