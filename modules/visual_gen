"""
Visual Generation  —  Pexels API
==================================
v4  Reference-Video Edition

KEY UPGRADES
────────────
• Dark cinematic grade matching reference: brightness=-0.10, saturation=0.72
• Ken Burns zoom on EVERY clip (no static shots) — reference uses zoom always
• Smart clip deduplication: tracks used video IDs across session
• Viral/lifestyle styles get cinematic dark gradient fallbacks
• Pexels portrait-first for Shorts (native vertical content)
• Clip trim: 2–5s segments cut from middle of clip (avoid fade-in/out)
"""

import asyncio, random, logging, re, struct, zlib, subprocess
from pathlib import Path
from typing import Optional, List, Set
import httpx

log = logging.getLogger("ytgen")

# ── Dimensions ───────────────────────────────────────────────────
W,   H,   FPS = 1920, 1080, 30
SV_W, SV_H    = 1080, 1920

# ── Used clip IDs (session-level dedup) ─────────────────────────
_USED_IDS: Set[int] = set()


def reset_used_clips() -> None:
    """Call once per generation run to clear the dedup set."""
    _USED_IDS.clear()


# ════════════════════════════════════════════════════════════════
#  PEXELS HELPERS
# ════════════════════════════════════════════════════════════════

def _best_pexels_file(video: dict, prefer_portrait: bool = False) -> Optional[dict]:
    """
    Pick the best video file from a Pexels video object.
    prefer_portrait → score portrait-oriented files higher.
    """
    files = video.get("video_files", [])
    if not files:
        return None
    # Filter: at least 720p, max 2160p
    pool = [f for f in files if 720 <= f.get("height", 0) <= 2160]
    if not pool:
        pool = files

    if prefer_portrait:
        portrait = [f for f in pool if f.get("width", 9999) <= f.get("height", 0)]
        if portrait:
            portrait.sort(key=lambda f: f.get("height", 0), reverse=True)
            return portrait[0]

    # Landscape: largest file ≤ 1920px tall
    landscape = [f for f in pool if f.get("height", 0) <= 1920]
    if not landscape:
        landscape = pool
    landscape.sort(key=lambda f: f.get("width", 0) * f.get("height", 0), reverse=True)
    return landscape[0] if landscape else None


async def _pexels_search(client: httpx.AsyncClient, query: str,
                          api_key: str, per_page: int = 12,
                          orientation: str = "landscape") -> list:
    try:
        r = await client.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": api_key},
            params={"query": query, "per_page": per_page,
                    "orientation": orientation, "size": "medium"},
            timeout=15,
        )
        if r.status_code == 200:
            videos = r.json().get("videos", [])
            log.info("    Pexels '%s' [%s] → %d results", query, orientation, len(videos))
            return videos
        log.warning("    Pexels HTTP %d for '%s'", r.status_code, query)
    except Exception as e:
        log.warning("    Pexels error '%s': %s", query, e)
    return []


async def _download_url(client: httpx.AsyncClient, url: str, out: Path) -> bool:
    try:
        async with client.stream("GET", url, follow_redirects=True,
                                 timeout=httpx.Timeout(connect=10, read=120,
                                                       write=10, pool=10)) as resp:
            if resp.status_code != 200:
                return False
            with open(out, "wb") as f:
                async for chunk in resp.aiter_bytes(131_072):
                    f.write(chunk)
        size = out.stat().st_size if out.exists() else 0
        if size > 150_000:
            log.info("    Downloaded %.1f MB → %s", size / 1_048_576, out.name)
            return True
        log.warning("    File too small (%d B)", size)
    except Exception as e:
        log.warning("    Download error: %s", e)
    if out.exists():
        out.unlink(missing_ok=True)
    return False


# Stop-words to strip when extracting visual keywords from narration
_STOP = frozenset({
    "a","an","the","and","but","or","so","if","in","on","at","to","for",
    "of","with","by","is","are","was","were","be","been","this","that",
    "it","we","you","i","me","my","your","our","they","them","their",
    "not","no","never","always","here","there","just","then","than",
    "more","most","will","can","do","does","did","have","has","had",
    "how","what","why","when","who","which","all","one","two","three",
    "number","about","from","into","out","up","its","very","also",
    "here","each","every","some","few","many",
})

