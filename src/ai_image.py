"""Cinematic motivational images via Cloudflare Workers AI (FLUX-1-schnell).

Each video is a slideshow of several AI-generated cinematic scenes (lone figures
at dawn, mountain summits, storms, the grind) plus a striking title thumbnail.
Cloudflare Workers AI has a generous free tier and a plain HTTP API, so it runs
inside the daily GitHub Actions pipeline.

Repo secrets:
  CF_ACCOUNT_ID   Cloudflare account id
  CF_API_TOKEN    API token with the "Workers AI" permission

Best-effort: if the secrets are missing or the API errors, the pipeline falls
back to procedurally drawn gradient backgrounds, so an upload never breaks over
the image step.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "@cf/black-forest-labs/flux-1-schnell"
API_URL = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"

# Interchangeable cinematic scenes. We rotate through them (offset by seed) so a
# video's slides are varied and consecutive uploads differ. All are unbranded,
# text-free, wide 16:9, monetization-safe.
SCENES = [
    "a lone silhouetted man standing on a mountain summit at sunrise, arms ready, "
    "vast valley of clouds below, god rays",
    "a determined athlete running up endless stadium stairs at dawn, dramatic "
    "backlight, sweat and steam, low angle",
    "a solitary figure walking a foggy road toward a bright horizon, long shadows, "
    "cinematic teal and orange",
    "a boxer wrapping his hands alone in a dark gym, single hard light beam, dust "
    "in the air, moody and intense",
    "a climber gripping a cliff edge high above the clouds at golden hour, "
    "epic scale, vertigo",
    "a person meditating on a rock before a stormy ocean, waves crashing, powerful "
    "and calm, dramatic sky",
    "a runner's silhouette against a huge rising sun on an empty desert highway, "
    "heat haze, vast and lonely",
    "a lone wolf on a snowy ridge under the northern lights, cold blue tones, "
    "majestic and solitary",
    "an eagle soaring over jagged mountain peaks at sunrise, sense of freedom and "
    "power, cinematic wide shot",
    "a man doing pushups alone in an empty warehouse at night, single overhead "
    "light, gritty determination",
    "a candlelit desk with an open notebook and coffee before dawn, warm focused "
    "glow, quiet discipline",
    "a hiker reaching a peak and raising a fist against a dramatic cloudy sunset, "
    "triumphant silhouette",
]

_COMMON = ("Ultra high detail, cinematic dramatic lighting, bold high contrast, "
           "photorealistic, epic and inspiring, no text, no watermark, no logos, "
           "unbranded, 16:9 wide cinematic composition.")


class AIImageError(RuntimeError):
    pass


def available() -> bool:
    return bool(os.environ.get("CF_ACCOUNT_ID", "").strip()
                and os.environ.get("CF_API_TOKEN", "").strip())


def scene_prompt(index: int) -> str:
    return f"{SCENES[index % len(SCENES)]}. {_COMMON}"


def generate(prompt: str, out_path: str | Path, steps: int = 6,
             timeout: int = 120) -> Path:
    """Generate one image → ``out_path`` (JPEG). Raises AIImageError on failure."""
    acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
    token = os.environ.get("CF_API_TOKEN", "").strip()
    if not acct or not token:
        raise AIImageError("CF_ACCOUNT_ID / CF_API_TOKEN not set")
    url = API_URL.format(acct=acct, model=MODEL)
    body = json.dumps({"prompt": prompt,
                       "steps": int(max(1, min(steps, 8)))}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise AIImageError(f"Cloudflare AI HTTP {exc.code}: {detail}") from exc
    except Exception as exc:
        raise AIImageError(f"Cloudflare AI request failed: {exc}") from exc

    if not payload.get("success", True):
        raise AIImageError(f"Cloudflare AI error: {str(payload.get('errors'))[:300]}")
    b64 = (payload.get("result") or {}).get("image")
    if not b64:
        raise AIImageError(f"no image in response: {json.dumps(payload)[:300]}")
    try:
        data = base64.b64decode(b64)
    except Exception as exc:
        raise AIImageError(f"bad base64 image: {exc}") from exc
    if len(data) < 2000:
        raise AIImageError(f"image too small ({len(data)} bytes)")
    out = Path(out_path)
    out.write_bytes(data)
    return out


def generate_slideshow(out_dir: str | Path, seed: int = 0,
                       count: int = 5) -> list[Path]:
    """Generate ``count`` cinematic slides, or ``[]`` if AI images are unavailable
    (caller falls back to procedural gradients). Partial success is fine — we
    return whatever slides rendered."""
    if not available():
        return []
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slides: list[Path] = []
    for i in range(count):
        dest = out_dir / f"slide_{i:02d}.jpg"
        try:
            generate(scene_prompt(seed + i), dest)
            slides.append(dest)
            print(f"    [img] slide {i + 1}/{count} ready (Cloudflare FLUX)")
        except AIImageError as exc:
            print(f"    [img] slide {i + 1} failed ({exc}); skipping")
    return slides
