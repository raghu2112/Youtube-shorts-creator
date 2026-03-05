"""
AI YouTube Shorts Generator — Backend
Run: python main.py
Open: http://127.0.0.1:8000
"""

import os, sys, traceback, asyncio, shutil, subprocess
import textwrap, time, random, math, functools, json
from pathlib import Path
from typing import Optional

import httpx, numpy as np
from gtts import gTTS
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ╔══════════════════════════════════════════════╗
# ║         SET YOUR API KEYS HERE               ║
# ╚══════════════════════════════════════════════╝
ANTHROPIC_API_KEY = "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"   # https://console.anthropic.com
PEXELS_API_KEY    = "siOJkQZDrixx22IYFoPclaGJXNbIPO8P8VUmesZUf3ykzheZ5RyPu2vt"       # https://www.pexels.com/api
# ═══════════════════════════════════════════════

BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI Shorts Generator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

VIDEO_WIDTH  = 1080
VIDEO_HEIGHT = 1920
FPS          = 30

# ───────────────────────────────────────────────
# Voice catalogue
# ───────────────────────────────────────────────
# Each voice maps to a gTTS (lang, tld) pair for regional accent variety.
# gTTS tld options:  com=US, co.uk=UK, com.au=AU, co.in=IN, ca=CA, ie=Ireland, co.za=SA
VOICES = [
    {"id":"en-US-1", "name":"Aria",      "desc":"US English",      "lang":"en","flag":"🇺🇸","gtts_lang":"en","gtts_tld":"com"},
    {"id":"en-US-2", "name":"Jenny",     "desc":"US English",      "lang":"en","flag":"🇺🇸","gtts_lang":"en","gtts_tld":"com"},
    {"id":"en-US-3", "name":"Guy",       "desc":"US English",      "lang":"en","flag":"🇺🇸","gtts_lang":"en","gtts_tld":"us"},
    {"id":"en-US-4", "name":"Sara",      "desc":"US English",      "lang":"en","flag":"🇺🇸","gtts_lang":"en","gtts_tld":"com"},
    {"id":"en-GB-1", "name":"Sonia",     "desc":"UK English",      "lang":"en","flag":"🇬🇧","gtts_lang":"en","gtts_tld":"co.uk"},
    {"id":"en-GB-2", "name":"Ryan",      "desc":"UK English",      "lang":"en","flag":"🇬🇧","gtts_lang":"en","gtts_tld":"co.uk"},
    {"id":"en-AU-1", "name":"Natasha",   "desc":"Australian",      "lang":"en","flag":"🇦🇺","gtts_lang":"en","gtts_tld":"com.au"},
    {"id":"en-AU-2", "name":"William",   "desc":"Australian",      "lang":"en","flag":"🇦🇺","gtts_lang":"en","gtts_tld":"com.au"},
    {"id":"en-IN-1", "name":"Neerja",    "desc":"Indian English",  "lang":"en","flag":"🇮🇳","gtts_lang":"en","gtts_tld":"co.in"},
    {"id":"en-IE-1", "name":"Emily",     "desc":"Irish English",   "lang":"en","flag":"🇮🇪","gtts_lang":"en","gtts_tld":"ie"},
    {"id":"en-ZA-1", "name":"Leah",      "desc":"South African",   "lang":"en","flag":"🇿🇦","gtts_lang":"en","gtts_tld":"co.za"},
    {"id":"en-CA-1", "name":"Linda",     "desc":"Canadian",        "lang":"en","flag":"🇨🇦","gtts_lang":"en","gtts_tld":"ca"},
    {"id":"es-ES-1", "name":"Elvira",    "desc":"Spanish (Spain)", "lang":"es","flag":"🇪🇸","gtts_lang":"es","gtts_tld":"es"},
    {"id":"es-MX-1", "name":"Dalia",     "desc":"Spanish (Mexico)","lang":"es","flag":"🇲🇽","gtts_lang":"es","gtts_tld":"com.mx"},
    {"id":"es-US-1", "name":"Valentina", "desc":"Spanish (US)",    "lang":"es","flag":"🇺🇸","gtts_lang":"es","gtts_tld":"com"},
    {"id":"fr-FR-1", "name":"Denise",    "desc":"French (France)", "lang":"fr","flag":"🇫🇷","gtts_lang":"fr","gtts_tld":"fr"},
    {"id":"fr-CA-1", "name":"Sylvie",    "desc":"French (Canada)", "lang":"fr","flag":"🇨🇦","gtts_lang":"fr","gtts_tld":"ca"},
    {"id":"de-DE-1", "name":"Katja",     "desc":"German",          "lang":"de","flag":"🇩🇪","gtts_lang":"de","gtts_tld":"de"},
    {"id":"hi-IN-1", "name":"Swara",     "desc":"Hindi",           "lang":"hi","flag":"🇮🇳","gtts_lang":"hi","gtts_tld":"co.in"},
    {"id":"ja-JP-1", "name":"Nanami",    "desc":"Japanese",        "lang":"ja","flag":"🇯🇵","gtts_lang":"ja","gtts_tld":"co.jp"},
    {"id":"zh-CN-1", "name":"Xiaoxiao",  "desc":"Chinese",         "lang":"zh","flag":"🇨🇳","gtts_lang":"zh-CN","gtts_tld":"com"},
    {"id":"zh-TW-1", "name":"HsiaoChen", "desc":"Chinese (TW)",    "lang":"zh","flag":"🇹🇼","gtts_lang":"zh-TW","gtts_tld":"com"},
    {"id":"ko-KR-1", "name":"SunHi",     "desc":"Korean",          "lang":"ko","flag":"🇰🇷","gtts_lang":"ko","gtts_tld":"co.kr"},
    {"id":"pt-BR-1", "name":"Francisca", "desc":"Portuguese (BR)", "lang":"pt","flag":"🇧🇷","gtts_lang":"pt","gtts_tld":"com.br"},
    {"id":"pt-PT-1", "name":"Raquel",    "desc":"Portuguese (PT)", "lang":"pt","flag":"🇵🇹","gtts_lang":"pt","gtts_tld":"pt"},
    {"id":"it-IT-1", "name":"Elsa",      "desc":"Italian",         "lang":"it","flag":"🇮🇹","gtts_lang":"it","gtts_tld":"it"},
    {"id":"ru-RU-1", "name":"Svetlana",  "desc":"Russian",         "lang":"ru","flag":"🇷🇺","gtts_lang":"ru","gtts_tld":"ru"},
    {"id":"ar-AE-1", "name":"Fatima",    "desc":"Arabic",          "lang":"ar","flag":"🇦🇪","gtts_lang":"ar","gtts_tld":"com"},
    {"id":"nl-NL-1", "name":"Colette",   "desc":"Dutch",           "lang":"nl","flag":"🇳🇱","gtts_lang":"nl","gtts_tld":"nl"},
    {"id":"tr-TR-1", "name":"Emel",      "desc":"Turkish",         "lang":"tr","flag":"🇹🇷","gtts_lang":"tr","gtts_tld":"com.tr"},
    {"id":"pl-PL-1", "name":"Zofia",     "desc":"Polish",          "lang":"pl","flag":"🇵🇱","gtts_lang":"pl","gtts_tld":"pl"},
]