def _extract_narration_keywords(narration: str, n: int = 3) -> List[str]:
    """Pull the most meaningful nouns/verbs from narration for Pexels search."""
    words = re.sub(r"[^\w\s]", "", narration.lower()).split()
    keywords = [w for w in words
                if len(w) >= 4 and w not in _STOP]
    # De-dup while preserving order
    seen: set = set()
    out: List[str] = []
    for w in keywords:
        if w not in seen:
            seen.add(w)
            out.append(w)
        if len(out) >= n:
            break
    return out


def _build_queries(visual_query: str, topic: str = "",
                   narration: str = "") -> List[str]:
    """
    Build ordered Pexels search query list — most specific first.
    Priority:
      1. Full visual_query (written by Claude / template)
      2. First 4 words of visual_query
      3. Narration keywords (3 top meaningful words)  ← NEW
      4. First 2 words of visual_query
      5. First 3 words of topic
      6. Cinematic fallbacks
    """
    vq    = visual_query.strip()
    words = vq.split()
    q4    = " ".join(words[:4])
    q2    = " ".join(words[:2])
    tw    = " ".join((topic or "").strip().split()[:3])

    # Narration-derived keywords as an extra search angle
    narr_kw = _extract_narration_keywords(narration)
    narr_q  = " ".join(narr_kw) if narr_kw else ""

    qs: List[str] = []
    for q in [vq, q4, narr_q, q2, tw]:
        if q and q not in qs:
            qs.append(q)

    # Reliable cinematic fallbacks
    qs.extend(["aerial drone city night",
               "cinematic ocean waves sunset",
               "nature landscape cinematic outdoor"])
    return list(dict.fromkeys(qs))


# ════════════════════════════════════════════════════════════════
#  PER-SEGMENT CLIP DOWNLOAD
# ════════════════════════════════════════════════════════════════

async def download_segment_clip(segment: dict, idx: int, wdir: Path,
                                pexels_key: str, topic: str = "",
                                shorts_mode: bool = False) -> Optional[Path]:
    if not pexels_key or pexels_key in ("", "your-pexels-key-here"):
        if idx == 0:
            log.warning("  PEXELS_API_KEY not set — gradient fallback.")
            log.warning("  Free key: https://www.pexels.com/api")
        return None

    vq      = str(segment.get("visual_query", "nature landscape")).strip()
    narr    = str(segment.get("narration", ""))
    queries = _build_queries(vq, topic, narration=narr)
    out     = wdir / f"seg_{idx:03d}_clip.mp4"
    prefer_p = shorts_mode   # prefer portrait for Shorts

    log.info("  Seg %d  query: '%s'", idx, vq[:60])

    async with httpx.AsyncClient() as client:
        # For Shorts: try portrait-oriented clips first across ALL queries
        if prefer_p:
            for q in queries:
                videos = await _pexels_search(client, q, pexels_key,
                                              orientation="portrait")
                videos = [v for v in videos if v.get("id") not in _USED_IDS]
                random.shuffle(videos)
                for video in videos[:5]:
                    chosen = _best_pexels_file(video, prefer_portrait=True)
                    if not chosen:
                        continue
                    url = chosen.get("link") or chosen.get("url", "")
                    if url and await _download_url(client, url, out):
                        _USED_IDS.add(video.get("id", 0))
                        log.info("  Seg %d  ✅ portrait via '%s'", idx, q[:40])
                        return out

        # Landscape (primary for standard, fallback for Shorts)
        for q in queries:
            videos = await _pexels_search(client, q, pexels_key,
                                          orientation="landscape")
            videos = [v for v in videos if v.get("id") not in _USED_IDS]
            random.shuffle(videos)
            for video in videos[:6]:
                chosen = _best_pexels_file(video)
                if not chosen:
                    continue
                url = chosen.get("link") or chosen.get("url", "")
                if url and await _download_url(client, url, out):
                    _USED_IDS.add(video.get("id", 0))
                    return out

    log.warning("  Seg %d: no Pexels clip → gradient fallback", idx)
    return None


async def download_all_clips(segments: list, wdir: Path, pexels_key: str,
                              topic: str = "", shorts_mode: bool = False
                              ) -> List[Optional[Path]]:
    """Download clips for all segments concurrently (max 3 parallel)."""
    reset_used_clips()
    sem = asyncio.Semaphore(3)

    async def _guarded(seg, i):
        async with sem:
            return await download_segment_clip(
                seg, i, wdir, pexels_key, topic, shorts_mode)

    results = await asyncio.gather(
        *[_guarded(s, i) for i, s in enumerate(segments)])
    found = sum(1 for r in results if r)
    log.info("  Clips: %d/%d from Pexels", found, len(segments))
    return list(results)


