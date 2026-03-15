"""
AI Viral Shorts Studio  —  v6
==============================
Gemini + Groq Edition  (no Claude dependency)

AI scripts : Gemini (gemini-1.5-flash)  →  Groq (llama-3.3-70b)  →  local template
Voice      : gTTS (Google TTS — free, no API key)
Video bg   : Pexels API (free)
Music      : FFmpeg synthesiser (no API key)

Run:  python main.py
Open: http://127.0.0.1:8000
"""

import os, sys, shutil, asyncio, functools, traceback, logging, time, subprocess
from pathlib import Path

SV_W, SV_H = 1080, 1920   # Shorts vertical dimensions

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

from modules.script_gen    import generate_script, VIDEO_STYLES
from modules.voice_gen     import (generate_all, synthesize, get_duration,
                                    VOICES, VOICE_SPEEDS, _get_preview_text)
from modules.visual_gen    import (download_all_clips,
                                    scale_and_crop, scale_and_crop_vertical,
                                    build_gradient_clip, STYLE_COLORS,
                                    MOTION_EFFECTS)
from modules.music_gen     import get_music
from modules.video_builder import (write_subtitles, make_title_card,
                                    make_outro_card, concat_video_segments,
                                    assemble,
                                    CAPTION_POSITIONS, CAPTION_STYLES)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ytgen")


# ─── Config ───────────────────────────────────────────────────────

_ENV_PATH = Path(__file__).parent / ".env"

try:
    from dotenv import load_dotenv
    if _ENV_PATH.exists():
        load_dotenv(dotenv_path=_ENV_PATH, override=False)
        log.info(".env loaded via python-dotenv")
    else:
        log.warning(".env not found at %s — copy .env.example and fill in keys.", _ENV_PATH)
except ImportError:
    log.warning("python-dotenv not installed. Using built-in parser.")
    if _ENV_PATH.exists():
        for _line in _ENV_PATH.read_text(encoding="utf-8-sig").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            if _line.lower().startswith("export "):
                _line = _line[7:].strip()
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            _v = _v.split(" #")[0].split("\t#")[0].strip().strip('"').strip("'")
            if _k and _k not in os.environ:
                os.environ[_k] = _v

_PLACEHOLDER_GEMINI  = "your-gemini-key-here"
_PLACEHOLDER_GROQ    = "your-groq-key-here"
_PLACEHOLDER_PEXELS  = "your-pexels-key-here"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", _PLACEHOLDER_GEMINI).strip()
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY",   _PLACEHOLDER_GROQ).strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY",  _PLACEHOLDER_PEXELS).strip()


def _key_configured(key: str, placeholder: str) -> bool:
    return bool(key and key not in (placeholder, "", "your-key-here")
                and not key.startswith("your-"))


if _key_configured(GEMINI_API_KEY, _PLACEHOLDER_GEMINI):
    log.info("Gemini  API key: configured (gemini-1.5-flash — free tier)")
else:
    log.info("Gemini  API key: not set  (add GEMINI_API_KEY to .env — free)")

if _key_configured(GROQ_API_KEY, _PLACEHOLDER_GROQ):
    log.info("Groq    API key: configured (llama-3.3-70b — free tier)")
else:
    log.info("Groq    API key: not set  (add GROQ_API_KEY to .env — free)")

BASE_DIR   = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
MUSIC_DIR  = BASE_DIR / "music"
for _d in (OUTPUT_DIR, STATIC_DIR, MUSIC_DIR):
    _d.mkdir(exist_ok=True)


# ─── Styles that use hard-cut (no xfade) + viral caption defaults ──
_HARD_CUT_STYLES = {"viral", "lifestyle", "motivational"}
_VIRAL_CAP_DEFAULTS = {
    "viral":     ("viral_center", "viral"),
    "lifestyle": ("viral_center", "viral"),
}


# ─── App ──────────────────────────────────────────────────────────

app = FastAPI(title="AI Viral Shorts Studio v6")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ─── Pydantic models ──────────────────────────────────────────────

class ScriptRequest(BaseModel):
    topic:        str
    style:        str = "viral"
    duration_sec: int = 60
    shorts_mode:  bool = True

class PreviewRequest(BaseModel):
    voice_id: str

