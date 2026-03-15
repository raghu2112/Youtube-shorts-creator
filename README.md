# AI Viral Shorts Studio

Generates professional **YouTube Shorts (9:16)** and **YouTube videos (16:9)** from a single topic sentence. Uses free AI APIs, free TTS, and FFmpeg. No credit card required to get started.

---

## What It Does

1. You enter a topic and pick a style
2. Gemini or Groq writes a viral script (falls back to a local template if no keys)
3. gTTS narrates the script in your chosen voice and language
4. Pexels provides cinematic B-roll clips matched to each segment
5. FFmpeg assembles everything — Ken Burns motion, captions, music, hard cuts — in ~30–90 seconds
6. You download the finished MP4

---

## AI Script Providers

Both are **free** with no credit card required.

| Provider | Model | Free Tier | Get Key |
|---|---|---|---|
| **Gemini** ← recommended | `gemini-1.5-flash` | 1 500 req/day · 15 RPM | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) |
| **Groq** (fallback) | `llama-3.3-70b-versatile` | 14 400 req/day · 500 RPM | [console.groq.com](https://console.groq.com) |

Priority order: **Gemini → Groq → local template**. The app always produces a video even with no AI keys configured.

---

## Quick Start

```bash
# 1. Clone / download the project
# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install FFmpeg  (required for all video processing)
#    Windows : https://ffmpeg.org/download.html  — add to PATH
#    macOS   : brew install ffmpeg
#    Linux   : sudo apt install ffmpeg

# 4. Configure API keys
Edit .env — at minimum add GEMINI_API_KEY for free AI scripts

# 5. Run
python main.py
# Browser opens automatically at http://127.0.0.1:8000
```

---

## .env Configuration

```env
# AI Script Generation (both free, no credit card)
GEMINI_API_KEY=AIza...      # aistudio.google.com/app/apikey
GROQ_API_KEY=gsk_...        # console.groq.com → API Keys

# Pexels video backgrounds (free)
PEXELS_API_KEY=...          # pexels.com/api
```

**All keys are optional.** Graceful degradation:

| Missing key | Fallback |
|---|---|
| No Gemini + No Groq | Local template scripts (still good quality) |
| No Pexels | Animated gradient backgrounds |

---

## Features

### Video Formats
- **YouTube Shorts** — 1080×1920, 9:16 vertical
- **YouTube Video** — 1920×1080, 16:9 landscape

### Video Styles (6)
| Style | Description |
|---|---|
| 🔥 Viral Listicle | Hook → numbered list → CTA, hard cuts, ~4s clips |
| ✨ Lifestyle | Mindset / self-improvement, motivational tone |
| 🎓 Educational | Explainer / TED-Ed style, clear and factual |
| 🌍 Documentary | Cinematic / Netflix style, investigative tone |
| ⚡ Motivational | High-energy, drives immediate action |
| 📺 News | Broadcast journalism style, authoritative |

### Caption Styles (8)

Each style has a **live inline preview** showing exactly how it renders — font, colour, outline, and box — before you generate the video.

| Style | Look |
|---|---|
| 🔥 Viral | Anton font · white · thick black outline · no box |
| Standard | Inter Bold · white · thin outline |
| Bold | Oswald 700 · white · heavy outline · extra contrast |
| ✦ Highlighted | Inter 800 · yellow `#ffe44d` · dark shadow |
| ▬ Box | White text on semi-transparent dark pill |
| ▶ Shorts | Oswald on dark background box · TikTok style |
| ◈ Cinematic | Inter Light italic · lavender · soft glow |
| 💥 MrBeast | Anton XL · yellow `#ffe600` · warm glow · word-by-word |

### Caption Positions (7)

A **mini phone diagram** in each card shows where captions appear on screen. Selecting a position immediately moves the caption bar in the live preview.

| Position | Placement |
|---|---|
| ⬇ Bottom | Above platform UI chrome (safe zone) |
| ⬆ Top | Header area |
| ⏺ Center | Vertical center — cinematic emphasis |
| 🔥 Viral Center | Bold bottom-center, auto-selected for Viral/Lifestyle |
| ▭ Lower Third | 75% down — news / documentary band |
| ▭ Upper Third | 25% from top — header band |
| ✎ Custom | Manual pixel X / Y coordinates |

Auto-switching: selecting a Viral or Lifestyle video style auto-selects **Viral Center**; all other styles default to **Bottom**.

### Voice Narration
- **23 voices** across 14 languages
- Voice groups: 🇺🇸 English, 🌍 European, 🌏 Asian
- Speed control: 0.75× · 1.0× · 1.25× · 1.5×
- **Preview button** — listen to the voice before rendering
- Powered by **gTTS** (Google Text-to-Speech, no API key, uses public endpoint)
- **Offline fallback**: pyttsx3 system TTS activates automatically if internet is unavailable

### Motion Effects (7 types)
Every clip gets a different camera movement — no consecutive repeats.

| Motion | Effect |
|---|---|
| `zoom_in` | Slow push-in 1.00 → 1.10× |
| `zoom_out` | Slow pull-out 1.10 → 1.00× |
| `pan_left` | Rightward pan at 1.06× zoom |
| `pan_right` | Leftward pan at 1.06× zoom |
| `pan_up` | Downward tilt at 1.06× zoom |
| `pan_down` | Upward tilt at 1.06× zoom |
| `hook` | Fast punch zoom-out 1.18 → 1.00× (always segment 0) |

### Pexels Clip Matching
- Portrait-first search for Shorts (native vertical content)
- Per-segment visual queries (written by AI or templates)
- Narration keyword extraction injected as a second search angle
- Session-level deduplication — no two segments get the same clip
- Graceful fallback to animated gradient if Pexels is unavailable

### Additional Features
- **Cinematic colour grade** — `eq brightness=-0.10 contrast=1.08 saturation=0.72` for viral styles
- **Hook segment** — first clip always uses the punch zoom-out + larger caption font (25% bigger)
- **Keyword highlighting** — ALL-CAPS words and 80 power words (`never`, `secret`, `brutal`, etc.) appear in accent colour at 112% size in captions
- **Background music** — synthesised locally via FFmpeg (chord pad + reverb); drop MP3s in `music/` to override
- **Intro / Outro cards** — optional title and branding cards
- **Hard cuts or xfade dissolve** — auto-selected by style; configurable
- **Real-time progress** — browser polls render steps (Voice → Clips → Process → Concat → Render)
- **Script editor** — every segment is editable before rendering

---

## Architecture

```
main.py                   FastAPI server — orchestrates all pipeline steps
modules/
  script_gen.py           Gemini → Groq → local template AI chain
  voice_gen.py            gTTS + pyttsx3 fallback, atempo speed control
  visual_gen.py           Pexels download, Ken Burns zoom, cinematic grade
  video_builder.py        ASS subtitles, FFmpeg concat, final assembly
  music_gen.py            FFmpeg chord synthesis, reverb, fade
static/
  index.html              Single-page studio UI (no framework)
music/                    Drop custom MP3s here to override generated music
output/                   Rendered videos (auto-cleaned, keeps last 10)
.env                      Your API keys (never committed)
```

---

## Render Pipeline

```
Topic
  └─▶ 1. Script      Gemini / Groq / template → segments with narration + visual_query
  └─▶ 2. Voice       gTTS per-segment MP3 → atempo speed → timestamps
  └─▶ 3. Clips       Pexels portrait search → download → dedup
  └─▶ 4. Process     zoompan Ken Burns + eq grade baked per clip (cap: 4s render window)
  └─▶ 5. Concat      hard-cut (viral) or xfade dissolve (standard)
  └─▶ 6. Subtitles   ASS file: 3-word chunks, keyword highlights, Hook style seg 0
  └─▶ 7. Music       FFmpeg chord pad at 22% volume (amix normalize=0)
  └─▶ 8. Assemble    libx264 crf=18 · aac 128k · faststart → MP4
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Serve the studio UI |
| GET | `/api/voices` | List all 23 voices |
| GET | `/api/styles` | List all 6 video styles |
| GET | `/api/voice-speeds` | List speed options |
| GET | `/api/caption-styles` | List all 8 caption styles |
| GET | `/api/caption-positions` | List all 7 caption positions |
| POST | `/api/preview-voice` | Generate voice preview MP3 |
| POST | `/api/script` | Generate script (AI or template) |
| POST | `/api/generate` | Render full video |
| GET | `/api/progress/{ts}` | Poll render progress |
| GET | `/api/download/{ts}` | Download finished MP4 |

---

## Requirements

- **Python** 3.10+
- **FFmpeg** 4.0+ with `libass` (for subtitle burn-in) — installed separately
- **Internet** for gTTS narration and Pexels clips (AI keys optional)

### Python packages (`requirements.txt`)

| Package | Purpose |
|---|---|
| `fastapi` + `uvicorn` | HTTP server |
| `pydantic` | Request validation |
| `httpx` | Async HTTP for Gemini / Groq / Pexels |
| `gtts` | Google Text-to-Speech |
| `pyttsx3` | Offline TTS fallback |
| `python-dotenv` | `.env` file loading |

---

## Troubleshooting

**Video renders but has no background clips**
→ Add `PEXELS_API_KEY` to `.env` (free at pexels.com/api)

**Script generation falls back to template every time**
→ Add `GEMINI_API_KEY` to `.env` (free at aistudio.google.com/app/apikey)

**`libass` subtitle error in FFmpeg**
→ Install FFmpeg from a full build: `sudo apt install ffmpeg` on Linux, or use the full Windows build from ffmpeg.org

**`gTTS` fails / no audio**
→ Check internet connection; pyttsx3 offline fallback activates automatically

**FFmpeg not found**
→ Ensure FFmpeg is installed and its `bin/` folder is in your system PATH

**Port 8000 already in use**
→ `python main.py` reads the port from the uvicorn call at the bottom of `main.py`; change `port=8000` to any free port
