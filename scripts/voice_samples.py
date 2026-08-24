#!/usr/bin/env python3
"""Render short spoken samples of several Spanish male voices (edge-tts) with the
channel's cinematic voice processing applied, so we can pick the most motivating
one. Writes out/samples/NN_<voice>.mp3. Best-effort per voice."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

LINE = ("Levántate. El mundo no espera a nadie. "
        "Hoy no hay excusas, solo disciplina. "
        "Demuéstrate de lo que estás hecho.")

# Deeper / more dramatic Spanish male candidates across accents.
VOICES = [
    "es-ES-AlvaroNeural",   # España (actual)
    "es-MX-JorgeNeural",    # México (grave, cálida)
    "es-US-AlonsoNeural",   # EE.UU. neutro
    "es-AR-TomasNeural",    # Argentina
    "es-CO-GonzaloNeural",  # Colombia
]

RATE = "-7%"
PITCH = "-9Hz"

# Same cinematic chain used in the video mix (compression + low-end + short echo).
AF = ("acompressor=threshold=-18dB:ratio=4:attack=6:release=140,"
      "equalizer=f=110:t=q:w=1.2:g=4,equalizer=f=320:t=q:w=1.5:g=-2,"
      "volume=1.35,aecho=0.85:0.9:55:0.22")


async def _render(voice: str, raw: Path) -> bool:
    import edge_tts
    comm = edge_tts.Communicate(LINE, voice, rate=RATE, pitch=PITCH)
    with open(raw, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
    return raw.exists() and raw.stat().st_size > 1024


def main() -> int:
    out = Path("out/samples")
    out.mkdir(parents=True, exist_ok=True)
    ok = []
    for i, voice in enumerate(VOICES):
        raw = out / f"_{voice}.raw.mp3"
        final = out / f"{i+1:02d}_{voice}.mp3"
        try:
            if not asyncio.run(_render(voice, raw)):
                print(f"  [skip] {voice}: empty")
                continue
            subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-af", AF,
                            "-b:a", "192k", str(final)], check=True,
                           capture_output=True)
            raw.unlink(missing_ok=True)
            ok.append(final.name)
            print(f"  [ok] {final.name}")
        except Exception as exc:
            print(f"  [skip] {voice}: {exc}")
    print(f"Rendered {len(ok)} samples: {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
