# 🔥 Motivación diaria — canal automatizado de superación

Genera y publica **un vídeo de motivación nuevo cada día** en YouTube, de forma
totalmente automática con GitHub Actions. Nicho: **motivación / mentalidad sigma /
superación personal en español** — alto RPM y mucha demanda de búsqueda.

Coste por defecto: **0 €/mes**. Todo original y seguro frente a copyright.

## Cómo funciona (el motor)

Cada ejecución (`python -m src.pipeline`) hace:

1. **Guion** (`src/scripts.py`) — escribe un monólogo motivacional **100% original**
   en español con Cloudflare Workers AI (LLM gratis); si no está disponible usa una
   biblioteca propia escrita a mano. Nada de citas copiadas.
2. **Narración** (`src/tts.py`) — voz neural gratuita de Microsoft Edge
   (`es-ES-AlvaroNeural`). Además da los tiempos de cada palabra para los subtítulos.
3. **Imágenes** (`src/ai_image.py`) — escenas cinematográficas (cumbres, tormentas,
   el amanecer, el esfuerzo) con Cloudflare FLUX. Si falla, fondos de degradado
   generados por código.
4. **Música** (`src/music.py`) — cama épica sintetizada con numpy (pad + sub-pulso),
   original y sin costura, mezclada por debajo de la voz con *ducking* automático.
5. **Vídeo** (`src/video.py`) — slideshow con efecto Ken Burns, **subtítulos grandes
   sincronizados palabra a palabra**, marca del canal y miniatura de alto CTR.
6. **Subida** (`src/upload_youtube.py`) — YouTube Data API v3 con *refresh token*
   OAuth (sin interacción), metadatos SEO en español y añadido a playlist.

## Secrets del repositorio

Obligatorios para subir:

| Secret             | Para qué |
| ------------------ | -------- |
| `YT_CLIENT_ID`     | OAuth client (Google Cloud) del canal de YouTube |
| `YT_CLIENT_SECRET` | idem |
| `YT_REFRESH_TOKEN` | token de refresco del canal (se genera una vez) |

Opcionales (mejoran el resultado, gratis):

| Secret            | Para qué |
| ----------------- | -------- |
| `CF_ACCOUNT_ID`   | Cloudflare Workers AI (imágenes + guiones IA) |
| `CF_API_TOKEN`    | idem, token con permiso *Workers AI* |
| `CHANNEL_NAME`    | nombre del canal en la marca/miniatura (por defecto "Mentalidad Imparable") |
| `VOICE`           | otra voz de edge-tts (p. ej. `es-MX-JorgeNeural`) |
| `AFFILIATE_BLOCK` | bloque de texto para la descripción (enlaces, etc.) |

> El repositorio puede vivir en una cuenta de GitHub distinta a la del canal de
> YouTube: la subida va **al canal del `YT_REFRESH_TOKEN`**, no a la cuenta de GitHub.

## Automatización

- `daily.yml` — 1 vídeo/día a las 06:00 UTC (~08:00 España). Reejecutable a mano
  (*workflow_dispatch*) eligiendo privacidad y duración.
- `ci.yml` — en cada push renderiza un vídeo corto **sin subir** y guarda la
  vista previa como artifact, para comprobar que todo funciona.

Para escalar a más vídeos/día, duplica `daily.yml` con otro `cron` y otro `SLOT`.

## Uso local

```bash
pip install -r requirements.txt   # + ffmpeg
python -m src.pipeline --no-upload --seconds 18 --slides 3
# -> out/video.mp4, out/thumb.jpg
```

(La narración `edge-tts` puede fallar por TLS detrás de un proxy corporativo local;
en GitHub Actions funciona sin problema.)

## Conseguir el refresh token (una vez)

```bash
pip install google-auth-oauthlib
python scripts/get_refresh_token.py /ruta/client_secret.json
```

Inicia sesión con la cuenta **del canal de YouTube** y guarda los tres valores como
secrets del repo.
