"""
Voice Generation  —  gTTS  +  FFmpeg speed control
====================================================
gTTS:  natural speech, 23 languages, no API key.
Speed: FFmpeg atempo filter applied post-synthesis.
       0.75x = slow/clear  |  1.0x = normal  |  1.25x = brisk  |  1.5x = fast

atempo range per filter instance: 0.5 – 2.0
For values outside that range the filters are chained (not needed here).
"""

import asyncio, subprocess, logging
from pathlib import Path
from typing import Tuple, List

log = logging.getLogger("ytgen")

# ══════════════════════════════════════════════════════════════════
#  VOICE SPEED  ←  NEW FEATURE
# ══════════════════════════════════════════════════════════════════

VOICE_SPEEDS = {
    "0.75": {"label": "🐢 0.75× — Slow",          "value": 0.75},
    "1.0":  {"label": "▶ 1.0× — Normal",          "value": 1.0},
    "1.25": {"label": "⚡ 1.25× — Slightly fast", "value": 1.25},
    "1.5":  {"label": "🚀 1.5× — Fast",           "value": 1.5},
}

def _build_atempo_filter(speed: float) -> str:
    """
    Build an FFmpeg audio filter string for speed change.
    atempo is limited to [0.5, 2.0] per instance; chain if needed.
    E.g. 0.25x = atempo=0.5,atempo=0.5
    """
    speed = max(0.25, min(4.0, speed))
    if abs(speed - 1.0) < 0.01:
        return ""                     # no processing needed

    filters = []
    remaining = speed
    # Chain downward (slow)
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    # Chain upward (fast)
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)


def apply_speed(src: Path, dst: Path, speed: float) -> None:
    """
    Adjust audio playback speed via FFmpeg atempo filter.
    Preserves pitch (atempo is a time-stretch, not a rate change).
    Source and destination may be the same file (atomic replace).
    """
    if abs(speed - 1.0) < 0.01:
        if src != dst:
            import shutil; shutil.copy2(src, dst)
        return

    af = _build_atempo_filter(speed)
    tmp = dst.with_suffix(".speed_tmp.mp3")

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-af", af,
         "-codec:a", "libmp3lame", "-q:a", "2",
         str(tmp)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120)

    if r.returncode != 0:
        log.warning("  Speed adjustment failed (%s) — keeping original", r.stderr[-200:])
        if src != dst:
            import shutil; shutil.copy2(src, dst)
        return

    # Atomic replace
    if dst.exists():
        dst.unlink()
    tmp.rename(dst)
    log.info("  Speed: %.2fx applied (%s)", speed, dst.name)


# ─── Voice catalogue ──────────────────────────────────────────────
VOICES = [
    {"id":"en-us", "name":"US English",           "lang":"en","tld":"com",    "flag":"🇺🇸"},
    {"id":"en-uk", "name":"UK English",            "lang":"en","tld":"co.uk",  "flag":"🇬🇧"},
    {"id":"en-au", "name":"Australian English",    "lang":"en","tld":"com.au", "flag":"🇦🇺"},
    {"id":"en-in", "name":"Indian English",        "lang":"en","tld":"co.in",  "flag":"🇮🇳"},
    {"id":"en-ie", "name":"Irish English",         "lang":"en","tld":"ie",     "flag":"🇮🇪"},
    {"id":"en-ca", "name":"Canadian English",      "lang":"en","tld":"ca",     "flag":"🇨🇦"},
    {"id":"en-za", "name":"South African English", "lang":"en","tld":"co.za",  "flag":"🇿🇦"},
    {"id":"es-es", "name":"Spanish (Spain)",       "lang":"es","tld":"es",     "flag":"🇪🇸"},
    {"id":"es-mx", "name":"Spanish (Mexico)",      "lang":"es","tld":"com.mx", "flag":"🇲🇽"},
    {"id":"fr-fr", "name":"French",                "lang":"fr","tld":"fr",     "flag":"🇫🇷"},
    {"id":"de-de", "name":"German",                "lang":"de","tld":"de",     "flag":"🇩🇪"},
    {"id":"hi-in", "name":"Hindi",                 "lang":"hi","tld":"co.in",  "flag":"🇮🇳"},
    {"id":"pt-br", "name":"Portuguese (Brazil)",   "lang":"pt","tld":"com.br", "flag":"🇧🇷"},
    {"id":"pt-pt", "name":"Portuguese (Portugal)", "lang":"pt","tld":"pt",     "flag":"🇵🇹"},
    {"id":"it-it", "name":"Italian",               "lang":"it","tld":"it",     "flag":"🇮🇹"},
    {"id":"nl-nl", "name":"Dutch",                 "lang":"nl","tld":"nl",     "flag":"🇳🇱"},
    {"id":"pl-pl", "name":"Polish",                "lang":"pl","tld":"pl",     "flag":"🇵🇱"},
    {"id":"tr-tr", "name":"Turkish",               "lang":"tr","tld":"com.tr", "flag":"🇹🇷"},
    {"id":"ru-ru", "name":"Russian",               "lang":"ru","tld":"ru",     "flag":"🇷🇺"},
    {"id":"ja-jp", "name":"Japanese",              "lang":"ja","tld":"co.jp",  "flag":"🇯🇵"},
    {"id":"ko-kr", "name":"Korean",                "lang":"ko","tld":"co.kr",  "flag":"🇰🇷"},
    {"id":"zh-cn", "name":"Chinese (Mandarin)",    "lang":"zh-CN","tld":"com", "flag":"🇨🇳"},
    {"id":"ar-ae", "name":"Arabic",                "lang":"ar","tld":"com",    "flag":"🇦🇪"},
]

