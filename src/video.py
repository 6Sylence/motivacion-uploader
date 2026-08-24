"""Render the motivational video: cinematic Ken-Burns slideshow + word-synced
burned captions + brand mark, with the narration mixed over a ducked music bed.

Pure ffmpeg + Pillow, no sampled assets. Falls back to procedurally drawn
gradient slides when no AI images are available, so a render never fails.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np

W, H = 1920, 1080
FPS = 30

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _font_path() -> str:
    for p in _FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return _FONT_CANDIDATES[0]


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + proc.stderr[-2500:])


def _probe_duration(path: str | Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Procedural fallback slides (used when AI images are unavailable)
# ---------------------------------------------------------------------------
_GRADIENTS = [
    ((12, 16, 34), (60, 30, 90)),    # deep blue → purple
    ((30, 10, 10), (110, 55, 20)),   # dark red → amber
    ((6, 20, 26), (20, 80, 90)),     # teal night
    ((20, 20, 24), (70, 70, 80)),    # graphite
    ((10, 14, 30), (10, 60, 110)),   # midnight blue
]


def _procedural_slide(index: int, out_path: Path) -> Path:
    from PIL import Image

    top, bot = _GRADIENTS[index % len(_GRADIENTS)]
    ramp = np.linspace(0, 1, H)[:, None]
    img = np.zeros((H, W, 3), dtype=np.float32)
    for c in range(3):
        img[:, :, c] = top[c] * (1 - ramp) + bot[c] * ramp
    # subtle vignette
    yy, xx = np.mgrid[0:H, 0:W]
    d = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    img *= (1 - 0.45 * np.clip(d - 0.2, 0, 1))[:, :, None]
    Image.fromarray(np.clip(img, 0, 255).astype("uint8")).save(out_path, quality=90)
    return out_path


def _ensure_slides(slides: list[Path], work: Path, want: int) -> list[Path]:
    slides = list(slides)
    i = 0
    while len(slides) < want:
        slides.append(_procedural_slide(i, work / f"proc_{i:02d}.jpg"))
        i += 1
    return slides[:want]


# ---------------------------------------------------------------------------
# Ken Burns clips + concat
# ---------------------------------------------------------------------------
def _kenburns_clip(image: Path, seconds: float, index: int, out: Path) -> None:
    # Single looped still + zoompan d=frames + -frames:v frames == exactly one
    # smooth zoom over `frames` output frames (the classic reliable idiom; using
    # -loop with -t makes zoompan re-expand every input frame -> minutes-long clips).
    frames = max(1, int(round(seconds * FPS)))
    zoom_in = index % 2 == 0
    if zoom_in:
        zexpr = "min(zoom+0.0009,1.20)"
    else:
        zexpr = "if(lte(zoom,1.0),1.20,max(1.001,zoom-0.0009))"
    vf = (
        f"scale=2560:1440:force_original_aspect_ratio=increase,"
        f"crop=2560:1440,"
        f"zoompan=z='{zexpr}':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},"
        f"eq=contrast=1.06:saturation=1.12:brightness=-0.02,"
        f"setsar=1,format=yuv420p"
    )
    _run(["ffmpeg", "-y", "-loop", "1", "-i", str(image),
          "-filter_complex", vf, "-frames:v", str(frames), "-r", str(FPS),
          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
          "-pix_fmt", "yuv420p", "-an", str(out)])


def _concat_clips(clips: list[Path], work: Path, out: Path) -> None:
    listfile = work / "clips.txt"
    listfile.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listfile),
          "-c", "copy", str(out)])


# ---------------------------------------------------------------------------
# Captions (ASS)
# ---------------------------------------------------------------------------
def _ts(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _write_ass(cues: list[dict], out: Path) -> Path:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,88,&H00FFFFFF,&H00000000,&H88000000,-1,0,1,5,3,2,140,140,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for c in cues:
        text = c["text"].replace("\n", " ").strip()
        lines.append(f"Dialogue: 0,{_ts(c['start'])},{_ts(c['end'])},Cap,,0,0,0,,"
                     f"{{\\fad(80,80)}}{text}")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Final compose (video + captions + brand + audio mix)
# ---------------------------------------------------------------------------
def compose(concat_video: Path, ass_file: Path, narration: Path, music: Path,
            channel_name: str, out: Path, total: float) -> None:
    font = _font_path()
    brand = channel_name.replace("'", "").replace(":", "")
    ass_esc = str(ass_file).replace(":", r"\:").replace("'", r"\'")
    font_esc = font.replace(":", r"\:")

    filt = (
        f"[0:v]subtitles='{ass_esc}':fontsdir=/usr/share/fonts,"
        f"drawtext=fontfile='{font_esc}':text='{brand}':"
        f"fontcolor=white@0.90:fontsize=46:x=(w-text_w)/2:y=h-96:"
        f"box=1:boxcolor=black@0.40:boxborderw=20[v];"
        f"[2:a]volume=0.26,apad[bed];"
        f"[1:a]volume=1.6,apad,asplit=2[voicekey][voicemix];"
        f"[bed][voicekey]sidechaincompress=threshold=0.03:ratio=9:attack=5:"
        f"release=320:makeup=1[bedduck];"
        f"[voicemix][bedduck]amix=inputs=2:duration=longest:normalize=0[a]"
    )
    _run(["ffmpeg", "-y",
          "-i", str(concat_video), "-i", str(narration), "-i", str(music),
          "-filter_complex", filt, "-map", "[v]", "-map", "[a]",
          "-t", f"{total:.3f}",
          "-c:v", "libx264", "-preset", "medium", "-crf", "19",
          "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
          "-movflags", "+faststart", str(out)])


def build_video(slides: list[Path], cues: list[dict], narration: Path,
                music: Path, channel_name: str, work_dir: str | Path,
                out_path: str | Path, total: float) -> Path:
    """Assemble the full video and return the output path."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    n = max(3, min(len(slides) if slides else 5, 8))
    slides = _ensure_slides(slides, work, n)

    per = total / len(slides)
    clips = []
    for i, s in enumerate(slides):
        clip = work / f"clip_{i:02d}.mp4"
        _kenburns_clip(s, per + 0.05, i, clip)
        clips.append(clip)
    concat_video = work / "concat.mp4"
    _concat_clips(clips, work, concat_video)

    ass = _write_ass(cues, work / "captions.ass")
    out = Path(out_path)
    compose(concat_video, ass, narration, music, channel_name, out, total)
    return out