class GenerateRequest(BaseModel):
    topic:        str
    script:       dict
    voice_id:     str   = "en-us"
    style:        str   = "viral"
    music_volume: float = 0.22

    voice_speed:  float = 1.0
    cap_position: str   = "viral_center"
    cap_style:    str   = "viral"
    # Accept both "custom_cap_x" (legacy) and "custom_x" (new HTML) for XY coords
    custom_cap_x: int   = 960
    custom_cap_y: int   = 900
    custom_x:     int   = -1   # if set (≥0) overrides custom_cap_x
    custom_y:     int   = -1   # if set (≥0) overrides custom_cap_y

    show_subs:    bool  = True
    add_intro:    bool  = False
    add_outro:    bool  = False
    shorts_mode:  bool  = True

    def resolved_x(self) -> int:
        return self.custom_x if self.custom_x >= 0 else self.custom_cap_x

    def resolved_y(self) -> int:
        return self.custom_y if self.custom_y >= 0 else self.custom_cap_y

class GenerateResponse(BaseModel):
    status:    str
    video_url: str = ""
    title:     str = ""
    message:   str = ""


# ─── Helpers ──────────────────────────────────────────────────────

def _ffmpeg_ok() -> tuple:
    return shutil.which("ffmpeg") is not None, shutil.which("ffprobe") is not None


