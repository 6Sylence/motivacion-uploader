"""Procedural cinematic underscore — 100% original, synthesized with numpy.

A slow, epic pad (root + fifth + octave) with a gentle sub-pulse and a soft
riser swell. It sits UNDER the narration (mixed low), giving videos an emotional,
"motivational speech over music" feel without any sampled/copyrighted track.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 44100

# Minor-key roots (Hz) for an epic, serious mood. One is picked per video by seed.
ROOTS = [55.00, 58.27, 61.74, 65.41, 49.00]  # A1, A#1, B1, C2, G1


def _adsr(n: int, attack: float, release: float) -> np.ndarray:
    env = np.ones(n)
    a = int(SR * attack)
    r = int(SR * release)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] = np.linspace(1, 0, r)
    return env


def _pad(freq: float, seconds: float, detune: float = 0.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    # a few slightly detuned saw-ish partials for a warm analog pad
    sig = np.zeros_like(t)
    for k, amp in ((1, 0.6), (2, 0.25), (3, 0.12), (4, 0.06)):
        f = freq * k * (1 + detune)
        sig += amp * np.sin(2 * np.pi * f * t)
    # slow tremolo for movement
    sig *= 1.0 + 0.08 * np.sin(2 * np.pi * 0.15 * t)
    return sig


def build_bed(seconds: float, out_path: str | Path, seed: int = 0) -> Path:
    """Render a seamless DARK, DRIVING cinematic bed of ``seconds`` to WAV.

    Deep minor drone + a pumping heartbeat/kick pulse + a rhythmic gate that
    makes the whole bed drive, plus a slow rising tension sweep. Epic and
    intense (modo-lobo / sigma edit vibe), not ambient."""
    root = ROOTS[seed % len(ROOTS)]
    n = int(SR * seconds)
    t = np.arange(n) / SR

    mix = np.zeros(n)
    # dark sustained chord: root, octave, fifth, plus body
    voices = [(root, 0.5, 0.004), (root * 2, 0.30, -0.004),
              (root * 3, 0.18, 0.006), (root * 1.5, 0.22, 0.0)]
    for freq, amp, det in voices:
        mix += amp * _pad(freq, seconds, det)

    # driving heartbeat/kick pulse (~88 BPM), phase-locked so it loops
    bpm = 88.0
    beat = 60.0 / bpm
    pulse = 0.5 * (1 + np.sin(2 * np.pi * (1 / beat) * t - np.pi / 2))
    sub = np.sin(2 * np.pi * root * 0.5 * t) * (pulse ** 4) * 0.5   # deep kick
    tick = np.sin(2 * np.pi * root * t) * (pulse ** 8) * 0.12        # attack tick
    mix += sub + tick

    # rhythmic gate: the whole bed pumps to the beat (sidechain-style drive)
    mix *= 0.60 + 0.40 * (pulse ** 2)

    # slow rising tension building across the track
    mix += np.sin(2 * np.pi * root * 3 * t) * 0.05 * np.clip(t / max(seconds, 1), 0, 1)

    # overall swell so it breathes and loops cleanly
    mix *= _adsr(n, attack=1.6, release=2.6)

    # drive into soft saturation + normalize
    mix = np.tanh(mix * 1.0)
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.92

    out = Path(out_path)
    data = (mix * 32767).astype("<i2")
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data.tobytes())
    return out
