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
    """Render a seamless cinematic music bed of ``seconds`` to ``out_path`` (WAV)."""
    rng = np.random.default_rng(seed)
    root = ROOTS[seed % len(ROOTS)]
    n = int(SR * seconds)

    mix = np.zeros(n)
    # sustained chord: root, fifth, octave, plus a high shimmer
    voices = [(root, 0.5, 0.004), (root * 1.5, 0.35, -0.004),
              (root * 2, 0.3, 0.006), (root * 3, 0.12, 0.0)]
    for freq, amp, det in voices:
        v = _pad(freq, seconds, det)
        mix += amp * v

    # slow sub pulse ~ every 2 s to give a heartbeat / drive
    pulse_period = 2.0
    t = np.arange(n) / SR
    pulse_env = 0.5 * (1 + np.sin(2 * np.pi * (1 / pulse_period) * t - np.pi / 2))
    sub = np.sin(2 * np.pi * root * 0.5 * t) * (pulse_env ** 3) * 0.35
    mix += sub

    # gentle overall swell (fade in / out) so it loops and breathes
    mix *= _adsr(n, attack=2.0, release=3.0)

    # soft saturation + normalize
    mix = np.tanh(mix * 0.8)
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = (mix / peak) * 0.9

    out = Path(out_path)
    data = (mix * 32767).astype("<i2")
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data.tobytes())
    return out