def _cleanup(keep: int = 10) -> None:
    dirs = sorted(OUTPUT_DIR.glob("*"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    for d in dirs[keep:]:
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)


def _clamp_speed(v: float) -> float:
    return max(0.25, min(4.0, v))

def _clamp_pos(pos: str) -> str:
    return pos if pos in CAPTION_POSITIONS else "bottom"

def _clamp_style(sty: str) -> str:
    return sty if sty in CAPTION_STYLES else "standard"


# ─── Static routes ────────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    f = STATIC_DIR / "index.html"
    if not f.exists():
        raise HTTPException(404, "static/index.html not found")
    return FileResponse(str(f))


# ─── Catalogue endpoints ──────────────────────────────────────────

@app.get("/api/voices")
async def api_voices():
    return {"voices": VOICES}


@app.get("/api/styles")
async def api_styles():
    return {"styles": [{"id": k, "label": v["label"]}
                        for k, v in VIDEO_STYLES.items()]}


@app.get("/api/voice-speeds")
async def api_voice_speeds():
    return {"speeds": [{"id": k, "label": v["label"], "value": v["value"]}
                        for k, v in VOICE_SPEEDS.items()]}


@app.get("/api/caption-positions")
async def api_caption_positions():
    return {"positions": [{"id": k, "label": v["label"], "desc": v["desc"]}
                           for k, v in CAPTION_POSITIONS.items()]}


@app.get("/api/caption-styles")
async def api_caption_styles():
    return {"styles": [{"id": k, "label": v["label"],
                         "desc": v["desc"], "emoji": v["emoji"]}
                        for k, v in CAPTION_STYLES.items()]}


# ─── Voice preview ────────────────────────────────────────────────

@app.post("/api/preview-voice")
async def api_preview_voice(req: PreviewRequest):
    valid = {v["id"] for v in VOICES}
    if req.voice_id not in valid:
        raise HTTPException(400, f"Unknown voice: {req.voice_id}")
    text    = _get_preview_text(req.voice_id)
    out_dir = OUTPUT_DIR / "previews"
    out_dir.mkdir(exist_ok=True)
    safe    = "".join(c if c.isalnum() else "_" for c in req.voice_id)
    out     = out_dir / f"prev_{safe}.mp3"
    try:
        await synthesize(text, req.voice_id, out)
    except Exception as e:
        raise HTTPException(500, f"Preview failed: {e}")
    if not out.exists():
        raise HTTPException(500, "Preview not created")
    return FileResponse(str(out), media_type="audio/mpeg",
                        headers={"Cache-Control": "no-cache"})


# ─── Script generation ────────────────────────────────────────────

@app.post("/api/script")
async def api_script(req: ScriptRequest):
    if not req.topic or len(req.topic.strip()) < 3:
        raise HTTPException(400, "Topic too short.")
    dur = max(30, min(180, req.duration_sec))
    try:
        script = await generate_script(
            req.topic.strip(), req.style, dur,
            gemini_key  = GEMINI_API_KEY,
            groq_key    = GROQ_API_KEY,
            shorts_mode = req.shorts_mode,
        )
        source = script.get("_source", "local_template")
        return {"status": "ok", "script": script, "source": source,
                "shorts_mode": req.shorts_mode}
    except Exception as e:
        log.error("Script error: %s", e)
        raise HTTPException(500, f"Script generation failed: {e}")


# ─── Main generation pipeline ─────────────────────────────────────

@app.post("/api/generate", response_model=GenerateResponse)
async def api_generate(req: GenerateRequest):
    if not req.topic or not req.script:
        raise HTTPException(400, "topic and script required.")

    ok_ff, ok_fp = _ffmpeg_ok()
    if not ok_ff:
        raise HTTPException(503, "FFmpeg not found. Install: https://ffmpeg.org")
    if not ok_fp:
        raise HTTPException(503, "FFprobe not found (included with FFmpeg).")

    segments = req.script.get("segments", [])
    if len(segments) < 2:
        raise HTTPException(400, "Need at least 2 segments.")

    # Sanitise inputs
    voice_speed  = _clamp_speed(req.voice_speed)
    shorts       = req.shorts_mode
    style        = req.style

    # Auto-apply viral defaults: viral_center position + viral caption style
    if style in _VIRAL_CAP_DEFAULTS:
        default_pos, default_cs = _VIRAL_CAP_DEFAULTS[style]
        cap_position = req.cap_position if req.cap_position not in ("bottom", "standard") \
                       else default_pos
        cap_style = req.cap_style if req.cap_style not in ("standard",) \
                    else default_cs
    else:
        cap_position = _clamp_pos(req.cap_position)
        cap_style    = _clamp_style(req.cap_style)
        # Shorts default
        if shorts and cap_style == "standard":
            cap_style = "shorts"

    custom_x = max(0, min(SV_W if shorts else 1920, req.resolved_x()))
    custom_y = max(0, min(SV_H if shorts else 1080, req.resolved_y()))

    # Hard-cut mode for viral/lifestyle — matches reference video
    hard_cut = style in _HARD_CUT_STYLES

    ts   = int(time.time() * 1000)
    wdir = OUTPUT_DIR / str(ts)
    wdir.mkdir(parents=True, exist_ok=True)

    valid_voices = {v["id"] for v in VOICES}
    voice_id     = req.voice_id if req.voice_id in valid_voices else "en-us"
    title        = req.script.get("title", req.topic)

    log.info("=" * 55)
    log.info("Topic       : %s", req.topic[:60])
    log.info("Segs        : %d | Voice: %s | Style: %s",
             len(segments), voice_id, style)
    log.info("Shorts mode : %s | Hard cut: %s", shorts, hard_cut)
    log.info("Speed: %.2fx | Cap: %s / %s", voice_speed, cap_position, cap_style)

    try:
        # ── Step 1: Voice synthesis ──────────────────────────────
        log.info("Step 1/5: Voice synthesis (speed=%.2fx)", voice_speed)
        audio_path, timestamps = await generate_all(
            segments, voice_id, wdir, voice_speed=voice_speed)
        total_dur = get_duration(audio_path)
        log.info("  Audio: %.1fs", total_dur)

        # ── Step 2: Download Pexels clips ────────────────────────
        log.info("Step 2/5: Fetching Pexels clips (%d segments)", len(segments))
        clip_paths = await download_all_clips(
            segments, wdir, PEXELS_API_KEY, req.topic, shorts_mode=shorts)

        # ── Step 3: Process clips ─────────────────────────────────
        # Each narration segment maps to ONE processed clip.
        # Motion cycles through MOTION_EFFECTS deterministically so every
        # consecutive clip gets a different camera direction — no random repeats.
        # First clip always uses 'hook' (fast punch zoom-out) for max impact.
        # If segment duration > 4s, the zoomed clip loops to fill the full length.
        log.info("Step 3/5: Processing clips (shorts=%s  style=%s)", shorts, style)
        processed = []
        colors    = STYLE_COLORS.get(style, STYLE_COLORS.get("educational",
                                                              ((8, 18, 55), (25, 55, 115))))

        # Render motion over at most 4s — keeps energy tight even on long narrations
        CLIP_RENDER_CAP = 4.0

        for i, seg in enumerate(segments):
            t0, t1  = timestamps[i]
            seg_dur = max(1.5, t1 - t0)
            raw     = clip_paths[i]
            proc    = wdir / f"seg_{i:03d}_proc.mp4"

            # First clip: hook punch.  Remaining: deterministic cycle so
            # zoom_in / zoom_out / pan_left / pan_right / … never repeat back-to-back.
            if i == 0:
                motion = "hook"
            else:
                motion = MOTION_EFFECTS[((i - 1) % len(MOTION_EFFECTS))]

            render_dur = min(seg_dur, CLIP_RENDER_CAP)

            if raw and raw.exists() and raw.stat().st_size > 50_000:
                try:
                    if shorts:
                        scale_and_crop_vertical(raw, proc, render_dur,
                                                style=style, motion=motion)
                    else:
                        scale_and_crop(raw, proc, render_dur,
                                       add_kenburns=True, style=style,
                                       motion=motion)
                    log.info("  Seg %d: Pexels %.1fs (render %.1fs) [%s] '%s'",
                             i, seg_dur, render_dur, motion,
                             seg.get("visual_query", "")[:35])
                except Exception as e:
                    log.warning("  Seg %d clip error: %s → gradient", i, e)
                    raw = None

            if not (raw and proc.exists() and proc.stat().st_size > 1000):
                build_gradient_clip(colors, render_dur, proc, shorts_mode=shorts)
                log.info("  Seg %d: gradient  %.1fs [%s]", i, render_dur, motion)

            # Loop processed clip to fill full segment duration if narration is longer
            if seg_dur > render_dur + 0.5:
                looped = wdir / f"seg_{i:03d}_loop.mp4"
                ow = SV_W if shorts else 1920
                oh = SV_H if shorts else 1080
                r_loop = subprocess.run(
                    ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(proc),
                     "-vf", f"scale={ow}:{oh}:flags=bilinear,format=yuv420p",
                     "-c:v", "libx264", "-preset", "fast", "-crf", "21",
                     "-an", "-t", str(seg_dur), str(looped)],
                    capture_output=True, encoding="utf-8", errors="replace", timeout=120)
                if r_loop.returncode == 0 and looped.exists() and looped.stat().st_size > 1000:
                    proc = looped

            processed.append(proc)

        # ── Step 4: Cards + concat ───────────────────────────────
        all_clips    = []
        intro_offset = 0.0

        if req.add_intro:
            tc = wdir / "title_card.mp4"
            make_title_card(title, style, 2.0, tc, shorts_mode=shorts)
            all_clips.append(tc)
            intro_offset = 2.0

        all_clips.extend(processed)

        if req.add_outro:
            oc = wdir / "outro_card.mp4"
            make_outro_card(style, 2.0, oc, shorts_mode=shorts)
            all_clips.append(oc)
            total_dur += 2.0

        total_dur  += intro_offset
        timestamps  = [(t0 + intro_offset, t1 + intro_offset)
                       for t0, t1 in timestamps]

        # xfade duration: 0 for hard-cut, 0.20s for Shorts, 0.40s standard
        xfade = 0.0 if hard_cut else (0.20 if shorts else 0.40)

        log.info("Step 4/5: Concat %d clips  hard_cut=%s  xfade=%.2fs",
                 len(all_clips), hard_cut, xfade)
        video_track = wdir / "video_track.mp4"
        concat_video_segments(all_clips, video_track, wdir,
                               xfade_dur=xfade,
                               shorts_mode=shorts,
                               hard_cut=hard_cut)

        # ── Subtitles ─────────────────────────────────────────────
        subs_path = None
        if req.show_subs:
            subs_path = wdir / "subs.ass"
            write_subtitles(
                segments, timestamps, total_dur, subs_path,
                video_style  = style,
                cap_position = cap_position,
                cap_style    = cap_style,
                custom_x     = custom_x,
                custom_y     = custom_y,
                shorts_mode  = shorts,
            )

        # ── Music ──────────────────────────────────────────────────
        music_path = None
        if req.music_volume > 0:
            music_path = get_music(style, total_dur, MUSIC_DIR, wdir)

        # ── Final assembly ─────────────────────────────────────────
        mode_label = "Shorts 1080×1920" if shorts else "YouTube 1920×1080"
        log.info("Step 5/5: Final assembly (%s)", mode_label)
        final_out = wdir / "final.mp4"
        fn = functools.partial(
            assemble,
            video_track, audio_path, subs_path,
            music_path, req.music_volume, total_dur,
            final_out, wdir,
            cap_position, cap_style, custom_x, custom_y, shorts,
        )
        await asyncio.get_event_loop().run_in_executor(None, fn)

        if not final_out.exists():
            raise RuntimeError("final.mp4 was not created")

        size_mb   = final_out.stat().st_size / 1_048_576
        pexels_ct = sum(1 for p in clip_paths if p)
        cut_type  = "hard-cut" if hard_cut else f"xfade-{xfade:.2f}s"
        log.info("Done: %.1f MB  %.1fs  %d/%d Pexels  %s  %s",
                 size_mb, total_dur, pexels_ct, len(segments), mode_label, cut_type)

        return GenerateResponse(
            status    = "success",
            video_url = f"/api/download/{ts}",
            title     = title,
            message   = (
                f"{'📱 Shorts' if shorts else '🎬 YouTube'}  "
                f"{total_dur:.0f}s · {len(segments)} segments · "
                f"{size_mb:.1f} MB · "
                f"{pexels_ct}/{len(segments)} Pexels · "
                f"speed {voice_speed:.2f}x · "
                f"{cap_style}/{cap_position} · {cut_type}"
            ),
        )

    except Exception as e:
        log.error("Generation failed:\n%s", traceback.format_exc())
        raise HTTPException(500, f"Generation failed: {e}")


