import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# -----------------------------
# Django bootstrap
# -----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Mabit.settings")

import django  # noqa
django.setup()

from django.utils import timezone  # noqa
from instagram_scraper.models import InstagramStory  # noqa

# -----------------------------
# Your POC functions (imported)
# -----------------------------
import classify_media as cm  # your uploaded file

from transformers import pipeline


# -----------------------------
# Config
# -----------------------------
CAPTION_MODEL = os.environ.get("AI_CAPTION_MODEL", "Salesforce/blip-image-captioning-base")
FFMPEG_PATH = str(BASE_DIR / "ffmpeg" / "bin" / "ffmpeg.exe")

# keywords: same behavior as your POC (env override or default list)
KEYWORDS_ENV = os.environ.get("AI_KEYWORDS", "").strip()
KEYWORDS: List[str] = [s.strip() for s in KEYWORDS_ENV.split(",") if s.strip()] if KEYWORDS_ENV else cm.DEFAULT_KEYWORDS

POLL_SECONDS = int(os.environ.get("AI_POLL_SECONDS", "3"))
BATCH_SIZE = int(os.environ.get("AI_BATCH_SIZE", "10"))

# Video options similar to your POC defaults :contentReference[oaicite:6]{index=6}
VIDEO_EVERY_SECONDS = int(os.environ.get("AI_VIDEO_EVERY_SECONDS", "3"))
MAX_VIDEO_FRAMES = int(os.environ.get("AI_MAX_VIDEO_FRAMES", "60"))
STATIC_CHECK_SECONDS = int(os.environ.get("AI_STATIC_CHECK_SECONDS", "1"))
MAX_VIDEO_SECONDS = int(os.environ.get("AI_MAX_VIDEO_SECONDS", "180"))  # 0 = no limit


# -----------------------------
# Model init (once)
# -----------------------------
IMG2TXT = pipeline("image-to-text", model=CAPTION_MODEL)


def analyze_image(path: Path) -> Dict[str, Any]:
    caption, _ = cm.model_generate_caption_and_tags(IMG2TXT, path)
    tags = cm.extract_tags_from_text(caption, max_tags=25)
    hits = cm.keyword_hits(tags, KEYWORDS)
    return {
        "caption": caption,
        "hits": hits,
        "is_interesting": len(hits) > 0,
    }


