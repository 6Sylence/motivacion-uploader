"""Narration via Microsoft Edge neural TTS (edge-tts) — free, no API key.

We use a Spanish male neural voice (``es-ES-AlvaroNeural`` by default) to read the
motivational monologue. edge-tts also emits *WordBoundary* events, which give us
the exact start time of every spoken word — we use those to burn word-synced
captions later, no speech-recognition needed.

Runs cleanly inside GitHub Actions. (Locally it may fail TLS through a corporate
MITM proxy; that's an environment quirk, not a code bug.)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path

# A calm-but-firm Spanish male voice fits the "sigma / superación" tone. Override
# with the VOICE env var (any edge-tts voice, e.g. es-MX-JorgeNeural).
DEFAULT_VOICE = "es-ES-AlvaroNeural"


def _voice() -> str:
    return os.environ.get("VOICE", "").strip() or DEFAULT_VOICE


async def _synthesize(text: str, out_path: Path, voice: str,
                      rate: str, pitch: str):
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    words: list[dict] = []
    with open(out_path, "wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offsets/durations come in 100-nanosecond ticks.
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                })
    return words


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def narrate(text: str, out_dir: str | Path, rate: str = "-7%",
            pitch: str = "-9Hz") -> tuple[Path, list[dict], float]:
    """Render ``text`` to ``out_dir/narration.mp3``.

    Returns ``(mp3_path, words, duration_seconds)`` where ``words`` is a list of
    ``{"text", "start", "end"}`` timings for caption sync (may be empty if the
    voice backend didn't emit word boundaries — the caller then falls back to
    even-timed captions). The duration is always the *actual* audio length
    (probed with ffprobe), never derived from word events, so a full-length
    narration is never truncated.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3 = out_dir / "narration.mp3"
    words = asyncio.run(_synthesize(text, mp3, _voice(), rate, pitch))
    if not mp3.exists() or mp3.stat().st_size < 1024:
        raise RuntimeError("edge-tts produced an empty narration file")
    duration = _probe_duration(mp3)
    if duration <= 0 and words:
        duration = words[-1]["end"]
    if duration <= 0:
        raise RuntimeError("could not determine narration duration")
    return mp3, words, duration


def _chunk_words(tokens: list[str], max_chars: int) -> list[str]:
    """Group raw word tokens into short caption lines (breaking on punctuation)."""
    lines: list[str] = []
    cur: list[str] = []
    for tok in tokens:
        tentative = " ".join(cur + [tok])
        if cur and (len(tentative) > max_chars
                    or cur[-1].endswith((".", "!", "?", ":", ";", ","))):
            lines.append(" ".join(cur))
            cur = []
        cur.append(tok)
    if cur:
        lines.append(" ".join(cur))
    return lines


def captions_from_text(text: str, duration: float,
                       max_chars: int = 24) -> list[dict]:
    """Build evenly-timed caption cues from the script text when the voice
    backend gives no word timings. Each cue's slice is proportional to its
    character length, so longer lines stay on screen longer — a clean, reliable
    approximation of word-synced captions."""
    tokens = text.split()
    lines = _chunk_words(tokens, max_chars)
    if not lines:
        return []
    weights = [max(1, len(l)) for l in lines]
    total_w = sum(weights)
    cues: list[dict] = []
    t = 0.0
    for line, w in zip(lines, weights):
        span = duration * (w / total_w)
        cues.append({"text": line.strip().upper(),
                     "start": round(t, 3),
                     "end": round(t + max(span - 0.04, 0.4), 3)})
        t += span
    return cues


def group_captions(words: list[dict], max_chars: int = 24) -> list[dict]:
    """Group word timings into short caption cues (2-4 words each) suitable for
    big centered burned-in subtitles. Returns ``{"text", "start", "end"}`` cues."""
    cues: list[dict] = []
    cur: list[dict] = []

    def flush():
        if cur:
            cues.append({
                "text": " ".join(w["text"] for w in cur).strip().upper(),
                "start": cur[0]["start"],
                "end": cur[-1]["end"],
            })

    for w in words:
        tentative = " ".join(x["text"] for x in cur + [w])
        # break on sentence punctuation or when the line gets long
        if cur and (len(tentative) > max_chars
                    or cur[-1]["text"].endswith((".", "!", "?", ":", ";", ","))):
            flush()
            cur = []
        cur.append(w)
    flush()
    return cues
