import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from PIL import Image
from tqdm import tqdm
from transformers import pipeline

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

# Your local keywords (NOT sent to the model)
DEFAULT_KEYWORDS = [
    "uniform", "camouflage", "soldier", "army", "military", "tank", "armored",
    "rifle", "weapon", "gun", "helicopter", "aircraft", "jet", "drone",
    "missile", "grenade", "base", "barracks", "parade"
]

STOPWORDS = {
    "a","an","the","and","or","of","in","on","at","with","to","for","from","by",
    "this","that","these","those","is","are","was","were","be","been","it","its",
    "as","into","over","under","near","inside","outside","during","while",
    "man","woman","people","person","photo","picture","image","scene","view"
}

def is_image(p: Path) -> bool:
    return p.suffix.lower() in IMAGE_EXTS

def is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS

import shutil

def ffmpeg_exists(ffmpeg_path: str) -> bool:
    return shutil.which(ffmpeg_path) is not None or Path(ffmpeg_path).exists()

def extract_frame_at_time(
    video_path: Path,
    out_path: Path,
    t_seconds: int,
    ffmpeg_path: str = "ffmpeg"
) -> Path | None:
    """
    Extract a single frame at time t_seconds.
    Returns the actual frame path if created, else None.
    """
    out_png = out_path.with_suffix(".png")

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", str(t_seconds),
        "-i", str(video_path),
        "-frames:v", "1",
        "-vf", "format=rgb24",
        str(out_png),
    ]

    subprocess.run(cmd, check=True)

    return out_png if out_png.exists() else None


