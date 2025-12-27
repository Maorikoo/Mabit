import json
import re
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
from datetime import timedelta
from django.utils import timezone


def parse_profile_request(raw: str) -> dict:
    """
    Parses profile request response.
    Handles:
    - error responses (blocked, not found, etc.)
    - public / private profiles
    """

    result = {
        "status": "error",
        "msg": "",
        "profile_pic_url": "",
    }

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        result["msg"] = "invalid json response"
        return result

    # ✅ 1) SERVER ERROR (blocked, not found, etc.)
    if data.get("status") == "error":
        result["status"] = "error"
        result["msg"] = data.get("msg", "")
        return result

    # ✅ 2) PRIVATE ACCOUNT
    if data.get("source") == "AccountPrivate":
        result["status"] = "private"
        return result

    # ✅ 3) PUBLIC ACCOUNT
    result["status"] = "public"

    # Extract profile picture from HTML (only when public)
    html = data.get("html", "")
    if html:
        soup = BeautifulSoup(html, "html.parser")
        img_tag = soup.find("img")
        if img_tag:
            result["profile_pic_url"] = img_tag.get("src", "")

    return result


def parse_stories_request(raw: str):
    data = json.loads(raw)

    # handle "no stories"
    if data.get("status") != "ok":
        return []

    html = data.get("html", "")
    soup = BeautifulSoup(html, "html.parser")

    stories = []

    media_nodes = soup.find_all(["img", "video"])
    for node in media_nodes:
        container = node.find_parent("div", class_="col-md-4")
        if not container:
            continue


        # detect type + url
        if node.name == "video":
            source = node.find("source")
            if not source or not source.get("src"):
                continue
            media_url = source["src"]
            media_type = "video"
        else:
            if not node.get("src"):
                continue
            media_url = node["src"]
            media_type = "image"

        # prefer "Download HD" link if exists
        download_a = container.find("a", id="download-video")
        if download_a and download_a.get("href"):
            media_url = download_a["href"]
        
        if "media.php" not in media_url:
            continue


        small = container.find("small")
        time_text = small.get_text(strip=True) if small else None
        timestamp = parse_time_ago(time_text)

        # ✅ CONVERT HERE
        timestamp = parse_time_ago(time_text)

        story_id = extract_story_id(media_url)

        stories.append({
            "story_id": story_id,
            "media_url": media_url,
            "media_type": media_type,
            "timestamp": timestamp,  # ✅ final value
        })

    return stories


def extract_story_id(media_url: str) -> str:
    """
    Try to get a stable ID.
    1) If URL has ?name=..._<digits> use those digits
    2) Else if URL has ?media=... use that as base
    3) Else fallback to sha1(url)
    """
    parsed = urlparse(media_url)
    qs = parse_qs(parsed.query)

    # name=anonimostory.com_Instagram_user_3796214496960974769
    if "name" in qs and qs["name"]:
        m = re.search(r"_(\d+)$", qs["name"][0])
        if m:
            return m.group(1)

    # sometimes media= contains the real IG url encoded
    if "media" in qs and qs["media"]:
        inner = unquote(qs["media"][0])
        # try to catch ig_cache_key (not always numeric), else hash inner
        return hashlib.sha1(inner.encode("utf-8")).hexdigest()[:32]

    return hashlib.sha1(media_url.encode("utf-8")).hexdigest()[:32]


_TIME_RE = re.compile(
    r"(\d+)\s*(second|seconds|minute|minutes|hour|hours|day|days)\s*ago",
    re.I
)

def parse_time_ago(time_text: str) -> str:
    """
    Converts:
      "20 hours ago"
      "5 minutes ago"
      "12 seconds ago"
      "1 day ago"
    into:
      "dd.mm.yy_HH.MM"
    """
    now = timezone.localtime(timezone.now())

    if not time_text:
        return now.strftime("%d.%m.%y_%H.%M")

    text = time_text.strip().lower()
    match = _TIME_RE.search(text)

    if not match:
        return now.strftime("%d.%m.%y_%H.%M")

    value = int(match.group(1))
    unit = match.group(2)

    if "second" in unit:
        upload_time = now - timedelta(seconds=value)
    elif "minute" in unit:
        upload_time = now - timedelta(minutes=value)
    elif "hour" in unit:
        upload_time = now - timedelta(hours=value)
    elif "day" in unit:
        upload_time = now - timedelta(days=value)
    else:
        upload_time = now

    return upload_time.strftime("%d.%m.%y_%H.%M")
