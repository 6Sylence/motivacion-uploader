"""Daily motivation pipeline: script -> narration -> images -> render -> upload.

Run locally (no upload, short):
    python -m src.pipeline --no-upload --seconds 20

In CI the workflow calls it with no flags for a full daily upload.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import os
from pathlib import Path

from . import ai_image, ai_voice, metadata, music, scripts, tts, video

ROOT = Path(__file__).resolve().parent.parent

# Hidden marker appended to tags so a future learning loop can map a video back
# to the theme that produced it (view-velocity ranking, like the music channel).
THEME_TAG = "mot-"


def _env(name: str, default=None):
    return os.environ.get(name, default)


def _daily_seed(date: _dt.date, slot: int) -> int:
    h = hashlib.sha256(f"{date.isoformat()}::{slot}".encode()).hexdigest()
    return int(h[:8], 16)


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Render/upload a daily motivation video.")
    p.add_argument("--out-dir", default=_env("OUT_DIR", str(ROOT / "out")))
    p.add_argument("--slot", type=int, default=int(_env("SLOT", "0") or "0"))
    p.add_argument("--date", default=_env("RUN_DATE") or None, help="YYYY-MM-DD")
    p.add_argument("--seconds", type=float, default=float(_env("MAX_SECONDS", "0") or "0"),
                   help="Cap narration length for quick tests (0 = full script).")
    p.add_argument("--slides", type=int, default=int(_env("SLIDES", "5") or "5"))
    p.add_argument("--privacy", default=_env("PRIVACY", "public"),
                   choices=["public", "unlisted", "private"])
    p.add_argument("--no-upload", action="store_true",
                   default=str(_env("NO_UPLOAD", "")).lower() in ("1", "true", "yes"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    date = _dt.date.fromisoformat(args.date) if args.date else _dt.date.today()
    seed = _daily_seed(date, args.slot)
    out_dir = Path(args.out_dir)
    work = out_dir / "work"
    work.mkdir(parents=True, exist_ok=True)
    channel = metadata.CHANNEL_NAME

    # 1. Script -------------------------------------------------------------
    title_theme, keyword, body = scripts.build_script(seed)
    if args.seconds and args.seconds > 0:
        # trim to a couple of sentences for a fast smoke test
        body = " ".join(body.split(". ")[:2]).strip()
        if not body.endswith("."):
            body += "."
    print(f"[1/5] script: '{title_theme}' ({len(body.split())} words)")

    # 2. Narration — ElevenLabs (emotional) if configured, else edge-tts -----
    voice_engine = "edge-tts"
    if ai_voice.available():
        try:
            narration, words, dur = ai_voice.narrate(body, work)
            voice_engine = "elevenlabs"
        except ai_voice.AIVoiceError as exc:
            print(f"    [voice] ElevenLabs failed ({exc}); falling back to edge-tts")
            narration, words, dur = tts.narrate(body, work)
    else:
        narration, words, dur = tts.narrate(body, work)
    if words:
        cues = tts.group_captions(words)
        cap_src = "word-synced"
    else:
        cues = tts.captions_from_text(body, dur)
        cap_src = "even-timed (no word events)"
    total = max(dur + 1.5, 8.0)
    print(f"[2/5] narration ({voice_engine}): {dur:.1f}s, "
          f"{len(cues)} caption cues [{cap_src}]")

    # 3. Cinematic images (Cloudflare FLUX, best-effort) -------------------
    n_slides = max(3, args.slides)
    slides = ai_image.generate_slideshow(work / "img", seed, count=n_slides)
    print(f"[3/5] images: {len(slides)} AI slides"
          + ("" if slides else " (using procedural gradients)"))

    # 4. Music bed + render -------------------------------------------------
    bed = music.build_bed(total + 1.0, work / "bed.wav", seed)
    final = out_dir / "video.mp4"
    video.build_video(slides, cues, narration, bed, channel, work, final, total)
    thumb_base = slides[0] if slides else None
    thumb = video.build_thumbnail(title_theme, thumb_base, channel,
                                  out_dir / "thumb.jpg")
    print(f"[4/5] render: {final} ({video._probe_duration(final):.1f}s)")

    # 5. Upload -------------------------------------------------------------
    meta = metadata.build_metadata(title_theme, keyword, body, seed, date,
                                   tag_marker=f"{THEME_TAG}{seed % len(scripts.THEMES)}")
    meta["privacyStatus"] = args.privacy
    if args.no_upload:
        print(f"[5/5] no-upload: '{meta['title']}'")
        print(f"[status] theme='{title_theme}' slides={len(slides)} "
              f"dur={total:.1f}s privacy={args.privacy}")
        return 0

    from . import upload_youtube
    upload_youtube.verify_credentials()
    video_id = upload_youtube.upload_video(final, meta, thumbnail_path=thumb)
    try:
        upload_youtube.add_to_playlist(video_id, meta["playlist"])
    except Exception as exc:
        print(f"playlist add skipped: {exc}")
    print(f"[5/5] uploaded https://youtu.be/{video_id}")
    print(f"[status] theme='{title_theme}' slides={len(slides)} "
          f"dur={total:.1f}s id={video_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
