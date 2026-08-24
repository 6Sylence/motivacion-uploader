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


def narrate(text: str, out_dir: str | Path, rate: str = "-4%",
            pitch: str = "-2Hz") -> tuple[Path, list[dict], float]:
    """Render ``text`` to ``out_dir/narration.mp3``.

    Returns ``(mp3_path, words, duration_seconds)`` where ``words`` is a list of
    ``{"text", "start", "end"}`` timings for caption sync. A slightly slower rate
    and lower pitch make the delivery weightier.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3 = out_dir / "narration.mp3"
    words = asyncio.run(_synthesize(text, mp3, _voice(), rate, pitch))
    duration = words[-1]["end"] if words else 0.0
    if mp3.stat().st_size < 1024:
        raise RuntimeError("edge-tts produced an empty narration file")
    return mp3, words, duration


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