# ─── Download + progress ──────────────────────────────────────────

@app.get("/api/download/{ts}")
async def api_download(ts: str):
    p = OUTPUT_DIR / ts / "final.mp4"
    if not p.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(str(p), media_type="video/mp4",
                        filename=f"shorts_{ts}.mp4")


@app.get("/api/progress/{ts}")
async def api_progress(ts: str):
    wdir  = OUTPUT_DIR / ts
    final = wdir / "final.mp4"
    vt    = wdir / "video_track.mp4"
    audio = wdir / "full_voice.mp3"
    clips = list(wdir.glob("seg_*_clip.mp4")) if wdir.exists() else []

    if final.exists():
        return {"step": 5, "label": "Done ✅",
                "done": True,
                "size_mb": round(final.stat().st_size / 1_048_576, 1)}
    if vt.exists():
        return {"step": 4, "label": "Final assembly…", "done": False}
    if clips:
        return {"step": 3, "label": f"Processing {len(clips)} clips…", "done": False}
    if audio.exists():
        return {"step": 2, "label": "Downloading Pexels clips…", "done": False}
    if wdir.exists():
        return {"step": 1, "label": "Generating narration…", "done": False}
    return {"step": 0, "label": "Starting…", "done": False}


# ─── Startup ──────────────────────────────────────────────────────

