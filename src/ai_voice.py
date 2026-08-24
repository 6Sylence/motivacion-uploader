"""Premium emotional narration via the ElevenLabs Text-to-Speech API.

This is the voice that actually sounds motivating (the modolobo / modocueva
tone) — dramatic, expressive, human. edge-tts stays as the free fallback.

Enable it by setting these repo secrets:
  ELEVENLABS_API_KEY   your ElevenLabs API key
  ELEVEN_VOICE_ID      (preferred) the exact voice id to use, OR
  ELEVEN_VOICE_NAME    a voice name to look up (e.g. a Spanish dramatic voice,
                       or your cloned voice "Álvaro Romero Miñano")

Optional tuning (0..1): ELEVEN_STABILITY, ELEVEN_STYLE, ELEVEN_SIMILARITY.

Everything is best-effort: if the key/voice/API is unavailable the pipeline
falls back to edge-tts, so an upload never breaks over the voice.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

VOICES_URL = "https://api.elevenlabs.io/v1/voices"
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
TTS_MODEL = "eleven_multilingual_v2"   # handles Spanish + cloned voices


class AIVoiceError(RuntimeError):
    pass


def available() -> bool:
    """True only if a key AND a voice (id or name) are configured."""
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice = (os.environ.get("ELEVEN_VOICE_ID", "").strip()
             or os.environ.get("ELEVEN_VOICE_NAME", "").strip())
    return bool(key and voice)


def resolve_voice_id(name: str) -> str | None:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key or not name:
        return None
    try:
        req = urllib.request.Request(
            VOICES_URL, headers={"xi-api-key": key, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None
    want = name.strip().lower()
    voices = data.get("voices", []) if isinstance(data, dict) else []
    for v in voices:
        if str(v.get("name", "")).strip().lower() == want:
            return v.get("voice_id")
    for v in voices:
        if want in str(v.get("name", "")).strip().lower():
            return v.get("voice_id")
    return None


def _voice_id() -> str | None:
    vid = os.environ.get("ELEVEN_VOICE_ID", "").strip()
    if vid:
        return vid
    name = os.environ.get("ELEVEN_VOICE_NAME", "").strip()
    return resolve_voice_id(name) if name else None


def _f(env: str, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(os.environ.get(env, "").strip())))
    except (ValueError, TypeError):
        return default


def _tts(text: str, voice_id: str, out_path: Path, timeout: int = 180) -> Path:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    url = TTS_URL.format(voice_id=voice_id) + "?output_format=mp3_44100_128"
    body = json.dumps({
        "text": text,
        "model_id": TTS_MODEL,
        # lower stability + some style = more emotional, dramatic delivery
        "voice_settings": {
            "stability": _f("ELEVEN_STABILITY", 0.40),
            "similarity_boost": _f("ELEVEN_SIMILARITY", 0.80),
            "style": _f("ELEVEN_STYLE", 0.45),
            "use_speaker_boost": True,
        },
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            data = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise AIVoiceError(f"ElevenLabs TTS HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise AIVoiceError(f"ElevenLabs TTS request failed: {exc}") from exc
    if "json" in ctype:
        raise AIVoiceError("TTS returned JSON, not audio: "
                           + data.decode("utf-8", "replace")[:300])
    if not data or len(data) < 1500:
        raise AIVoiceError(f"TTS returned {len(data)} bytes (not audio)")
    out_path.write_bytes(data)
    return out_path


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def narrate(text: str, out_dir: str | Path) -> tuple[Path, list[dict], float]:
    """Drop-in replacement for tts.narrate using ElevenLabs. Returns
    ``(mp3_path, [], duration)`` — no word timings (captions fall back to the
    even-timed text splitter). Raises AIVoiceError if unavailable/failed."""
    if not available():
        raise AIVoiceError("ElevenLabs not configured")
    vid = _voice_id()
    if not vid:
        raise AIVoiceError("no ElevenLabs voice resolved (check ELEVEN_VOICE_ID/NAME)")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3 = out_dir / "narration.mp3"
    _tts(text, vid, mp3)
    dur = _probe_duration(mp3)
    if dur <= 0:
        raise AIVoiceError("could not determine narration duration")
    print("    [voice] ElevenLabs narration ready")
    return mp3, [], dur