# Build a lookup: voice_id → gTTS params
_VOICE_MAP = {v["id"]: (v["gtts_lang"], v["gtts_tld"]) for v in VOICES}

VOICE_PREVIEW_TEXT = {
    "en": "Hey! This is how I sound. I will narrate your short video with this voice.",
    "es": "Hola, así es como sueno. Seré el narrador de tu video corto.",
    "fr": "Bonjour, voici ma voix. Je vais narrer votre vidéo courte.",
    "de": "Hallo, so klingt meine Stimme. Ich werde dein Kurzvideo erzählen.",
    "hi": "नमस्ते, मैं ऐसे बोलता हूँ। मैं आपके शॉर्ट वीडियो की आवाज़ बनूँगा।",
    "ja": "こんにちは。これが私の声です。あなたの動画をナレーションします。",
    "zh": "你好，这是我的声音。我将为你的短视频配音。",
    "ko": "안녕하세요, 이것이 제 목소리입니다. 당신의 영상을 나레이션하겠습니다。",
    "pt": "Olá, esta é minha voz. Vou narrar o seu vídeo curto.",
    "it": "Ciao, questa è la mia voce. Narrerò il tuo video breve.",
    "ru": "Привет, это мой голос. Я буду озвучивать ваше видео.",
    "ar": "مرحبا، هذا صوتي. سأقوم بالتعليق على الفيديو القصير الخاص بك.",
    "nl": "Hallo, dit is mijn stem. Ik zal je korte video vertellen.",
    "tr": "Merhaba, bu benim sesim. Kısa videonuzu anlatacağım.",
    "pl": "Cześć, to jest mój głos. Opiszę twój krótki film.",
}

MOODS = {
    "motivational": {"label":"🔥 Motivational","query":"success athlete motivation winner",
        "colors":[(160,10,0),(220,70,0),(255,130,0)],"overlay":(25,8,0,110),
        "tone":"energetic, powerful, inspiring, action-oriented"},
    "calm":         {"label":"🌊 Calm","query":"nature ocean zen peaceful",
        "colors":[(0,30,70),(0,70,130),(10,120,170)],"overlay":(0,8,20,100),
        "tone":"soothing, gentle, mindful, peaceful"},
    "thriller":     {"label":"😱 Thriller","query":"dark dramatic suspense mystery",
        "colors":[(10,0,20),(55,0,75),(110,0,55)],"overlay":(12,0,22,145),
        "tone":"suspenseful, intense, dramatic, gripping"},
    "educational":  {"label":"🎓 Educational","query":"science technology innovation",
        "colors":[(0,25,75),(0,70,150),(0,130,190)],"overlay":(0,8,28,110),
        "tone":"informative, clear, engaging, factual"},
    "comedy":       {"label":"😂 Comedy","query":"fun colorful vibrant playful",
        "colors":[(170,0,90),(215,75,0),(175,150,0)],"overlay":(22,8,0,90),
        "tone":"funny, witty, playful, humorous"},
    "documentary":  {"label":"🌍 Documentary","query":"cinematic landscape world travel",
        "colors":[(18,18,18),(55,38,18),(95,65,28)],"overlay":(10,10,10,130),
        "tone":"factual, journalistic, thoughtful, cinematic"},
    "horror":       {"label":"👻 Horror","query":"dark eerie fog mysterious night",
        "colors":[(5,0,0),(28,0,0),(58,8,8)],"overlay":(15,0,0,155),
        "tone":"eerie, unsettling, dark, creepy"},
    "business":     {"label":"💼 Business","query":"office city corporate professional",
        "colors":[(8,18,38),(18,38,75),(28,58,115)],"overlay":(10,14,28,120),
        "tone":"professional, confident, authoritative, strategic"},
}