_VOICE_MAP = {v["id"]: (v["lang"], v["tld"]) for v in VOICES}

PREVIEW_TEXT = {
    "en":  "Hello! This is how I sound. I will narrate your YouTube video clearly and naturally.",
    "es":  "Hola, así es como sueno. Voy a narrar tu vídeo de YouTube.",
    "fr":  "Bonjour, voici ma voix. Je vais narrer votre vidéo YouTube.",
    "de":  "Hallo, so klingt meine Stimme. Ich werde Ihr YouTube-Video erzählen.",
    "hi":  "नमस्ते! यह मेरी आवाज़ है। मैं आपके YouTube वीडियो को नैरेट करूँगा।",
    "pt":  "Olá, esta é minha voz. Vou narrar o seu vídeo do YouTube.",
    "it":  "Ciao, questa è la mia voce. Narrerò il tuo video YouTube.",
    "ru":  "Привет, это мой голос. Я буду озвучивать ваше видео.",
    "ja":  "こんにちは、これが私の声です。あなたのYouTube動画をナレーションします。",
    "ko":  "안녕하세요, 이것이 제 목소리입니다. YouTube 영상을 나레이션하겠습니다.",
    "ar":  "مرحبا، هذا صوتي. سأقوم بالتعليق على فيديو YouTube الخاص بك.",
    "zh":  "你好，这是我的声音。我将为你的YouTube视频配音。",
    "nl":  "Hallo, dit is mijn stem. Ik ga je YouTube-video vertellen.",
    "tr":  "Merhaba, bu benim sesim. YouTube videonuzu anlatacağım.",
    "pl":  "Cześć, to jest mój głos. Opiszę twój film na YouTube.",
}


def _get_preview_text(voice_id: str) -> str:
    lang, _ = _VOICE_MAP.get(voice_id, ("en", "com"))
    return PREVIEW_TEXT.get(lang[:2], PREVIEW_TEXT["en"])


# ─── Core synthesis ───────────────────────────────────────────────

def _synth_gtts(text: str, voice_id: str, out: Path) -> None:
    from gtts import gTTS
    lang, tld = _VOICE_MAP.get(voice_id, ("en", "com"))
    gTTS(text=text, lang=lang, tld=tld, slow=False).save(str(out))


def _synth_pyttsx3_fallback(text: str, out: Path) -> None:
    import pyttsx3
    wav = out.with_suffix(".wav")
    engine = pyttsx3.init()
    try:
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 1.0)
        engine.save_to_file(text, str(wav))
        engine.runAndWait()
    finally:
        try: engine.stop()
        except: pass
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav),
         "-codec:a", "libmp3lame", "-q:a", "2", str(out)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    wav.unlink(missing_ok=True)


async def synthesize(text: str, voice_id: str, out: Path) -> None:
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _synth_gtts, text, voice_id, out)
        if out.exists() and out.stat().st_size > 500:
            return
    except Exception as e:
        log.warning("  gTTS failed: %s — pyttsx3 fallback", e)
    try:
        await loop.run_in_executor(None, _synth_pyttsx3_fallback, text, out)
    except Exception as e:
        raise RuntimeError(f"All TTS engines failed: {e}")
    if not out.exists() or out.stat().st_size < 200:
        raise RuntimeError(f"TTS produced no output for: {text[:40]!r}")


def get_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, encoding="utf-8", errors="replace")
    try:
        d = float(r.stdout.strip())
        return d if d > 0.1 else 3.0
    except Exception:
        return 3.0


def concat_audio(files: List[Path], out: Path) -> None:
    lst = out.parent / "_audio_list.txt"
    lst.write_text(
        "\n".join(f"file '{p.name}'" for p in files),
        encoding="utf-8")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst.name,
         "-ar", "44100", "-ac", "2", "-codec:a", "libmp3lame", "-q:a", "2",
         out.name],
        capture_output=True, encoding="utf-8", errors="replace",
        timeout=120, cwd=str(out.parent))
    lst.unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"Audio concat failed:\n{r.stderr[-400:]}")


async def generate_all(
    segments:    list,
    voice_id:    str,
    wdir:        Path,
    voice_speed: float = 1.0,     # ← NEW: speed multiplier
    **kwargs
) -> Tuple[Path, List[Tuple[float, float]]]:
    """
    Synthesise one MP3 per segment, apply speed adjustment,
    build timestamp map, concat into single full-track MP3.

    voice_speed: 0.75 = slow, 1.0 = normal, 1.25 = brisk, 1.5 = fast
    """
    files, timestamps, cursor = [], [], 0.0
    GAP = 0.25   # seconds of silence between segments

    for i, seg in enumerate(segments):
        text = str(seg.get("narration", "")).strip() or "Continue."
        raw  = wdir / f"seg_{i:03d}_voice_raw.mp3"
        out  = wdir / f"seg_{i:03d}_voice.mp3"

        log.info("  Voice %d/%d: '%s…'", i+1, len(segments), text[:50])
        await synthesize(text, voice_id, raw)

        # Apply speed BEFORE measuring duration so timestamps are accurate
        apply_speed(raw, out, voice_speed)
        if raw.exists() and raw != out:
            raw.unlink(missing_ok=True)

        dur = get_duration(out)
        timestamps.append((cursor, cursor + dur))
        cursor += dur + GAP
        files.append(out)
        log.info("    -> %.1fs  (speed=%.2fx)", dur, voice_speed)

    combined = wdir / "full_voice.mp3"
    concat_audio(files, combined)
    log.info("Full audio: %.1fs", get_duration(combined))
    return combined, timestamps