if __name__ == "__main__":
    _cleanup()
    ok_ff, ok_fp = _ffmpeg_ok()
    has_pexels   = _key_configured(PEXELS_API_KEY, _PLACEHOLDER_PEXELS)
    has_gemini   = _key_configured(GEMINI_API_KEY, _PLACEHOLDER_GEMINI)
    has_groq     = _key_configured(GROQ_API_KEY,   _PLACEHOLDER_GROQ)
    ai_count     = sum([has_gemini, has_groq])

    print("\n  ┌──────────────────────────────────────────────┐")
    print("  │   YouTube / Shorts Video Generator  v6      │")
    print("  │   Gemini + Groq Edition                      │")
    print("  └──────────────────────────────────────────────┘")
    print()
    print(f"  FFmpeg   : {'✅ Ready' if ok_ff else '❌ MISSING — https://ffmpeg.org'}")
    print(f"  FFprobe  : {'✅ Ready' if ok_fp else '❌ MISSING'}")
    print()

    print(f"  ── AI Script Providers ({ai_count}/2 active) ──")
    if has_gemini:
        print(f"  Gemini   : ✅  configured  (gemini-1.5-flash — free tier)")
    else:
        print(f"  Gemini   : –   Not set  →  GEMINI_API_KEY in .env")
        print(f"             aistudio.google.com/app/apikey  (FREE, 1500/day)")

    if has_groq:
        print(f"  Groq     : ✅  configured  (llama-3.3-70b — free tier)")
    else:
        print(f"  Groq     : –   Not set  →  GROQ_API_KEY in .env")
        print(f"             console.groq.com  (FREE, 14 400/day)")

    if ai_count == 0:
        print()
        print(f"  ⚠️  No AI keys — using local template scripts.")
        print(f"     Add GEMINI_API_KEY for free AI-generated scripts.")

    print()
    if has_pexels:
        print(f"  Pexels   : ✅  Configured")
    else:
        print(f"  Pexels   : ⚠️  Not set — gradient backgrounds")
        print(f"             → Free key: https://www.pexels.com/api")
    print()
    print(f"  Styles    : {len(VIDEO_STYLES)} (viral, lifestyle, educational, documentary, motivational, news)")
    print(f"  Voices    : {len(VOICES)} across 14 languages | Speeds: {len(VOICE_SPEEDS)}")
    print(f"  Cap styles: {len(CAPTION_STYLES)} (viral, standard, bold, highlighted, box, shorts, cinematic, mrbeast)")
    print(f"  Cap pos   : {len(CAPTION_POSITIONS)} (bottom, top, center, viral_center, lower_third, upper_third, custom)")
    print(f"  Output    : {OUTPUT_DIR.absolute()}")
    print(f"\n  ➜  Open http://127.0.0.1:8000\n")

    if not ok_ff:
        sys.exit(1)

    import threading, webbrowser
    threading.Thread(
        target=lambda: (time.sleep(1.2), webbrowser.open("http://127.0.0.1:8000")),
        daemon=True,
    ).start()

    uvicorn.run("main:app", host="127.0.0.1", port=8000,
                reload=False, log_level="warning")