LANG_NAMES = {
    "en":"English","es":"Spanish","fr":"French","de":"German","hi":"Hindi",
    "ja":"Japanese","zh":"Chinese","ko":"Korean","pt":"Portuguese","it":"Italian","ru":"Russian",
}

# ───────────────────────────────────────────────
# Caption styles & placements
# ───────────────────────────────────────────────
# ASS colour format: &HAABBGGRR  (alpha, blue, green, red — reversed from HTML)
CAPTION_STYLES = {
    "box": {
        "label": "📦 Box",
        "desc":  "White text · dark box",
        # White text on a semi-transparent black rectangle — most readable
        "primary":     "&H00FFFFFF",
        "secondary":   "&H000000FF",
        "outline_col": "&H00000000",
        "back_col":    "&HAA000000",
        "bold": -1, "border_style": 3, "outline": 0, "shadow": 6,
        "fontsize": 72,
    },
    "classic": {
        "label": "✨ Classic",
        "desc":  "White · drop shadow",
        "primary":     "&H00FFFFFF",
        "secondary":   "&H000000FF",
        "outline_col": "&H00000000",
        "back_col":    "&H00000000",
        "bold": -1, "border_style": 1, "outline": 3, "shadow": 5,
        "fontsize": 72,
    },
    "neon": {
        "label": "💜 Neon",
        "desc":  "White · purple glow",
        # White text with a vivid purple/magenta glow outline
        "primary":     "&H00FFFFFF",
        "secondary":   "&H000000FF",
        "outline_col": "&H00FF52BE",   # magenta glow  (BGR: BE 52 FF)
        "back_col":    "&H00000000",
        "bold": -1, "border_style": 1, "outline": 5, "shadow": 10,
        "fontsize": 74,
    },
    "outlined": {
        "label": "⬛ Outlined",
        "desc":  "White · thick outline",
        "primary":     "&H00FFFFFF",
        "secondary":   "&H000000FF",
        "outline_col": "&H00000000",
        "back_col":    "&H00000000",
        "bold": -1, "border_style": 1, "outline": 7, "shadow": 0,
        "fontsize": 76,
    },
    "minimal": {
        "label": "🔤 Minimal",
        "desc":  "Small · clean · subtle",
        "primary":     "&H00FFFFFF",
        "secondary":   "&H000000FF",
        "outline_col": "&H80000000",
        "back_col":    "&H00000000",
        "bold": 0, "border_style": 1, "outline": 2, "shadow": 2,
        "fontsize": 58,
    },
    "tiktok": {
        "label": "🔥 TikTok",
        "desc":  "Yellow · bold · big",
        # Bright yellow like viral TikTok captions
        "primary":     "&H0000FFFF",   # yellow (BGR: 00 FF FF)
        "secondary":   "&H000000FF",
        "outline_col": "&H00000000",
        "back_col":    "&H00000000",
        "bold": -1, "border_style": 1, "outline": 5, "shadow": 0,
        "fontsize": 82,
    },
    "cinematic": {
        "label": "🎬 Cinematic",
        "desc":  "Cream · elegant · italic",
        # Warm cream italic — documentary / film style
        "primary":     "&H00D0E8FF",   # cream (BGR: D0 E8 FF)
        "secondary":   "&H000000FF",
        "outline_col": "&H00000000",
        "back_col":    "&H00000000",
        "bold": 0, "border_style": 1, "outline": 3, "shadow": 4,
        "fontsize": 68, "italic": -1,
    },
    "fire": {
        "label": "🔴 Fire",
        "desc":  "Orange-red · high energy",
        "primary":     "&H000052FF",   # orange-red (BGR: 00 52 FF)
        "secondary":   "&H000000FF",
        "outline_col": "&H00000000",
        "back_col":    "&H00000000",
        "bold": -1, "border_style": 1, "outline": 5, "shadow": 0,
        "fontsize": 78,
    },
}

CAPTION_PLACEMENTS = {
    "bottom": {"label": "⬇ Bottom", "alignment": 2, "margin_v": 90},
    "center": {"label": "⬛ Center", "alignment": 5, "margin_v": 0},
    "top":    {"label": "⬆ Top",    "alignment": 8, "margin_v": 90},
}

# ───────────────────────────────────────────────
# Request models
# ───────────────────────────────────────────────
class ScriptRequest(BaseModel):
    topic: str
    mood: str = "motivational"
    length_seconds: int = 30
    language: str = "en"

class VoicePreviewRequest(BaseModel):
    voice_id: str
    lang: str = "en"

class GenerateRequest(BaseModel):
    script: list
    voice: str = "en-US-1"
    mood: str = "motivational"
    length_seconds: int = 30
    show_captions: bool = True
    topic: str = ""
    caption_style: str = "box"
    caption_placement: str = "bottom"

class GenerateResponse(BaseModel):
    status: str
    video_url: str = ""
    message: str = ""

# ───────────────────────────────────────────────
# Utilities
# ───────────────────────────────────────────────
def check_ffmpeg():
    return shutil.which("ffmpeg") is not None, shutil.which("ffprobe") is not None

def get_audio_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True)
    try:
        d = float(r.stdout.strip())
        return d if d > 0.5 else 12.0
    except ValueError:
        return 12.0

