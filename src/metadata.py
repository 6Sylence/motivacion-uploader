"""YouTube metadata for the Spanish motivation / self-improvement channel.

Spanish-first (the audience is hispanohablante), reproducible per (theme, date),
with rotating headline hooks so a repeated theme never publishes an identical
title. Built for the "motivación / sigma / superación personal" niche, which has
strong RPM and high search demand.
"""

from __future__ import annotations

import datetime as _dt
import os

CHANNEL_NAME = os.environ.get("CHANNEL_NAME", "").strip() or "MENTE SIGMA"

# Headline hooks prepended/appended to the theme title for variety + SEO.
HOOKS = [
    "ESCÚCHALO CADA MAÑANA",
    "EL VIDEO QUE NECESITAS HOY",
    "DEJA DE PERDER EL TIEMPO",
    "MENTALIDAD DE ACERO",
    "ACTIVA TU MODO SIGMA",
    "ANTES DE RENDIRTE, MIRA ESTO",
    "1 MINUTO QUE CAMBIA TU DÍA",
    "PARA LOS QUE NO SE RINDEN",
]

TAGS = [
    "motivacion", "motivacion personal", "superacion personal", "desarrollo personal",
    "disciplina", "mentalidad", "mentalidad ganadora", "mentalidad sigma",
    "sigma", "sigma rule", "reglas sigma", "motivacion en español",
    "video motivacional", "discurso motivacional", "frases motivadoras",
    "motivacion diaria", "levantate y lucha", "no te rindas", "constancia",
    "habitos", "exito", "productividad", "motivacion gym", "motivacion 2026",
    "crecimiento personal", "inteligencia emocional", "estoicismo", "enfoque",
]

# Localized description lines (Spanish core + a few big markets for extra reach).
LOCALES = {
    "es": "Motivación diaria para tu disciplina, tu mentalidad y tu superación personal. Un vídeo nuevo cada día para que no aflojes. Suscríbete y actívate. 🔥",
    "pt": "Motivação diária para a sua disciplina, mentalidade e superação pessoal. Um vídeo novo todos os dias. Inscreva-se e ative-se. 🔥",
    "en": "Daily motivation for your discipline, mindset and self-improvement. A new video every day. Subscribe and lock in. 🔥",
}


def _localizations(title: str) -> dict:
    return {lang: {"title": title, "description": d} for lang, d in LOCALES.items()}


def _hashtags() -> str:
    return "#motivacion #disciplina #mentalidad #superacion #sigma"


def build_metadata(title_theme: str, keyword: str, body: str, seed: int,
                   date: _dt.date | None = None, tag_marker: str | None = None) -> dict:
    """Return the YouTube metadata dict for one motivational video."""
    date = date or _dt.date.today()
    hook = HOOKS[seed % len(HOOKS)]
    # e.g. "DISCIPLINA — ESCÚCHALO CADA MAÑANA | Motivación"
    title = f"{title_theme.upper()} — {hook} | Motivación"
    title = title[:98]

    tags = list(TAGS)
    # theme keyword variants up front for relevance
    for extra in (keyword, f"{keyword} motivacion", f"motivacion {keyword}"):
        if extra.lower() not in [t.lower() for t in tags]:
            tags.insert(0, extra)
    if tag_marker:
        tags.append(tag_marker)
    # keep tags under YouTube's ~500-char budget
    budget, kept = 460, []
    for t in tags:
        if sum(len(x) + 1 for x in kept) + len(t) + 1 <= budget:
            kept.append(t)
    tags = kept

    desc_lines = [
        f"{title_theme}. {HOOKS[(seed + 1) % len(HOOKS)].capitalize()}.",
        "",
        LOCALES["es"],
        "",
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬",
        "🔔 Suscríbete para no perderte la motivación de cada día.",
        "👍 Dale like si esto te ha activado.",
        "💬 Escribe en comentarios tu objetivo de hoy.",
        "",
        "Contenido 100% original. Narración y música creadas para este canal.",
        "",
        _hashtags(),
    ]
    affiliate = os.environ.get("AFFILIATE_BLOCK", "").strip()
    if affiliate:
        desc_lines.insert(4, affiliate)
        desc_lines.insert(5, "")

    return {
        "title": title,
        "description": "\n".join(desc_lines),
        "tags": tags,
        "categoryId": "22",  # People & Blogs — standard for motivation channels
        "privacyStatus": os.environ.get("PRIVACY", "public"),
        "localizations": _localizations(title),
        "playlist": "Motivación diaria 🔥",
    }
