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

# Dark, gritty, high-intensity "sigma / modo lobo" scenes — the aesthetic of
# viral motivation edits (modolobo, modocueva): lone wolves, lions, stoic marble
# statues, storms, fire, solitary warriors. Rotated (offset by seed) so slides
# vary and consecutive uploads differ. All unbranded, text-free, 16:9, safe.
SCENES = [
    "a massive lone black wolf staring straight at the camera in dark misty forest, "
    "piercing eyes, moonlight rimlight, breath fog, menacing and majestic",
    "a powerful male lion in profile emerging from deep shadow, single hard "
    "light on the mane, black background, intense and regal",
    "a weathered ancient Greek marble statue of a stoic philosopher, dramatic "
    "chiaroscuro side light, deep black background, cracked stone, timeless",
    "a lone hooded man walking away through torrential rain on an empty dark city "
    "street at night, wet reflections, single street lamp, cinematic and somber",
    "a shirtless boxer alone in a pitch-black gym under one harsh overhead light, "
    "sweat and steam, chalk dust, gritty determination, heavy shadows",
    "a solitary warrior silhouette on a cliff against a violent lightning storm, "
    "wind and rain, epic dramatic sky, tiny against the chaos",
    "close-up of glowing embers and fire sparks rising in total darkness, intense "
    "orange glow, cinematic and moody",
    "a lone wolf on a snowy ridge under a cold stormy sky, desaturated blue tones, "
    "solitary and unbreakable",
    "a man doing pushups alone in a dark concrete room, one shaft of hard light "
    "through a window, dust in the air, raw and gritty",
    "an eagle diving through storm clouds over black jagged mountains, dramatic "
    "and powerful, high contrast",
    "a lone figure climbing a steep dark mountain in fog at dawn, exhausted but "
    "relentless, moody desaturated cinematic grade",
    "a clenched fist raised against a dark dramatic sky with a single beam of "
    "light breaking through storm clouds, triumphant and intense",
]

_COMMON = ("Dark moody cinematic still, very high contrast, deep crushed blacks, "
           "dramatic single-source lighting, desaturated with a subtle warm or "
           "teal accent, fine film grain, gritty and epic, powerful sigma "
           "motivation aesthetic, photorealistic, no text, no watermark, "
           "no logos, unbranded, 16:9 wide cinematic composition.")


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