# ───────────────────────────────────────────────
# Script generation
# ───────────────────────────────────────────────
def fallback_script(topic: str, mood: str, length_seconds: int) -> list:
    p = topic.strip().rstrip(".")
    count = max(5, min(14, length_seconds // 3))
    banks = {
        "motivational":[
            f"This is your sign to master {p}.",
            "Most people quit right before the breakthrough.",
            "The ones who win show up every single day.",
            "It starts with one decision made right now.",
            "Discipline will always beat motivation.",
            f"Master {p} and your entire life transforms.",
            "Stop waiting for the perfect moment.",
            "Your future is built in the next five minutes.",
            "The secret is to start before you feel ready.",
            "Write this down — it will change everything.",
            "Your only competition is who you were yesterday.",
            "Share this with someone who needs to hear it.",
            "Follow for daily mindset shifts.",
            "The clock is ticking. Are you ready?"],
        "calm":[
            f"Let us talk about {p}.",
            "Take a slow deep breath right now.",
            "The world gets quieter when you pay attention.",
            "There is beauty hiding in the ordinary.",
            "One small step forward is still real progress.",
            f"{p} teaches us the power of presence.",
            "You do not need to rush anything today.",
            "Peace is a practice not a destination.",
            "Let go of what is beyond your control.",
            "Rest is not a reward — it is a requirement.",
            "You are exactly where you need to be.",
            "Breathe. Everything will work itself out.",
            "Follow for more peaceful moments.",
            "Save this for when you need it most."],
        "thriller":[
            f"The truth about {p} is darker than you think.",
            "Nobody is talking about this until now.",
            "Pay very close attention to what comes next.",
            "It started with a single unexplained event.",
            "The deeper you dig the stranger it gets.",
            "Three people disappeared after discovering this.",
            "The pattern became impossible to ignore.",
            f"And {p} was at the center of everything.",
            "Connect the dots. You will see it too.",
            "Once you see this you cannot unsee it.",
            "What do you think is really happening here?",
            "Comment below. We need to discuss this.",
            "Follow before this gets removed.",
            "Part two drops tomorrow night."],
        "educational":[
            f"Here is what science actually says about {p}.",
            "Most people have been getting this completely wrong.",
            "Let me explain it in the simplest terms.",
            "Researchers spent decades proving this one fact.",
            "The data is far more surprising than you think.",
            f"{p} works because of one core principle.",
            "Here is the insight that changes everything.",
            "Apply this and watch what happens.",
            "The results are backed by peer reviewed research.",
            "This is why the experts pay close attention.",
            "Share this with someone who needs to know.",
            "Follow for more science backed content.",
            "Save this video for future reference.",
            "Knowledge like this is real power."],
        "comedy":[
            f"Nobody warns you about the reality of {p}.",
            "And honestly I felt this deep in my soul.",
            "Why is this so devastatingly accurate?",
            "Scientists have spent years not understanding this.",
            f"{p} said absolutely not today.",
            "Your brain at three in the morning apparently.",
            "The accuracy of this should be illegal.",
            "Send this to someone who needs therapy.",
            "If you know you genuinely know.",
            "This is peak human experience right here.",
            "My entire life summed up in one video.",
            "Part two is somehow even more accurate.",
            "Follow for more painfully relatable content.",
            "Like if this described your whole week."],
        "documentary":[
            f"The story of {p} begins in an unlikely place.",
            "For decades most of this remained completely hidden.",
            "The evidence was hiding in plain sight all along.",
            "Local communities felt the shift before anyone else.",
            "Experts still disagree on what happens next.",
            f"But {p} continues to reshape our world today.",
            "The question is are we paying attention?",
            "History has a habit of repeating its patterns.",
            "What we do now will echo for generations.",
            "The choice ultimately belongs to all of us.",
            "Follow for more untold stories from around the world.",
            "Share this with someone who needs to see it.",
            "The full documentary drops this Friday.",
            "Subscribe so you never miss another one."],
        "horror":[
            f"Something is deeply wrong with {p}.",
            "Watch this one with the lights on.",
            "It started quietly three years ago.",
            "Nobody believed the first witnesses.",
            "Then the reports began multiplying overnight.",
            "The footage still cannot be explained.",
            "Investigators found something they should not have.",
            f"And {p} was only the beginning.",
            "Sleep with the lights on tonight.",
            "You have officially been warned.",
            "Part two is somehow more disturbing.",
            "Subscribe if you actually dare.",
            "Do not say we did not warn you.",
            "They may already be watching this too."],
        "business":[
            f"The smartest operators deeply understand {p}.",
            "Here is what business schools never teach you.",
            "Rule one — protect your time at all costs.",
            "Rule two — cash flow is always the king.",
            "Most businesses fail at this one critical step.",
            f"Those who master {p} scale fast and hard.",
            "The difference is never talent it is systems.",
            "Build once. Profit for years.",
            "Your network is worth more than your degree.",
            "Double down ruthlessly on what is working.",
            "Cut everything else without mercy.",
            "This is the advice I needed at twenty two.",
            "Follow for more real business frameworks.",
            "Save this and review it every single quarter."],
    }
    lines = banks.get(mood, banks["motivational"])
    return lines[:count]

async def generate_script_claude(topic: str, mood: str, length_seconds: int, language: str) -> list:
    target = max(5, min(14, length_seconds // 3))
    lang_name = LANG_NAMES.get(language, "English")
    tone = MOODS.get(mood, MOODS["motivational"])["tone"]
    prompt = f"""You are a viral YouTube Shorts scriptwriter.
Topic: {topic}
Mood: {tone}
Language: {lang_name}
Number of caption lines: exactly {target}
Rules:
- Each line must be 6 to 14 words (shown as on-screen caption)
- Write entirely in {lang_name}
- Tone must be: {tone}
- Make each line punchy, emotionally engaging, shareable
- End with a strong call-to-action
Return ONLY a valid JSON array of strings. No markdown, no explanation.
Example: ["Line one here.", "Line two here.", "Call to action."]"""
    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-sonnet-4-20250514","max_tokens":800,
                  "messages":[{"role":"user","content":prompt}]},
        )
        if r.status_code != 200:
            raise ValueError(f"Claude API {r.status_code}: {r.text[:200]}")
        raw = r.json()["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"): raw = raw[4:]
        sentences = json.loads(raw.strip())
        if not isinstance(sentences, list) or len(sentences) < 2:
            raise ValueError("Invalid response from Claude")
        return [str(s) for s in sentences]

# ───────────────────────────────────────────────
# Audio
# ───────────────────────────────────────────────
# ───────────────────────────────────────────────
# Audio  (Google TTS — free, online, reliable)
# ───────────────────────────────────────────────
def _gtts_lang_tld(voice_id: str):
    """Return (lang, tld) for the given voice id."""
    return _VOICE_MAP.get(voice_id, ("en", "com"))

def _make_audio_sync(text: str, voice_id: str, out: Path) -> None:
    """Blocking gTTS call — run in thread executor."""
    lang, tld = _gtts_lang_tld(voice_id)
    tts = gTTS(text=text, lang=lang, tld=tld, slow=False)
    tts.save(str(out))

async def make_audio(text: str, voice_id: str, out: Path) -> None:
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _make_audio_sync, text, voice_id, out)
    except Exception as e:
        raise RuntimeError(f"gTTS failed: {e}")

# ───────────────────────────────────────────────
# Pexels background
# ───────────────────────────────────────────────
def _pexels_best_file(video: dict) -> Optional[dict]:
    """
    Pick the best video file from a Pexels video object.
    Priority: portrait (w <= h) → highest resolution ≤ 1920px tall → largest file.
    """
    files = video.get("video_files", [])
    if not files:
        return None
    portrait = [f for f in files if f.get("width", 9999) <= f.get("height", 0)]
    pool = portrait if portrait else files
    # prefer HD but not 4K (too slow to download); sort by height desc, cap at 1920
    pool = [f for f in pool if f.get("height", 0) <= 1920] or pool
    pool.sort(key=lambda f: f.get("height", 0), reverse=True)
    return pool[0]

async def _pexels_search(client: httpx.AsyncClient, query: str,
                         per_page: int = 10) -> list:
    """Run a single Pexels video search and return the videos list."""
    r = await client.get(
        "https://api.pexels.com/videos/search",
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "per_page": per_page,
                "orientation": "portrait", "size": "medium"},
    )
    if r.status_code != 200:
        print(f"  Pexels HTTP {r.status_code} for query: {query}")
        return []
    return r.json().get("videos", [])

