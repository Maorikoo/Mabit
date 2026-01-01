from .client import ScraperClient, trigger_global_pause, rotate_circuit_if_needed
from .parsers import parse_stories_request, parse_profile_request
from instagram_scraper.services.profile_saver import save_profile
from instagram_scraper.services.story_saver import save_stories
from django.conf import settings
import time


BASE_URL = "https://media.mollygram.com/"

def scrape_instagram(username: str, log_callback=None):
    client = ScraperClient()

    profile_url = f"{BASE_URL}?url={username}"
    profile_response = client.get(profile_url)
    profile_data = parse_profile_request(profile_response.text)

    status = (profile_data.get("status") or "").lower()
    msg = (profile_data.get("msg") or "").strip()  # Keep original case for comparison
    msg_lower = msg.lower()

    # ✅ BLOCK DETECTION
    if "temporarily blocked" in msg:
        if log_callback:
            log_callback(f"{username}: Block detected, Attempting to rotate Tor IP")
        
        # This function ensures only one thread rotates, others wait
        did_rotation = rotate_circuit_if_needed(log_callback=log_callback)
        
        if did_rotation:
            # This thread rotated the circuit - proceed normally
            if log_callback:
                log_callback(f"{username}: Circuit rotation complete.")
            
            return {
                "username": username,
                "profile": "blocked",
                "stories_found": 0,
                "stories_saved": 0,
                "pause_seconds": 0,
            }
        else:
            # Another thread is rotating - this thread should wait 60 seconds then retry
            if log_callback:
                log_callback(f"{username}: Another thread is rotating circuit. Waiting 60 seconds, then will retry with new IP...")
            
            time.sleep(60)  # Wait 60 seconds for the new IP to be ready
            
            if log_callback:
                log_callback(f"{username}: Wait complete. Retrying with new IP...")
            
            return {
                "username": username,
                "profile": "blocked",
                "stories_found": 0,
                "stories_saved": 0,
                "pause_seconds": 0,  # No additional pause needed, already waited 60s
            }
        
    # ✅ ERROR STATUS - check if it's a temporary server error
    # Only retry if message indicates temporary server unavailability
    # Otherwise, assume user doesn't exist and skip
    if status == "error":
        # Check if it's a temporary server error message
        is_temporary_error = False

        if "temporarily unavailable" in msg_lower:
            is_temporary_error = True
        
        if is_temporary_error:
            if log_callback:
                log_callback(f"{username}: Temporary server error detected - will retry...")
            
            return {
                "username": username,
                "profile": "error",  # Mark as error so it can be retried
                "stories_found": 0,
                "stories_saved": 0,
            }
        else:
            # Not a temporary error - assume user doesn't exist, skip immediately
            if log_callback:
                log_callback(f"{username}: Error detected ({msg}) - not a temporary error, skipping...")
            
            return {
                "username": username,
                "profile": "not_found",  # Mark as not_found so it's skipped
                "stories_found": 0,
                "stories_saved": 0,
            }

    # save profile normally (if not blocked or error)
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