# ---------------------------------------------------------------------------
# Thumbnail
# ---------------------------------------------------------------------------
def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build_thumbnail(title: str, base_slide: Path | None, channel_name: str,
                    out_path: str | Path) -> Path:
    """Bold high-CTR thumbnail: cinematic image + big punchy title + brand."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    if base_slide and Path(base_slide).exists():
        img = Image.open(base_slide).convert("RGB").resize((1280, 720))
    else:
        proc = _procedural_slide(0, Path(out_path).with_suffix(".base.jpg"))
        img = Image.open(proc).convert("RGB").resize((1280, 720))

    # darken bottom third for text legibility
    overlay = Image.new("RGB", img.size, (0, 0, 0))
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    for y in range(720):
        md.line([(0, y), (1280, y)], fill=int(180 * max(0, (y - 300) / 420)))
    img = Image.composite(overlay, img, mask)

    draw = ImageDraw.Draw(img)
    font_file = _font_path()

    def font(sz):
        try:
            return ImageFont.truetype(font_file, sz)
        except Exception:
            return ImageFont.load_default()

    words = title.upper().split()
    headline = " ".join(words[:3]) if len(words) > 3 else title.upper()
    big = font(150)
    lines = _wrap(draw, headline, big, 1180)
    if len(lines) > 2:  # shrink until it fits two lines
        big = font(110)
        lines = _wrap(draw, headline, big, 1180)

    total_h = sum(big.getbbox(l)[3] - big.getbbox(l)[1] + 16 for l in lines)
    y = 700 - total_h - 70
    for line in lines:
        w = draw.textlength(line, font=big)
        x = (1280 - w) / 2
        # heavy outline
        for dx in range(-5, 6, 2):
            for dy in range(-5, 6, 2):
                draw.text((x + dx, y + dy), line, font=big, fill=(0, 0, 0))
        draw.text((x, y), line, font=big, fill=(255, 214, 10))  # bold yellow
        y += big.getbbox(line)[3] - big.getbbox(line)[1] + 16

    # brand chip
    bf = font(40)
    brand = channel_name.upper()
    bw = draw.textlength(brand, font=bf)
    draw.rectangle([(40, 40), (40 + bw + 40, 40 + 60)], fill=(200, 20, 20))
    draw.text((60, 50), brand, font=bf, fill=(255, 255, 255))

    out = Path(out_path)
    img.save(out, "JPEG", quality=90)
    return out