async def download_pexels(topic: str, mood_query: str, out: Path) -> bool:
    """
    Search Pexels for a video relevant to the user's topic.
    Strategy:
      1. Try the full topic string (most relevant)
      2. Try first 3 words of topic (broader)
      3. Fall back to mood keyword
    Downloads the highest-quality portrait file found.
    """
    if not PEXELS_API_KEY or PEXELS_API_KEY == "your-pexels-key-here":
        return False

    # Build search queries from most-specific to least-specific
    topic_clean = " ".join(topic.strip().split()[:6])          # first 6 words
    topic_short = " ".join(topic.strip().split()[:3])          # first 3 words
    queries = []
    if topic_clean:
        queries.append(topic_clean)
    if topic_short and topic_short != topic_clean:
        queries.append(topic_short)
    queries.append(mood_query)                                   # mood fallback
    queries.append("nature cinematic vertical")                  # last resort

    try:
        async with httpx.AsyncClient(timeout=50) as client:
            for query in queries:
                print(f"  🔍 Pexels: '{query}'")
                videos = await _pexels_search(client, query)
                if not videos:
                    continue
                # Prefer portrait-oriented videos
                portrait_vids = [v for v in videos
                                 if v.get("width", 9999) <= v.get("height", 0)]
                pool = portrait_vids if portrait_vids else videos
                random.shuffle(pool)          # vary results across generations
                for video in pool[:5]:
                    chosen = _pexels_best_file(video)
                    if not chosen:
                        continue
                    url = chosen.get("link") or chosen.get("url", "")
                    if not url:
                        continue
                    print(f"  ⬇️  Downloading {chosen.get('height',0)}p portrait…")
                    try:
                        async with client.stream("GET", url,
                                                 follow_redirects=True,
                                                 timeout=60) as resp:
                            if resp.status_code == 200:
                                with open(out, "wb") as f:
                                    async for chunk in resp.aiter_bytes(131072):
                                        f.write(chunk)
                                if out.stat().st_size > 100_000:
                                    print(f"  ✅ {out.stat().st_size/1_048_576:.1f} MB")
                                    return True
                    except Exception as e:
                        print(f"  Download error: {e}")
                        continue
        return False
    except Exception as e:
        print(f"Pexels error: {e}")
        return False