def analyze_video(path: Path) -> Dict[str, Any]:
    if not cm.ffmpeg_exists(FFMPEG_PATH):
        raise FileNotFoundError(
            f"ffmpeg not found. Tried: {FFMPEG_PATH}. Put ffmpeg in PATH or set AI_FFMPEG_PATH."
        )

    import tempfile

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)

        # 1) Static-video check (t=0 vs t=STATIC_CHECK_SECONDS) :contentReference[oaicite:7]{index=7}
        f0 = td_path / "frame_000000.png"
        f1 = td_path / "frame_000001.png"

        frame0 = cm.extract_frame_at_time(path, f0, 0, ffmpeg_path=FFMPEG_PATH)
        if frame0 is None:
            raise RuntimeError("Failed to extract first frame")

        cap0, _ = cm.model_generate_caption_and_tags(IMG2TXT, frame0)

        static_video = False
        try:
            frame1 = cm.extract_frame_at_time(path, f1, STATIC_CHECK_SECONDS, ffmpeg_path=FFMPEG_PATH)
            if frame1 is not None:
                cap1, _ = cm.model_generate_caption_and_tags(IMG2TXT, frame1)
                if cm.captions_similar(cap0, cap1):
                    static_video = True
        except Exception:
            static_video = False

        if static_video:
            # treat like image: analyze first frame
            tags0 = cm.extract_tags_from_text(cap0, max_tags=25)
            hits0 = cm.keyword_hits(tags0, KEYWORDS)
            return {
                "caption": cap0,
                "hits": hits0,
                "is_interesting": len(hits0) > 0,
            }

        # 2) Scan frames with early stop on hit :contentReference[oaicite:8]{index=8}
        frame_summaries = []
        hit_counts: Dict[str, int] = {}
        any_hit = False

        # record t=0 analysis
        tags0 = cm.extract_tags_from_text(cap0, max_tags=25)
        hits0 = cm.keyword_hits(tags0, KEYWORDS)
        frame_summaries.append({"t": 0, "caption": cap0, "hits": hits0})
        if hits0:
            any_hit = True
            for h in hits0:
                hit_counts[h] = hit_counts.get(h, 0) + 1

        if not any_hit:
            frames_used = 1
            t = VIDEO_EVERY_SECONDS

            while frames_used < MAX_VIDEO_FRAMES:
                if MAX_VIDEO_SECONDS > 0 and t > MAX_VIDEO_SECONDS:
                    break

                out_frame = td_path / f"frame_{frames_used:06d}.png"
                try:
                    frame_path = cm.extract_frame_at_time(path, out_frame, t, ffmpeg_path=FFMPEG_PATH)
                    if frame_path is None:
                        break
                except Exception:
                    break

                caption, _ = cm.model_generate_caption_and_tags(IMG2TXT, frame_path)
                tags = cm.extract_tags_from_text(caption, max_tags=25)
                hits = cm.keyword_hits(tags, KEYWORDS)

                frame_summaries.append({"t": t, "caption": caption, "hits": hits})

                if hits:
                    any_hit = True
                    for h in hits:
                        hit_counts[h] = hit_counts.get(h, 0) + 1
                    break  # early stop

                frames_used += 1
                t += VIDEO_EVERY_SECONDS

        # YOUR RULE: for videos, store "caption" as all frame captions joined
        joined_caption = "\n".join([f't={fs["t"]}: {fs["caption"]}' for fs in frame_summaries])

        all_hits = sorted(hit_counts.keys())
        return {
            "caption": joined_caption,
            "hits": all_hits,
            "is_interesting": any_hit,
        }


def analyze_path(path_str: str) -> Dict[str, Any]:
    p = Path(path_str)
    if cm.is_image(p):
        return analyze_image(p)
    if cm.is_video(p):
        return analyze_video(p)
    raise ValueError(f"Unsupported file type: {p.suffix}")


def process_instagram_stories(batch_size: int) -> int:
    qs = (
        InstagramStory.objects
        .filter(media_file__isnull=False, ai_analyzed_at__isnull=True)
        .order_by("timestamp")[:batch_size]
    )

    stories = list(qs)
    processed = 0

    for s in stories:
        # ensure file path exists
        try:
            local_path = s.media_file.path
        except Exception as e:
            print(f"[SKIP] story_id={s.story_id} no local file path: {e}")
            continue

        try:
            result = analyze_path(local_path)

            s.ai_caption = result["caption"] or ""
            s.ai_hits = result["hits"] or []
            s.ai_is_interesting = bool(result["is_interesting"])
            s.ai_analyzed_at = timezone.now()
            s.save(update_fields=["ai_caption", "ai_hits", "ai_is_interesting", "ai_analyzed_at"])

            processed += 1
            print(f"[OK] IG story_id={s.story_id} interesting={s.ai_is_interesting} hits={s.ai_hits}")

        except Exception as e:
            # Leave ai_analyzed_at NULL so it retries later
            print(f"[ERR] IG story_id={s.story_id}: {e}")

    return processed


def main():
    print("[AI SERVICE] Started.")
    print(f"[AI SERVICE] model={CAPTION_MODEL}")
    print(f"[AI SERVICE] keywords={KEYWORDS}")
    print(f"[AI SERVICE] poll={POLL_SECONDS}s batch={BATCH_SIZE}")

    while True:
        total = 0
        total += process_instagram_stories(BATCH_SIZE)

        # later:
        # total += process_facebook_posts(BATCH_SIZE)
        # total += process_tiktok_videos(BATCH_SIZE)

        if total == 0:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