# ════════════════════════════════════════════════════════════════
#  CLIP PROCESSING  —  Reference-video cinematic grade
# ════════════════════════════════════════════════════════════════

# Reference video grade (measured from pixel analysis):
# Slightly darkened, desaturated, high-contrast → feels cinematic
_GRADE_VIRAL  = "eq=brightness=-0.10:contrast=1.08:saturation=0.72"
_GRADE_NORMAL = "eq=brightness=-0.04:contrast=1.06:saturation=1.18"


def _get_grade(style: str) -> str:
    """Dark cinematic grade for viral/lifestyle; standard for others."""
    return _GRADE_VIRAL if style in ("viral", "lifestyle", "motivational") else _GRADE_NORMAL


def get_clip_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, encoding="utf-8", errors="replace")
    try:
        return max(0.5, float(r.stdout.strip()))
    except Exception:
        return 5.0


def _motion_zoom_expr(motion: str, frames: int, out_w: int, out_h: int) -> str:
    """
    Return a zoompan filter expression for the requested motion style.

    motion values:
      zoom_in   — slow push-in  (1.00 → 1.10)
      zoom_out  — slow pull-out (1.10 → 1.00)
      pan_left  — slow rightward pan at 1.06× zoom
      pan_right — slow leftward pan at 1.06× zoom
      pan_up    — slow downward tilt at 1.06× zoom
      pan_down  — slow upward tilt at 1.06× zoom
      hook      — fast zoom-out punch (1.18 → 1.00) for first-clip hook

    All expressions produce smooth, loopable motion with no jumps.
    """
    s = f"{out_w}x{out_h}"
    f = frames

    exprs = {
        "zoom_in":  (f"zoompan=z='min(zoom+0.0007,1.10)':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                     f"d={f}:s={s}:fps={FPS}"),

        "zoom_out": (f"zoompan=z='if(eq(on,1),1.10,max(1.0,zoom-0.0007))':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                     f"d={f}:s={s}:fps={FPS}"),

        "pan_left": (f"zoompan=z=1.06:"
                     f"x='(iw-iw/zoom)*on/{f}':"
                     f"y='ih/2-(ih/zoom/2)':"
                     f"d={f}:s={s}:fps={FPS}"),

        "pan_right":(f"zoompan=z=1.06:"
                     f"x='(iw-iw/zoom)*(1-on/{f})':"
                     f"y='ih/2-(ih/zoom/2)':"
                     f"d={f}:s={s}:fps={FPS}"),

        "pan_up":   (f"zoompan=z=1.06:"
                     f"x='iw/2-(iw/zoom/2)':"
                     f"y='(ih-ih/zoom)*on/{f}':"
                     f"d={f}:s={s}:fps={FPS}"),

        "pan_down": (f"zoompan=z=1.06:"
                     f"x='iw/2-(iw/zoom/2)':"
                     f"y='(ih-ih/zoom)*(1-on/{f})':"
                     f"d={f}:s={s}:fps={FPS}"),

        "hook":     (f"zoompan=z='if(eq(on,1),1.18,max(1.0,1.18-on*0.004))':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                     f"d={f}:s={s}:fps={FPS}"),
    }
    return exprs.get(motion, exprs["zoom_in"])


# Ordered motion cycle — alternates direction so consecutive clips feel dynamic
MOTION_EFFECTS = [
    "zoom_in", "zoom_out", "pan_left", "pan_right",
    "zoom_in", "pan_up",   "zoom_out", "pan_down",
]


def scale_and_crop(src: Path, dst: Path, dur: float,
                   add_kenburns: bool = True,
                   style: str = "educational",
                   motion: str = "zoom_in") -> None:
    """
    Scale & centre-crop to 1920×1080 with cinematic grade.
    motion controls the Ken Burns direction: zoom_in, zoom_out, pan_left, pan_right.
    """
    grade = _get_grade(style)
    scale = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")

    src_dur = get_clip_duration(src)
    ss = min(src_dur * 0.15, 2.0) if src_dur > dur + 1.0 else 0.0

    if add_kenburns:
        frames = max(1, int(dur * FPS))
        zoom_expr = _motion_zoom_expr(motion, frames, W, H)
        vf = f"{scale},{zoom_expr},{grade},format=yuv420p"
    else:
        vf = f"{scale},{grade},format=yuv420p"

    ss_args = ["-ss", f"{ss:.2f}"] if ss > 0 else []
    r = subprocess.run(
        ["ffmpeg", "-y"] + ss_args +
        ["-stream_loop", "-1", "-i", str(src),
         "-vf", vf,
         "-c:v", "libx264", "-preset", "fast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-an", "-t", str(dur), str(dst)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=240)

    if r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000:
        return

    # Fallback: no zoom
    log.warning("  scale_and_crop zoompan failed → plain crop")
    vf2 = f"{scale},{grade},format=yuv420p"
    r2 = subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-vf", vf2, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-an", "-t", str(dur), str(dst)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if r2.returncode != 0:
        raise RuntimeError(f"scale_and_crop failed:\n{r2.stderr[-300:]}")


def scale_and_crop_vertical(src: Path, dst: Path, dur: float,
                             style: str = "educational",
                             motion: str = "zoom_in",
                             hook_mode: bool = False) -> None:
    """
    Convert any clip to 1080×1920 (9:16 Shorts format).

    motion : one of zoom_in | zoom_out | pan_left | pan_right |
                     pan_up | pan_down | hook
             Controls the Ken Burns direction for this clip.
             hook_mode=True is a legacy alias that forces motion='hook'.

    Portrait clips  → scale+crop + zoompan with chosen motion.
    Landscape clips → blurred background + sharp foreground overlay,
                      foreground also gets the chosen motion.
    """
    if hook_mode:          # legacy caller compat
        motion = "hook"

    grade   = _get_grade(style)
    frames  = max(1, int(dur * FPS))

    src_dur = get_clip_duration(src)
    ss      = min(src_dur * 0.15, 2.0) if src_dur > dur + 1.0 else 0.0
    ss_args = ["-ss", f"{ss:.2f}"] if ss > 0 else []

    # ── Detect source orientation ────────────────────────────────
    r_probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(src)],
        capture_output=True, encoding="utf-8", errors="replace")
    try:
        parts    = r_probe.stdout.strip().split(",")
        src_w, src_h = int(parts[0]), int(parts[1])
        is_portrait  = src_h >= src_w
    except Exception:
        is_portrait  = False

    # ── Portrait path — direct scale+crop with motion ────────────
    if is_portrait:
        zoom_filter = _motion_zoom_expr(motion, frames, SV_W, SV_H)
        vf = (f"scale={SV_W}:{SV_H}:force_original_aspect_ratio=increase,"
              f"crop={SV_W}:{SV_H},"
              f"{zoom_filter},"
              f"{grade},format=yuv420p")
        r = subprocess.run(
            ["ffmpeg", "-y"] + ss_args +
            ["-stream_loop", "-1", "-i", str(src),
             "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "21",
             "-pix_fmt", "yuv420p", "-an", "-t", str(dur), str(dst)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=240)
        if r.returncode == 0 and dst.exists() and dst.stat().st_size > 1000:
            log.info("    portrait %s motion=%s", src.name[:30], motion)
            return

    # ── Landscape path — blurred bg + sharp zoomed foreground ────
    # The foreground gets the chosen motion; the bg stays blurred/static.
    # NOTE: filter_complex uses literal pixel values — W/H vars not valid there.
    fg_zoom = _motion_zoom_expr(motion, frames, SV_W, SV_W)   # square fg box
    fc = (
        f"[0:v]"
        f"scale={SV_W}:{SV_H}:force_original_aspect_ratio=increase,"
        f"crop={SV_W}:{SV_H},"
        f"boxblur=luma_radius=20:luma_power=2,"
        f"eq=brightness=-0.18:saturation=0.40,"
        f"format=yuv420p[bg];"

        f"[0:v]"
        f"scale={SV_W}:-2,"
        f"{fg_zoom},"
        f"{grade},format=yuv420p[fg];"

        f"[bg][fg]overlay=x=0:y=({SV_H}-{SV_W})/2,"
        f"crop={SV_W}:{SV_H}:0:0,"
        f"format=yuv420p[out]"
    )
    r2 = subprocess.run(
        ["ffmpeg", "-y"] + ss_args +
        ["-stream_loop", "-1", "-i", str(src),
         "-filter_complex", fc, "-map", "[out]",
         "-c:v", "libx264", "-preset", "fast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-an", "-t", str(dur), str(dst)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=300)

    if r2.returncode == 0 and dst.exists() and dst.stat().st_size > 1000:
        log.info("    landscape+blur %s motion=%s", src.name[:30], motion)
        return

    # ── Final fallback — plain crop, no zoom ─────────────────────
    log.warning("  scale_and_crop_vertical blur failed → simple crop")
    vf_fb = (f"scale={SV_W}:{SV_H}:force_original_aspect_ratio=increase,"
             f"crop={SV_W}:{SV_H},{grade},format=yuv420p")
    r3 = subprocess.run(
        ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src),
         "-vf", vf_fb, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
         "-pix_fmt", "yuv420p", "-an", "-t", str(dur), str(dst)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if r3.returncode != 0:
        raise RuntimeError(f"scale_and_crop_vertical failed:\n{r3.stderr[-300:]}")


# ════════════════════════════════════════════════════════════════
#  MOTION EFFECTS  (post-processing pass — motion is normally baked
#  into scale_and_crop, but this is kept for optional extra passes)
# ════════════════════════════════════════════════════════════════


def apply_motion_effect(src: Path, dst: Path, dur: float,
                        motion: str, shorts_mode: bool = False) -> None:
    """
    Apply slow zoom/pan to an already-processed clip.
    Uses the same _motion_zoom_expr as scale_and_crop so motion types are consistent.
    Called when extra post-processing motion is needed (rare — motion is normally
    baked into scale_and_crop directly).
    """
    out_w  = SV_W if shorts_mode else W
    out_h  = SV_H if shorts_mode else H
    frames = max(1, int(dur * FPS))

    if not motion or motion == "static":
        if src != dst:
            import shutil as _sh
            _sh.copy2(src, dst)
        return

    zp = _motion_zoom_expr(motion, frames, out_w, out_h)

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src),
         "-vf", f"{zp},format=yuv420p",
         "-c:v", "libx264", "-preset", "fast", "-crf", "21",
         "-pix_fmt", "yuv420p", "-an", "-t", str(dur), str(dst)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=180)

    if r.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
        log.warning("  apply_motion_effect %s failed → copy", motion)
        import shutil as _sh
        _sh.copy2(src, dst)


# ════════════════════════════════════════════════════════════════
#  GRADIENT FALLBACK  (dark cinematic, matches reference style)
# ════════════════════════════════════════════════════════════════

def build_gradient_clip(color_pair: tuple, dur: float, dst: Path,
                        shorts_mode: bool = False) -> None:
    c0, c1 = color_pair
    tw = SV_W if shorts_mode else W
    th = SV_H if shorts_mode else H

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFF_FFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    PW, PH = 2, 128
    rows = []
    for row in range(PH):
        t  = row / max(PH - 1, 1)
        rows.append(b"\x00" + bytes([
            int(c0[0] + (c1[0]-c0[0])*t),
            int(c0[1] + (c1[1]-c0[1])*t),
            int(c0[2] + (c1[2]-c0[2])*t),
        ] * PW))

    raw  = b"".join(rows)
    comp = zlib.compress(raw, 9)
    png  = (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", struct.pack(">IIBBBBB", PW, PH, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", comp)
            + _chunk(b"IEND", b""))

    png_path = dst.parent / f"_grad_{dst.stem}.png"
    png_path.write_bytes(png)

    r = subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(png_path),
         "-vf", f"scale={tw}:{th}:flags=bilinear,format=yuv420p",
         "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage",
         "-crf", "23", "-an", "-t", str(dur), str(dst)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    png_path.unlink(missing_ok=True)

    if r.returncode != 0:
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", f"color=c=0x0d0d0d:size={tw}x{th}:rate={FPS}",
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
             "-an", "-t", str(dur), str(dst)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=20)


# ── Style → gradient colour palette ──────────────────────────────
# viral/lifestyle: very dark, almost black — matches reference video dark B-roll
STYLE_COLORS = {
    "viral":       ((4,  4,  8),   (18, 16, 28)),   # near-black dark purple
    "lifestyle":   ((6,  6,  12),  (22, 18, 32)),   # dark cool night
    "educational": ((8,  18, 55),  (25, 55, 115)),
    "documentary": ((12, 10, 6),   (40, 30, 16)),
    "motivational":((55, 6,  0),   (120, 28, 0)),
    "news":        ((6,  6,  16),  (18, 18, 48)),
}