# ───────────────────────────────────────────────
# Frame rendering
# ───────────────────────────────────────────────
# ───────────────────────────────────────────────────────
# Fast rendering — pure FFmpeg (no per-frame Python loop)
# ───────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────
# Fast rendering  (~10–20 s for a 30-second Short)
#
# Strategy:
#   • Background  → FFmpeg lavfi `color` source (animated gradient via
#                   geq on a tiny 2-frame PNG strip) — no zoompan ever
#   • Pexels bg   → stream_loop + scale/crop + fast colorbalance tint
#   • Captions    → ASS subtitle file burned with libass  (single filter,
#                   GPU-friendly; far faster than chained drawtext)
#   • Encoder     → libx264 -preset ultrafast -crf 26 -threads 0
# ──────────────────────────────────────────────────────────────────

def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def _make_gradient_png(w: int, h: int, colors: list, out: Path) -> None:
    """Fast gradient PNG — one horizontal scanline per row, no loops."""
    c0, c1, c2 = colors
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        t  = y / h
        rc = _lerp(c0, c1, t * 2) if t < 0.5 else _lerp(c1, c2, (t - 0.5) * 2)
        arr[y, :] = rc
    Image.fromarray(arr).save(str(out))

def _ass_escape(text: str) -> str:
    """Minimal ASS escape — only special chars that break the format."""
    return (text
        .replace("\\", "")
        .replace("{",  "")
        .replace("}",  "")
        .replace("\n", " ")
        .strip())

