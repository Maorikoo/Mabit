from .client import ScraperClient, trigger_global_pause
from .tor_control import TorController
from .parsers import parse_stories_request, parse_profile_request
from instagram_scraper.services.profile_saver import save_profile
from instagram_scraper.services.story_saver import save_stories

BASE_URL = "https://media.mollygram.com/"

def scrape_instagram(username: str, log_callback=None):
    client = ScraperClient()

    profile_url = f"{BASE_URL}?url={username}"
    profile_response = client.get(profile_url)
    profile_data = parse_profile_request(profile_response.text)

    status = (profile_data.get("status") or "").lower()
    msg = (profile_data.get("msg") or "").lower()

    # ✅ BLOCK DETECTION
    if "temporarily blocked" in msg:
        # pause everyone and rotate Tor IP (new circuit)
        pause_s = 1 + int(__import__("random").uniform(0, 5))
        tor = TorController()
        tor.new_identity()  # Request a new Tor IP
        trigger_global_pause(pause_s)
        return {
            "username": username,
            "profile": "blocked",
            "stories_found": 0,
            "stories_saved": 0,
            "pause_seconds": pause_s,
        }

    # save profile normally (if not blocked)
    save_profile(username, profile_data)

    if status != "public":
        # treat private/unknown/not_found however you already do
        return {"username": username, "profile": status or "unknown", "stories_found": 0, "stories_saved": 0}

    stories_url = f"{BASE_URL}?url={username}&method=allstories"
    stories_response = client.get(stories_url)
    stories = parse_stories_request(stories_response.text)

    # Log starting to download stories if there are any
    if stories and log_callback:
        log_callback(f"{username} public, starting to download stories")

    saved_count = save_stories(username, stories, log_callback=log_callback)

    return {
        "username": username,
        "profile": "public",
        "stories_found": len(stories),
        "stories_saved": saved_count,
    }