def normalize_caption_for_compare(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def captions_similar(a: str, b: str) -> bool:
    """
    Simple similarity check without extra libs:
    - If identical after normalization -> True
    - Or high token overlap -> True
    """
    na = normalize_caption_for_compare(a)
    nb = normalize_caption_for_compare(b)
    if not na or not nb:
        return False
    if na == nb:
        return True

    A = set(na.split())
    B = set(nb.split())
    if not A or not B:
        return False
    jaccard = len(A & B) / len(A | B)
    return jaccard >= 0.9  # strict; tweak to 0.85 if needed

def normalize_token(t: str) -> str:
    t = t.strip().lower()
    t = re.sub(r"[^a-z0-9\s\-]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def extract_tags_from_text(text: str, max_tags: int = 20) -> list[str]:
    """
    Convert caption/tag-string into a normalized tag list.
    Works even if model returns a sentence.
    """
    # split by commas first; if none, split by words
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        parts = re.split(r"\s+", text)

    tags = []
    for p in parts:
        tok = normalize_token(p)
        if not tok or tok in STOPWORDS:
            continue
        # keep short phrases like "military vehicle" if caption provides them
        if len(tok) <= 2:
            continue
        tags.append(tok)

    # de-duplicate in order
    seen = set()
    dedup = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            dedup.append(t)

    return dedup[:max_tags]

def model_generate_caption_and_tags(img2txt, img_path: Path):
    """
    Uses an image-to-text model to generate:
    - caption (natural language)
    - tags_text (comma-separated tags if the model follows the prompt)
    """
    with Image.open(img_path) as im:
        im = im.convert("RGB")

        # 1) caption
        cap_out = img2txt(im)
        caption = cap_out[0]["generated_text"] if cap_out else ""

    return caption.strip(), ""

def keyword_hits(tags: list[str], keywords: list[str]):
    """
    Local matching only. Returns matched keywords.
    Matching is:
    - exact keyword in tag
    - keyword appears as substring in tag OR tag appears as substring in keyword (helps phrases)
    """
    kw_norm = [normalize_token(k) for k in keywords if normalize_token(k)]
    tags_norm = [normalize_token(t) for t in tags if normalize_token(t)]

    hits = set()
    for k in kw_norm:
        for t in tags_norm:
            if k == t or k in t or t in k:
                hits.add(k)
    return sorted(hits)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Folder containing images/videos")

    # Image-to-text model (captioning)
    ap.add_argument(
        "--caption-model",
        default="Salesforce/blip-image-captioning-base",
        help='Image-to-text model. Default: Salesforce/blip-image-captioning-base',
    )

    # Your local keywords (NOT sent to model)
    ap.add_argument(
        "--keywords",
        default="",
        help="Comma-separated keywords you want to flag on (kept local; not sent to AI).",
    )

    # Video handling
    ap.add_argument("--video-every-seconds", type=int, default=3)
    ap.add_argument("--max-video-frames", type=int, default=60)

    ap.add_argument("--out", default="media_ai_tags.jsonl")
    ap.add_argument("--ffmpeg-path", default="ffmpeg", help="Path to ffmpeg.exe or 'ffmpeg' if in PATH")
    ap.add_argument("--static-check-seconds", type=int, default=1,help="Compare frame at t=0 and t=this value to detect 'image-as-video'")
    ap.add_argument("--max-video-seconds", type=int, default=180,help="Limit scan to first N seconds of each video for speed (0 = no limit)")

    args = ap.parse_args()

    root = Path(args.path).expanduser().resolve()
    if not root.exists():
        raise SystemExit(f"Path not found: {root}")

    keywords = [s.strip() for s in args.keywords.split(",") if s.strip()] or DEFAULT_KEYWORDS

    # Image-to-text pipeline (model does NOT receive your keywords)
    img2txt = pipeline("image-to-text", model=args.caption_model)

    media = [p for p in root.rglob("*") if p.is_file() and (is_image(p) or is_video(p))]
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for p in tqdm(media, desc="Tagging (AI-generated tags)"):
            item = {
                "path": str(p),
                "type": "image" if is_image(p) else "video",
            }

            try:
                if is_image(p):
                    caption, _ = model_generate_caption_and_tags(img2txt, p)
                    tags = extract_tags_from_text(caption, max_tags=25)
                    hits = keyword_hits(tags, keywords)

                    item.update({
                        "caption": caption,
                        "tags": tags,
                        "hits": hits,
                        "is_interesting": len(hits) > 0,
                    })
                else:
                    # Video: extract frames at timestamps and early-stop
                    if not ffmpeg_exists(args.ffmpeg_path):
                        raise FileNotFoundError(
                            f"ffmpeg not found. Tried: {args.ffmpeg_path}. "
                            f"Either add ffmpeg to PATH or pass --ffmpeg-path C:\\path\\to\\ffmpeg.exe"
                        )

                    with tempfile.TemporaryDirectory() as td:
                        td_path = Path(td)

                        # --- 1) Static-video check (t=0 vs t=static_check_seconds) ---
                        # (extension here is irrelevant; extractor will write .png anyway)
                        f0 = td_path / "frame_000000.png"
                        f1 = td_path / "frame_000001.png"

                        # Extract first frame
                        frame0 = extract_frame_at_time(p, f0, 0, ffmpeg_path=args.ffmpeg_path)
                        if frame0 is None:
                            raise RuntimeError("Failed to extract first frame")

                        cap0, _ = model_generate_caption_and_tags(img2txt, frame0)

                        # Extract second frame (1s by default). If it fails, treat as non-static.
                        static_video = False
                        try:
                            frame1 = extract_frame_at_time(p, f1, args.static_check_seconds, ffmpeg_path=args.ffmpeg_path)
                            if frame1 is not None:
                                cap1, _ = model_generate_caption_and_tags(img2txt, frame1)
                                if captions_similar(cap0, cap1):
                                    static_video = True
                        except Exception:
                            static_video = False

                        # If it's static, treat it like an image: just analyze the first frame and move on.
                        tags0 = extract_tags_from_text(cap0, max_tags=25)
                        hits0 = keyword_hits(tags0, keywords)

                        if static_video:
                            item.update({
                                "frames_analyzed": 2,
                                "static_video": True,
                                "caption": cap0,
                                "tags": tags0,
                                "hits": hits0,
                                "is_interesting": len(hits0) > 0,
                                "note": "Detected as static (image-as-video) by comparing first two frame captions."
                            })
                        else:
                            # --- 2) Scan frames over time with early stop on hit ---
                            frame_summaries = []
                            hit_counts = {}
                            any_hit = False

                            # Record t=0 analysis
                            frame_summaries.append({
                                "t": 0,
                                "caption": cap0,
                                "tags": tags0[:12],
                                "hits": hits0,
                                "is_interesting": len(hits0) > 0,
                            })
                            if hits0:
                                any_hit = True
                                for h in hits0:
                                    hit_counts[h] = hit_counts.get(h, 0) + 1

                            if not any_hit:
                                max_frames = args.max_video_frames
                                step = args.video_every_seconds
                                max_t = args.max_video_seconds

                                frames_used = 1
                                t = step

                                while frames_used < max_frames:
                                    if max_t > 0 and t > max_t:
                                        break

                                    out_frame = td_path / f"frame_{frames_used:06d}.png"

                                    try:
                                        frame_path = extract_frame_at_time(p, out_frame, t, ffmpeg_path=args.ffmpeg_path)
                                        if frame_path is None:
                                            break
                                    except subprocess.CalledProcessError:
                                        break

                                    caption, _ = model_generate_caption_and_tags(img2txt, frame_path)
                                    tags = extract_tags_from_text(caption, max_tags=25)
                                    hits = keyword_hits(tags, keywords)

                                    frame_summaries.append({
                                        "t": t,
                                        "caption": caption,
                                        "tags": tags[:12],
                                        "hits": hits,
                                        "is_interesting": len(hits) > 0,
                                    })

                                    if hits:
                                        any_hit = True
                                        for h in hits:
                                            hit_counts[h] = hit_counts.get(h, 0) + 1
                                        break  # Early stop

                                    frames_used += 1
                                    t += step

                            hit_summary = sorted(
                                [{"keyword": k, "frames_hit": c} for k, c in hit_counts.items()],
                                key=lambda x: x["frames_hit"],
                                reverse=True
                            )

                            item.update({
                                "static_video": False,
                                "frames_analyzed": len(frame_summaries),
                                "is_interesting": any_hit,
                                "hit_summary": hit_summary,
                                "sample_frames": frame_summaries[:10],
                            })



            except subprocess.CalledProcessError as e:
                item["error"] = f"ffmpeg failed: {e}"
            except Exception as e:
                item["error"] = str(e)

            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Done. Wrote: {out_path}")

if __name__ == "__main__":
    main()