def _seconds_to_ass(t: float) -> str:
    h  = int(t // 3600)
    m  = int((t % 3600) // 60)
    s  = t % 60
    return f"{h}:{m:02d}:{s:06.3f}"  # e.g. 0:00:03.250

def _write_ass(sentences: list, duration: float, out: Path,
               font_name: str = "Arial", font_size: int = 72,
               style_id: str = "box", placement_id: str = "bottom") -> None:
    """
    Write an ASS subtitle file with the chosen visual style and placement.
    Supports 8 styles × 3 placements configured via CAPTION_STYLES / CAPTION_PLACEMENTS.
    """
    n       = len(sentences)
    seg     = duration / n
    fade_ms = min(250, int(seg * 150))

    s  = CAPTION_STYLES.get(style_id,     CAPTION_STYLES["box"])
    p  = CAPTION_PLACEMENTS.get(placement_id, CAPTION_PLACEMENTS["bottom"])

    fs       = s.get("fontsize", font_size)
    bold     = s.get("bold", -1)
    italic   = s.get("italic", 0)
    bstyle   = s.get("border_style", 3)
    outline  = s.get("outline", 0)
    shadow   = s.get("shadow", 6)
    align    = p["alignment"]
    margin_v = p["margin_v"]

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {VIDEO_WIDTH}\n"
        f"PlayResY: {VIDEO_HEIGHT}\n"
        "WrapStyle: 1\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
        "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Cap,{font_name},{fs},"
        f"{s['primary']},{s['secondary']},{s['outline_col']},{s['back_col']},"
        f"{bold},{italic},0,0,"
        f"100,100,2,0,{bstyle},{outline},{shadow},"
        f"{align},60,60,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )

    events = []
    for i, raw in enumerate(sentences):
        t0  = i * seg
        t1  = t0 + seg
        txt = _ass_escape(raw)
        tag = f"{{\\fad({fade_ms},{fade_ms})}}"
        events.append(
            f"Dialogue: 0,{_seconds_to_ass(t0)},{_seconds_to_ass(t1)},"
            f"Cap,,0,0,0,,{tag}{txt}"
        )
    out.write_text(header + "\n".join(events), encoding="utf-8")

def _find_font_name() -> str:
    """Return a font name available on the system (for ASS header)."""
    for name, path in [
        ("Arial",           r"C:/Windows/Fonts/arial.ttf"),
        ("Calibri",         r"C:/Windows/Fonts/calibri.ttf"),
        ("Verdana",         r"C:/Windows/Fonts/verdana.ttf"),
        ("DejaVu Sans",     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("Liberation Sans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        ("Ubuntu",          "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"),
    ]:
        if os.path.exists(path):
            return name
    return "Arial"   # fallback; libass will pick any sans-serif

def _ffmpeg_escape_path(p) -> str:
    """
    Escape a file path for use inside an FFmpeg -vf filter string.
    NOTE: This is only used as a fallback. The preferred approach is
    to pass just the filename and set cwd= in subprocess.run().
    """
    s = str(p).replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        s = s[0] + "\\:" + s[2:]
    s = s.replace(" ", "\\ ")
    return s


def build_video(sentences, audio_path, output_path, duration, mood,
                show_captions, bg_path=None,
                caption_style="box", caption_placement="bottom"):
    """
    YouTube-Shorts-style renderer — pure FFmpeg, no per-frame Python.

    KEY TRICK for Windows paths with spaces / drive letters:
      All file arguments use absolute paths on the -i / -vf flags.
      The ASS subtitle filter uses ONLY the bare filename (subs.ass)
      and subprocess.run is called with cwd=<output_dir>, so FFmpeg
      finds the file in its working directory — no path escaping at all.

    Pexels path   : full-bleed portrait video → slight dim → captions
    Gradient path : animated gradient PNG → captions
    Encode        : libx264 veryfast/ultrafast, ~10–25 s render time
    """
    cfg        = MOODS.get(mood, MOODS["motivational"])
    colors     = cfg["colors"]
    work_dir   = Path(output_path).parent   # FFmpeg will run from here
    ass_fname  = "subs.ass"                 # just the filename — no path needed
    ass_path   = work_dir / ass_fname

    # ── Write ASS subtitle file ───────────────────────────────────────
    if show_captions and sentences:
        font_name  = _find_font_name()
        _write_ass(sentences, duration, ass_path, font_name=font_name,
                   style_id=caption_style, placement_id=caption_placement)
        # Use ONLY the bare filename — FFmpeg's cwd will be work_dir
        ass_filter = "ass=" + ass_fname
    else:
        ass_filter = ""

    use_pexels = bool(bg_path and Path(bg_path).exists())

    if use_pexels:
        # ── YouTube Shorts style ──────────────────────────────────────
        # 1. Fill frame: scale + crop to exactly 1080×1920 (no black bars)
        # 2. Slight brightness drop so white captions stay readable
        # 3. Burn captions with libass
        scale_crop = (
            "scale={W}:{H}:force_original_aspect_ratio=increase,"
            "crop={W}:{H}"
        ).format(W=VIDEO_WIDTH, H=VIDEO_HEIGHT)
        eq_filter  = "eq=brightness=-0.06:saturation=1.1"
        vf_parts   = [scale_crop, eq_filter]
        if ass_filter:
            vf_parts.append(ass_filter)

        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(bg_path),       # absolute path — fine on -i flag
            "-i", str(audio_path),
            "-vf", ",".join(vf_parts),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(duration), "-shortest",
            "-movflags", "+faststart",
            str(output_path),          # absolute path — fine as output arg
        ]
    else:
        # ── Gradient PNG fallback ─────────────────────────────────────
        grad_path = work_dir / "grad.png"
        _make_gradient_png(VIDEO_WIDTH, VIDEO_HEIGHT, colors, grad_path)
        vf_parts = []
        if ass_filter:
            vf_parts.append(ass_filter)
        vf_str = ",".join(vf_parts) if vf_parts else "null"

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-framerate", str(FPS),
            "-i", str(grad_path),
            "-i", str(audio_path),
            "-vf", vf_str,
            "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
            "-crf", "22", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(duration), "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ]

    print("  FFmpeg: {} | captions={}".format(
        "Pexels" if use_pexels else "gradient",
        "on" if show_captions else "off"
    ))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
        cwd=str(work_dir),   # ← THIS is the key fix: FFmpeg finds subs.ass here
    )
    if result.returncode != 0:
        raise RuntimeError("FFmpeg failed:\n" + result.stderr[-3000:])

# ═══════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════

@app.get("/")
async def serve_ui():
    html_file = STATIC_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(404, "static/index.html not found. Please create it.")
    return FileResponse(str(html_file))

@app.get("/voices")
async def get_voices():
    return {"voices": VOICES}

@app.get("/moods")
async def get_moods():
    return {"moods": [{"id":k,"label":v["label"]} for k,v in MOODS.items()]}

@app.get("/caption-styles")
async def get_caption_styles():
    return {"styles": [
        {"id": k, "label": v["label"], "desc": v["desc"]}
        for k, v in CAPTION_STYLES.items()
    ]}

@app.get("/caption-placements")
async def get_caption_placements():
    return {"placements": [
        {"id": k, "label": v["label"]}
        for k, v in CAPTION_PLACEMENTS.items()
    ]}

@app.post("/voice-preview")
async def voice_preview(req: VoicePreviewRequest):
    valid = {v["id"] for v in VOICES}
    if req.voice_id not in valid:
        raise HTTPException(400, f"Unknown voice: {req.voice_id}")
    text = VOICE_PREVIEW_TEXT.get(req.lang, VOICE_PREVIEW_TEXT["en"])
    preview_dir = OUTPUT_DIR / "previews"
    preview_dir.mkdir(exist_ok=True)
    # Use voice_id as filename key (safe chars only)
    safe_id = req.voice_id.replace("-", "_")
    out = preview_dir / f"preview_{safe_id}.mp3"
    try:
        await make_audio(text, req.voice_id, out)
    except Exception as e:
        raise HTTPException(500, f"Preview failed: {e}")
    if not out.exists():
        raise HTTPException(500, "Preview audio not created.")
    return FileResponse(str(out), media_type="audio/mpeg", filename="preview.mp3",
                        headers={"Cache-Control": "no-cache"})

@app.post("/api/generate-script")
async def api_generate_script(req: ScriptRequest):
    if not req.topic or len(req.topic.strip()) < 3:
        raise HTTPException(400, "Topic is too short.")
    use_claude = ANTHROPIC_API_KEY and ANTHROPIC_API_KEY != "your-anthropic-key-here"
    if use_claude:
        try:
            sentences = await generate_script_claude(req.topic, req.mood, req.length_seconds, req.language)
            return {"status":"success","script":sentences,"source":"claude-ai"}
        except Exception as e:
            print(f"Claude fallback: {e}")
    sentences = fallback_script(req.topic, req.mood, req.length_seconds)
    return {"status":"success","script":sentences,"source":"template"}

@app.post("/generate", response_model=GenerateResponse)
async def generate_video(req: GenerateRequest):
    if not req.script or len(req.script) < 2:
        raise HTTPException(400, "Script needs at least 2 lines.")
    ok_ff,ok_fp = check_ffmpeg()
    if not ok_ff: raise HTTPException(503,"FFmpeg not found. Install from https://ffmpeg.org")
    if not ok_fp: raise HTTPException(503,"FFprobe not found. Ensure FFmpeg/bin is in PATH.")

    length = max(10, min(65, req.length_seconds))
    ts = int(time.time()*1000)
    wdir = OUTPUT_DIR / str(ts)
    wdir.mkdir(parents=True, exist_ok=True)
    audio_path = wdir/"voice.mp3"; bg_path=wdir/"bg.mp4"; video_path=wdir/"shorts.mp4"

    valid = {v["id"] for v in VOICES}
    voice = req.voice if req.voice in valid else "en-US-1"
    full_text = " ".join(str(s) for s in req.script)

    print(f"\n🎙  Voice: {voice}")
    try:
        await make_audio(full_text, voice, audio_path)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(500, f"Voice generation failed: {e}. Check internet connection.")

    if not audio_path.exists() or audio_path.stat().st_size < 500:
        raise HTTPException(500,"Audio file not created.")

    try: duration = get_audio_duration(audio_path)
    except Exception: duration = max(len(req.script)*2.2, float(length))
    duration = max(duration, float(length)*0.8)
    print(f"⏱  {duration:.1f}s")

    mood_query = MOODS.get(req.mood, MOODS["motivational"])["query"]
    topic_str  = req.topic.strip() if req.topic else " ".join(str(s) for s in req.script[:2])
    print(f"🔎  Topic: '{topic_str[:60]}'")
    has_bg = await download_pexels(topic_str, mood_query, bg_path)
    print(f"🎬  bg: {'Pexels ✅' if has_bg else 'gradient (Pexels unavailable)'}")

    print("🚀  Rendering with FFmpeg…")
    try:
        loop = asyncio.get_event_loop()
        fn = functools.partial(
            build_video, req.script, audio_path, video_path,
            duration, req.mood, req.show_captions,
            bg_path if has_bg else None,
            req.caption_style, req.caption_placement,
        )
        await loop.run_in_executor(None, fn)  # runs sync FFmpeg in thread, keeps server responsive
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(500, f"Render failed: {e}")

    if not video_path.exists():
        raise HTTPException(500, "Output video not created.")

    size_mb = video_path.stat().st_size / 1_048_576
    bg_src = "Pexels" if has_bg else "gradient"
    print(f"✅  {size_mb:.1f} MB")

    return GenerateResponse(
        status="success",
        video_url=f"/download/{ts}",
        message=f"{duration:.0f}s · {len(req.script)} captions · {size_mb:.1f} MB · {bg_src}",
    )

@app.get("/download/{timestamp}")
async def download_video(timestamp: str):
    vp = OUTPUT_DIR / timestamp / "shorts.mp4"
    if not vp.exists(): raise HTTPException(404,"Video not found.")
    return FileResponse(str(vp), media_type="video/mp4", filename=f"shorts_{timestamp}.mp4")

@app.get("/progress/{timestamp}")
async def render_progress(timestamp: str):
    """Poll this to get real-time render progress."""
    wdir = OUTPUT_DIR / timestamp
    mp4  = wdir / "shorts.mp4"
    audio = wdir / "voice.mp3"
    bg    = wdir / "bg.mp4"
    grad  = wdir / "grad.png"

    if mp4.exists():
        size = mp4.stat().st_size
        return {"step": 4, "label": "Done", "done": True, "size_mb": round(size/1_048_576, 1)}
    if audio.exists() and (bg.exists() or grad.exists()):
        return {"step": 3, "label": "Rendering frames…", "done": False}
    if audio.exists():
        return {"step": 2, "label": "Fetching background…", "done": False}
    if wdir.exists():
        return {"step": 1, "label": "Generating voice…", "done": False}
    return {"step": 0, "label": "Starting…", "done": False}

# ───────────────────────────────────────────────
def cleanup(keep=10):
    dirs = sorted(OUTPUT_DIR.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs[keep:]:
        if d.is_dir(): shutil.rmtree(d, ignore_errors=True)

if __name__ == "__main__":
    cleanup()
    print("\n🎬  AI YouTube Shorts Generator")
    print("═"*46)
    ok_ff,ok_fp = check_ffmpeg()
    print(f"  FFmpeg   : {'✅' if ok_ff else '❌  https://ffmpeg.org'}")
    print(f"  FFprobe  : {'✅' if ok_fp else '❌'}")
    print(f"  Claude   : {'✅ configured' if ANTHROPIC_API_KEY!='your-anthropic-key-here' else '⚠️  Not set — using template scripts'}")
    print(f"  Pexels   : {'✅ configured' if PEXELS_API_KEY!='your-pexels-key-here' else '⚠️  Not set — using gradient backgrounds'}")
    print(f"  Voices   : {len(VOICES)} neural voices")
    print(f"  Output   : {OUTPUT_DIR.absolute()}")
    print(f"\n  → Open   http://127.0.0.1:8000\n")
    if sys.platform == "win32":
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
    else:
        subprocess.run([sys.executable,"-m","gunicorn","main:app",
            "--bind","0.0.0.0:8000","--workers","1",
            "--worker-class","uvicorn.workers.UvicornWorker",
            "--timeout","300","--access-logfile","-","--error-logfile","-",
        ], check=True)
