"""Motivational scripts (Spanish).

Each upload gets a short, punchy monologue about discipline, mindset, focus and
self-improvement. We try to WRITE A FRESH one with Cloudflare Workers AI (free
text model) so no two videos repeat; if that's unavailable we fall back to an
original hand-written library. Everything is 100% original (no copied quotes),
clean and monetization-safe.
"""

from __future__ import annotations

import json
import os
import urllib.request

# Rotating themes -> the LLM writes an original monologue on one of these.
THEMES = [
    ("Disciplina", "disciplina"),
    ("Deja de rendirte", "no rendirse"),
    ("La mentalidad lo es todo", "mentalidad"),
    ("Levántate temprano", "madrugar y rutina"),
    ("El silencio y el trabajo", "trabajar en silencio"),
    ("Domina tu mente", "control mental"),
    ("Nadie vendrá a salvarte", "responsabilidad personal"),
    ("Consistencia sobre motivación", "constancia"),
    ("Convierte el dolor en fuerza", "resiliencia"),
    ("El enfoque es tu superpoder", "enfoque y concentración"),
]

MODEL = "@cf/meta/llama-3.1-8b-instruct"
CF_URL = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"

_SYSTEM = (
    "Eres un guionista de vídeos de motivación en español. Escribes monólogos "
    "originales, potentes y directos, en segunda persona (tú), sobre disciplina, "
    "mentalidad y superación. Tono firme e inspirador, frases cortas. Prohibido "
    "copiar citas de nadie, prohibido tacos, prohibido lenguaje ofensivo. Solo el "
    "texto del monólogo, sin títulos ni comillas ni emojis."
)


def _cf_generate(theme: str) -> str | None:
    acct = os.environ.get("CF_ACCOUNT_ID", "").strip()
    token = os.environ.get("CF_API_TOKEN", "").strip()
    if not acct or not token:
        return None
    prompt = (f"Escribe un monólogo motivacional 100% original en español sobre: "
              f"{theme}. Entre 160 y 220 palabras. En segunda persona (tú), frases "
              f"cortas y contundentes, con un cierre que empuje a la acción.")
    body = json.dumps({
        "messages": [{"role": "system", "content": _SYSTEM},
                     {"role": "user", "content": prompt}],
        "max_tokens": 600,
    }).encode()
    req = urllib.request.Request(
        CF_URL.format(acct=acct, model=MODEL), data=body, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        txt = (data.get("result") or {}).get("response", "").strip()
        # sanity: must look like real prose, not an error / refusal
        if txt and len(txt) > 220 and " " in txt:
            return txt
    except Exception as exc:
        print(f"    [script] CF text generation failed ({exc}); using the library")
    return None


# Original fallback library (hand-written, clean). One per theme index.
_LIBRARY = [
    "La disciplina no es un castigo, es libertad. Es hacer lo que debes cuando "
    "no te apetece, y hacerlo igual. La motivación te enciende un día; la "
    "disciplina te sostiene los otros trescientos sesenta y cuatro. No esperes a "
    "tener ganas. Las ganas llegan después, cuando ya has empezado. Cada vez que "
    "cumples una promesa que te hiciste, te vuelves más fuerte. Cada vez que la "
    "rompes, te vuelves más débil. Elige. Empieza hoy, aunque sea pequeño. Hazlo.",
    "Rendirte es fácil. Por eso casi todos lo hacen. Pero tú no eres casi todos. "
    "El momento en el que quieres abandonar suele ser justo el momento antes del "
    "cambio. Un paso más. Solo uno. Y luego otro. No necesitas ser el más rápido, "
    "necesitas ser el que no se detiene. Respira, aprieta los dientes y sigue. Lo "
    "que hoy te parece imposible, mañana será tu punto de partida.",
    "Tu mente es el campo de batalla. Ganas ahí o no ganas en ningún sitio. Los "
    "pensamientos que alimentas se convierten en tus acciones, y tus acciones en "
    "tu vida. Deja de repetirte que no puedes. Empieza a preguntarte cómo sí. "
    "Controla tu mente y controlarás tu destino. Nadie decide por ti lo que "
    "piensas. Ese poder es tuyo. Úsalo.",
    "Mientras el mundo duerme, tú puedes construir tu ventaja. Levantarte "
    "temprano no te hace mejor persona, te da algo que casi nadie tiene: tiempo "
    "y silencio para trabajar en ti. Una hora al amanecer vale por tres al "
    "mediodía. Gana la mañana y ganarás el día. Gana el día suficientes veces y "
    "ganarás tu vida.",
    "No hables de tus planes. Constrúyelos. El ruido no cambia nada; el trabajo "
    "sí. Trabaja en silencio y deja que los resultados hagan el escándalo. La "
    "gente respeta lo que ve, no lo que prometes. Baja la cabeza, haz el trabajo, "
    "y un día levantarás la vista y estarás muy lejos de donde empezaste.",
    "El dolor que sientes hoy será la fuerza que sientas mañana. No huyas de la "
    "dificultad: es ahí donde te construyes. Nadie fuerte nació cómodo. Cada "
    "obstáculo es un entrenamiento disfrazado. Aguanta, aprende, avanza. Lo que "
    "no te rompe te está afilando.",
    "Nadie vendrá a salvarte. Y esa es la mejor noticia que vas a escuchar, "
    "porque significa que todo depende de ti. Deja de esperar el momento "
    "perfecto, el permiso, la suerte. Toma la responsabilidad completa de tu "
    "vida. En el instante en que dejas de culpar y empiezas a actuar, todo "
    "cambia. El poder siempre fue tuyo.",
    "La constancia vence al talento cuando el talento no es constante. No "
    "necesitas un día heroico; necesitas mil días normales bien hechos. Pequeño, "
    "repetido, imparable. Lo que haces todos los días importa mil veces más que "
    "lo que haces de vez en cuando. Aparece. Otra vez. Y otra. Ahí está el "
    "secreto que nadie quiere oír.",
    "El enfoque es tu superpoder en un mundo lleno de distracciones. Quien "
    "controla su atención controla su vida. Apaga el ruido, elige una cosa y "
    "entrégate por completo. La energía dispersa no mueve nada; concentrada, lo "
    "atraviesa todo. Menos pantallas, más propósito. Enfócate y serás imparable.",
    "Cada mañana eliges: la versión que se queja o la versión que actúa. Nadie "
    "te debe nada. El mundo responde al que se mueve. Deja de esperar a estar "
    "listo, porque nunca lo estarás del todo. Empieza asustado si hace falta, "
    "pero empieza. La acción imperfecta siempre gana a la perfección que nunca "
    "llega.",
]


def build_script(seed: int = 0):
    """Return (title, keyword, body). Fresh via CF if possible, else library."""
    title, theme = THEMES[seed % len(THEMES)]
    body = _cf_generate(theme) or _LIBRARY[seed % len(_LIBRARY)]
    return title, theme, body
