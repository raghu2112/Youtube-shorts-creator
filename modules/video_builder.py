"""
Video Assembly  —  Pure FFmpeg Pipeline
========================================
v4  Reference-Video Edition

NEW IN THIS VERSION
────────────────────
"viral"   caption style — pixel-matched to reference video:
  • Bold white text, ~66px, thick 5px black outline
  • NO background box — pure outline only (matches reference)
  • Position: ~50% vertical = dead center of frame
  • Left-aligned text (ASS alignment=4, pos at ~30% from left)
  • Clean fade animation (no pop/scale)

Hard-cut mode — reference video uses ZERO crossfades (all hard cuts).
  • concat_video_segments() now accepts hard_cut=True
  • Default for viral/lifestyle style

Updated CAPTION_POSITIONS: "viral_center" preset added.
Cinematic color grades delegated to visual_gen.py.
"""

import re, subprocess, os, shutil, logging
from pathlib import Path
from typing import List, Optional, Tuple

log = logging.getLogger("ytgen")

W,  H,  FPS = 1920, 1080, 30
SV_W, SV_H  = 1080, 1920

# ── Font detection ────────────────────────────────────────────────
_FONT_CANDIDATES = [
    ("Arial",           r"C:/Windows/Fonts/arial.ttf"),
    ("Calibri",         r"C:/Windows/Fonts/calibri.ttf"),
    ("Verdana",         r"C:/Windows/Fonts/verdana.ttf"),
    ("Trebuchet MS",    r"C:/Windows/Fonts/trebuc.ttf"),
    ("DejaVu Sans",     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("Liberation Sans", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("Ubuntu",          "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"),
    ("Noto Sans",       "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("Arial",           "/Library/Fonts/Arial.ttf"),
    ("Helvetica Neue",  "/System/Library/Fonts/HelveticaNeue.ttc"),
]

def _find_font() -> Tuple[str, str]:
    for name, path in _FONT_CANDIDATES:
        if os.path.exists(path):
            return name, path
    return "Arial", ""

_FONT_NAME, _FONT_PATH = _find_font()


# ══════════════════════════════════════════════════════════════════
#  CAPTION POSITIONS
# ══════════════════════════════════════════════════════════════════
#
#  ASS numpad alignment:
#    7 8 9  →  top-left / top-center / top-right
#    4 5 6  →  mid-left / center     / mid-right
#    1 2 3  →  bot-left / bottom     / bot-right
#
#  "viral_center" pos_tag: uses inline \pos(x,y) at exact 50% vertical,
#  left-aligned — matches the reference video exactly.

CAPTION_POSITIONS = {
    "bottom": {
        "label":          "⬇ Bottom",
        "desc":           "Standard — above platform UI chrome",
        "alignment":      2,   # bottom-center
        "margin_v":       90,
        "margin_v_shorts":280,  # 14.6% of 1920 — safely above like/comment UI
        "pos_tag":        None,
    },
    "top": {
        "label":          "⬆ Top",
        "desc":           "Above content area",
        "alignment":      8,
        "margin_v":       60,
        "margin_v_shorts":160,
        "pos_tag":        None,
    },
    "center": {
        "label":          "⏺ Center",
        "desc":           "Cinematic / emphasis",
        "alignment":      5,
        "margin_v":       0,
        "margin_v_shorts":0,
        "pos_tag":        None,
    },
    "viral_center": {
        "label":          "🔥 Viral Center",
        "desc":           "Bold bottom-center — safe above platform UI",
        "alignment":      2,    # bottom-center (was mid-left 4 — caused captions in middle of screen)
        "margin_v":       90,
        "margin_v_shorts":280,  # same safe zone as "bottom"
        "pos_tag":        None,  # no inline \pos() needed
    },
    "lower_third": {
        "label":          "▭ Lower Third",
        "desc":           "News / documentary — 75 % down",
        "alignment":      2,
        "margin_v":       220,
        "margin_v_shorts":480,
        "pos_tag":        None,
    },
    "upper_third": {
        "label":          "▭ Upper Third",
        "desc":           "Header band — 25 % from top",
        "alignment":      8,
        "margin_v":       220,
        "margin_v_shorts":400,
        "pos_tag":        None,
    },
    "custom": {
        "label":          "✎ Custom",
        "desc":           "Enter exact X / Y pixel coordinates",
        "alignment":      5,
        "margin_v":       0,
        "margin_v_shorts":0,
        "pos_tag":        "custom",
    },
}


# ══════════════════════════════════════════════════════════════════
#  CAPTION STYLES
# ══════════════════════════════════════════════════════════════════
#
#  "viral" style — pixel-matched from reference video:
#    • Bold sans-serif, ~66px
#    • White text, thick black outline (5px), no shadow box
#    • border_style=1 (outline+shadow), shadow=2 for depth
#    • NO back_col box (back_col transparent)
#    • Clean fade animation
#
#  ASS colour: &HAABBGGRR  (alpha 00=opaque, FF=transparent)
#    white  = &H00FFFFFF
#    black  = &H00000000
#    yellow = &H0000FFFF

CAPTION_STYLES = {
    # ─── NEW: Viral Reference Style ──────────────────────────────
    "viral": {
        "label":        "🔥 Viral",
        "desc":         "Bold white, thick outline — reference video style",
        "emoji":        "🔥",
        "fontsize":     66,  "fontsize_s": 70,
        "bold":         -1,  "italic": 0,
        "primary":      "&H00FFFFFF",   # white
        "secondary":    "&H00FFFFFF",
        "outline_col":  "&H00000000",   # black outline
        "back_col":     "&H00000000",   # NO box (alpha FF = fully transparent)
        "border_style": 1,              # outline+shadow (NOT opaque box)
        "outline":      5,   "shadow": 2,
        "scale_x":      100, "spacing": 1,
        "animation":    "fade",
        "accent":       "&H00FFFFFF",   # all-white (reference has no color highlights)
    },
    # ─── Standard ────────────────────────────────────────────────
    "standard": {
        "label":        "Standard",
        "desc":         "Clean white with black outline",
        "emoji":        "Aa",
        "fontsize":     52,  "fontsize_s": 58,
        "bold":         0,   "italic": 0,
        "primary":      "&H00FFFFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H00000000",
        "back_col":     "&H00000000",
        "border_style": 1,
        "outline":      2.5, "shadow": 2,
        "scale_x":      100, "spacing": 1,
        "animation":    "fade",
        "accent":       "&H0000FFFF",
    },
    "bold": {
        "label":        "Bold",
        "desc":         "Heavy text — maximum contrast",
        "emoji":        "AB",
        "fontsize":     56,  "fontsize_s": 62,
        "bold":         -1,  "italic": 0,
        "primary":      "&H00FFFFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H00000000",
        "back_col":     "&H00000000",
        "border_style": 1,
        "outline":      4,   "shadow": 3,
        "scale_x":      100, "spacing": 0,
        "animation":    "fade",
        "accent":       "&H0000FFFF",
    },
    "highlighted": {
        "label":        "Highlighted",
        "desc":         "Yellow text — keyword focus",
        "emoji":        "✦",
        "fontsize":     52,  "fontsize_s": 58,
        "bold":         -1,  "italic": 0,
        "primary":      "&H0000FFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H00000033",
        "back_col":     "&H00000000",
        "border_style": 1,
        "outline":      3,   "shadow": 2,
        "scale_x":      100, "spacing": 1,
        "animation":    "fade",
        "accent":       "&H00FFFFFF",
    },
    "box": {
        "label":        "Box",
        "desc":         "White text on semi-transparent dark box",
        "emoji":        "▬",
        "fontsize":     50,  "fontsize_s": 56,
        "bold":         0,   "italic": 0,
        "primary":      "&H00FFFFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H00000000",
        "back_col":     "&HAA000000",
        "border_style": 4,
        "outline":      2,   "shadow": 0,
        "scale_x":      100, "spacing": 2,
        "animation":    "fade",
        "accent":       "&H0000FFFF",
    },
    "shorts": {
        "label":        "Shorts",
        "desc":         "YouTube Shorts / TikTok — large, bold, pop-in",
        "emoji":        "▶",
        "fontsize":     66,  "fontsize_s": 72,
        "bold":         -1,  "italic": 0,
        "primary":      "&H00FFFFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H00000000",
        "back_col":     "&HC8000000",
        "border_style": 4,
        "outline":      5,   "shadow": 4,
        "scale_x":      105, "spacing": 0,
        "animation":    "popup",
        "accent":       "&H0000FFFF",
    },
    "cinematic": {
        "label":        "Cinematic",
        "desc":         "Minimal, elegant — blur-focus reveal",
        "emoji":        "◈",
        "fontsize":     46,  "fontsize_s": 52,
        "bold":         0,   "italic": 1,
        "primary":      "&H00FFFFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H55000000",
        "back_col":     "&H00000000",
        "border_style": 1,
        "outline":      2,   "shadow": 4,
        "scale_x":      100, "spacing": 2,
        "animation":    "focus",
        "accent":       "&H00D0D0FF",
    },
    "mrbeast": {
        "label":        "MrBeast",
        "desc":         "One word at a time, explosive pop-in",
        "emoji":        "💥",
        "fontsize":     88,  "fontsize_s": 96,
        "bold":         -1,  "italic": 0,
        "primary":      "&H0000FFFF",
        "secondary":    "&H000000FF",
        "outline_col":  "&H00000000",
        "back_col":     "&H00000000",
        "border_style": 1,
        "outline":      6,   "shadow": 4,
        "scale_x":      110, "spacing": 0,
        "animation":    "word_pop",
        "accent":       "&H00FFFFFF",
    },
}


# ── Per video-style accent and background colours ─────────────────
_STYLE_ACCENT = {
    "educational":  "&H0055FFFF",
    "documentary":  "&H00F5D87D",
    "motivational": "&H000066FF",
    "news":         "&H00FFFFFF",
    "viral":        "&H00FFFFFF",   # all white — reference video has no color
    "lifestyle":    "&H00FFFFFF",
}

_STYLE_BG = {
    "educational":  ("0d1437", "1a2d6e"),
    "documentary":  ("0c0a06", "2d2010"),
    "motivational": ("460800", "8f2100"),
    "news":         ("060610", "121230"),
    "viral":        ("080808", "141418"),   # very dark, matches reference
    "lifestyle":    ("060610", "0f0f22"),
}


# ══════════════════════════════════════════════════════════════════
#  CAPTION TEXT PROCESSING
# ══════════════════════════════════════════════════════════════════

_PLAIN_TAG_RE   = re.compile(r'\{[^}]*\}')
WORDS_PER_CHUNK = 3     # 3 words per chunk → ~1.5-2s each
MAX_CHARS_LINE  = 20    # forces tight 2-line wrapping
MAX_LINES       = 2

# Common power words that should be highlighted even when not ALL-CAPS
_POWER_WORDS = frozenset({
    "never", "always", "every", "most", "best", "worst", "only", "real",
    "truth", "secret", "first", "last", "stop", "start", "wrong", "right",
    "actually", "exactly", "proven", "critical", "crucial", "instantly",
    "impossible", "simple", "brutal", "shocking", "incredible", "nobody",
    "everything", "nothing", "massive", "ultimate", "single", "zero",
    "billion", "million", "percent", "double", "triple", "forever",
})


def _is_keyword(word: str) -> bool:
    """True for ALL-CAPS words AND common power words."""
    core = word.strip(".,!?:;\"'()[]…-–—")
    if not core:
        return False
    # ALL-CAPS (existing rule)
    if core.isupper() and len(core) > 1 and core.isalpha():
        return True
    # Power word (case-insensitive)
    if core.lower() in _POWER_WORDS and len(core) >= 4:
        return True
    return False


def _highlight(word: str, accent: str, size_pct: int = 112) -> str:
    """
    Colour + subtle size boost for highlighted keywords.
    size_pct=112 → 12% larger than body text — visible but not jarring.
    ASS tags: \\c sets colour, \\b1 forces bold, \\fscx/\\fscy scale the glyph.
    \\r resets all overrides back to style defaults after the word.
    """
    return (f"{{\\c{accent}\\b1\\fscx{size_pct}\\fscy{size_pct}}}"
            f"{word}"
            f"{{\\r}}")


def _plain_len(text: str) -> int:
    return len(_PLAIN_TAG_RE.sub("", text))


def _chunk_words(words: List[str], size: int) -> List[List[str]]:
    return [words[i:i + size] for i in range(0, len(words), size)]


def _apply_highlights(words: List[str], accent: str,
                      size_pct: int = 112) -> List[str]:
    """Highlight keywords with accent colour + size boost."""
    return [_highlight(w, accent, size_pct) if _is_keyword(w) else w
            for w in words]


def _wrap_to_ass(words: List[str]) -> str:
    lines: List[str]  = []
    current: List[str] = []
    current_len: int   = 0
    for word in words:
        plen = _plain_len(word)
        sep  = 1 if current else 0
        if current and (current_len + sep + plen > MAX_CHARS_LINE):
            lines.append(" ".join(current))
            if len(lines) >= MAX_LINES:
                break
            current, current_len = [word], plen
        else:
            current.append(word)
            current_len += sep + plen
    if current and len(lines) < MAX_LINES:
        lines.append(" ".join(current))
    return r"\N".join(lines)


def _animation_tag(animation: str) -> str:
    if animation == "fade":
        return r"{\fad(180,120)}"
    if animation == "popup":
        return r"{\fscx5\fscy5\t(0,220,\fscx100\fscy100)\fad(0,120)}"
    if animation == "focus":
        return r"{\blur8\fad(50,150)\t(0,280,\blur0)}"
    if animation == "word_pop":
        return r"{\fscx0\fscy0\t(0,180,\fscx100\fscy100)\fad(0,80)}"
    return ""


def _ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:06.3f}"


def _ass_escape(text: str) -> str:
    return (text
            .replace("\\", "")
            .replace("{", "")
            .replace("}", "")
            .replace("\n", " ")
            .strip())


# ══════════════════════════════════════════════════════════════════
#  ASS STYLE BLOCK BUILDER
# ══════════════════════════════════════════════════════════════════

def _make_ass_style(
    cap_style:    str,
    cap_position: str,
    video_style:  str  = "educational",
    shorts_mode:  bool = False,
) -> Tuple[str, str, str, int, Optional[str]]:
    """
    Build the ASS [V4+ Styles] block.

    Returns:
      (style_block_text, accent_colour, animation_type, alignment, pos_tag_or_None)
    """
    cs       = CAPTION_STYLES.get(cap_style, CAPTION_STYLES["standard"])
    pos      = CAPTION_POSITIONS.get(cap_position, CAPTION_POSITIONS["bottom"])
    vid_acc  = _STYLE_ACCENT.get(video_style, "&H00FFFFFF")

    acc       = cs.get("accent", vid_acc)
    animation = cs.get("animation", "fade")
    alignment = pos["alignment"]
    margin_v  = pos["margin_v_shorts"] if shorts_mode else pos["margin_v"]
    pos_tag   = pos["pos_tag"]

    fontsize = cs["fontsize_s"] if shorts_mode else cs["fontsize"]

    fmt = (
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,"
        "OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,"
        "ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
    )

    narr_style = (
        f"Style: Narr,{_FONT_NAME},{fontsize},"
        f"{cs['primary']},{cs['secondary']},"
        f"{cs['outline_col']},{cs['back_col']},"
        f"{cs['bold']},{cs['italic']},0,0,"
        f"{cs['scale_x']},100,{cs['spacing']},0,"
        f"{cs['border_style']},{cs['outline']},{cs['shadow']},"
        f"{alignment},60,60,{margin_v},1\n"
    )

    # Hook style — 25 % larger, same position, for the first-segment caption
    hook_size    = int(fontsize * 1.25)
    hook_outline = min(cs['outline'] + 1.5, 8)
    hook_shadow  = min(cs['shadow']  + 1,   6)
    hook_style   = (
        f"Style: Hook,{_FONT_NAME},{hook_size},"
        f"{cs['primary']},{cs['secondary']},"
        f"{cs['outline_col']},{cs['back_col']},"
        f"-1,0,0,0,"                        # always bold for hook
        f"{cs['scale_x']},100,0,0,"
        f"{cs['border_style']},{hook_outline},{hook_shadow},"
        f"{alignment},60,60,{margin_v},1\n"
    )

    lower_mv    = 120 if shorts_mode else 55
    lower_align = 8   # top-center — NEVER overlaps bottom narration captions
    lower_style = (
        f"Style: Lower,{_FONT_NAME},38,"
        f"{vid_acc},&H000000FF,"
        f"&H00000000,&H88000000,"
        f"0,0,0,0,100,100,1,0,3,2,0,"
        f"{lower_align},60,60,{lower_mv},1\n"
    )

    return fmt + narr_style + hook_style + lower_style, acc, animation, alignment, pos_tag


# ══════════════════════════════════════════════════════════════════
#  SUBTITLE WRITER
# ══════════════════════════════════════════════════════════════════

def write_subtitles(
    segments:     list,
    timestamps:   List[Tuple[float, float]],
    total_dur:    float,
    out:          Path,
    video_style:  str  = "educational",
    cap_position: str  = "bottom",
    cap_style:    str  = "standard",
    custom_x:     int  = 960,
    custom_y:     int  = 900,
    shorts_mode:  bool = False,
) -> Path:
    """
    Write an ASS subtitle file with word-chunk timing and keyword highlighting.

    Caption timing  : each chunk ≤ MAX_CHUNK_DUR (2.5 s) — captions refresh fast.
    Keyword emphasis: ALL-CAPS + power words get accent colour + 12 % size boost.
    Hook segment (i=0): uses the larger 'Hook' ASS style — 25 % bigger font +
                        faster popup animation for maximum first-2-second impact.
    Lower-third banner (on_screen_text) is placed at the TOP so it never
    overlaps narration captions at the bottom.
    """
    play_w = SV_W if shorts_mode else W
    play_h = SV_H if shorts_mode else H

    style_block, acc, animation, alignment, pos_tag = _make_ass_style(
        cap_style, cap_position, video_style, shorts_mode)

    # ── Inline position tag (custom only) ────────────────────────
    inline_pos = ""
    if pos_tag == "custom":
        cx = max(60, min(play_w - 60, custom_x))
        cy = max(30, min(play_h - 30, custom_y))
        inline_pos = f"{{\\pos({cx},{cy})}}"

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {play_w}\n"
        f"PlayResY: {play_h}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        + style_block
        + "\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, "
        "MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events: List[str] = []

    for i, seg in enumerate(segments):
        if i >= len(timestamps):
            break
        t0, t1 = timestamps[i]
        t1 = min(t1, total_dur)
        if t1 <= t0 + 0.05:
            continue

        seg_dur   = t1 - t0
        narration = _ass_escape(str(seg.get("narration", ""))).strip()
        on_screen = _ass_escape(str(seg.get("on_screen_text", ""))).strip()

        # Segment 0 = hook: larger font, popup animation for max first-2s impact
        is_hook_seg = (i == 0)
        narr_style_name = "Hook" if is_hook_seg else "Narr"
        seg_animation   = "popup" if is_hook_seg else animation
        # Slightly stronger size boost on highlights for hook segment
        kw_size_pct = 118 if is_hook_seg else 112

        # ── on_screen_text (shown briefly at segment start) ───────
        if on_screen and cap_style != "viral":
            # Only show on_screen banner for non-viral styles
            # (viral style keeps continuous narration text, no banner)
            lt0 = t0 + seg_dur * 0.10
            lt1 = t0 + seg_dur * 0.80
            events.append(
                f"Dialogue: 1,{_ts(lt0)},{_ts(lt1)},"
                f"Lower,,0,0,0,,{{\\fad(200,150)}}{on_screen}"
            )

        if not narration:
            continue

        words = narration.split()
        if not words:
            continue

        # ── MrBeast: one event per word, non-overlapping ─────────
        if animation == "word_pop":
            word_dur = seg_dur / max(len(words), 1)
            wtag     = _animation_tag("word_pop")
            for wi, word in enumerate(words):
                wt0 = t0 + wi * word_dur
                wt1 = t0 + (wi + 1) * word_dur  # exact end — no overlap
                events.append(
                    f"Dialogue: 0,{_ts(wt0)},{_ts(wt1)},"
                    f"Narr,,0,0,0,,{wtag}{inline_pos}{word}"
                )
            continue

        # ── All other styles: 3-word chunks, ≤ 2.5s each ─────────
        MAX_CHUNK_DUR = 2.5
        chunks = _chunk_words(words, WORDS_PER_CHUNK)
        n      = len(chunks)
        cdur   = min(seg_dur / n, MAX_CHUNK_DUR)
        atag   = _animation_tag(seg_animation)   # popup for hook, else style default

        for ci, chunk in enumerate(chunks):
            ct0 = t0 + ci * cdur
            ct1 = ct0 + cdur - min(0.08, cdur * 0.06)
            ct1 = max(ct0 + 0.30, ct1)
            ct1 = min(ct1, t1 - 0.05)   # never exceed segment end

            highlighted = _apply_highlights(chunk, acc, kw_size_pct)
            text        = _wrap_to_ass(highlighted)
            if not text.strip():
                continue

            events.append(
                f"Dialogue: 0,{_ts(ct0)},{_ts(ct1)},"
                f"{narr_style_name},,0,0,0,,{atag}{inline_pos}{text}"
            )

    out.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    log.info("  Subtitles: %d events | style=%s | pos=%s | %s → %s",
             len(events), cap_style, cap_position,
             "9:16" if shorts_mode else "16:9", out.name)
    return out


# ══════════════════════════════════════════════════════════════════
#  CARDS (title / outro)
# ══════════════════════════════════════════════════════════════════

def make_title_card(title: str, style: str, dur: float, out: Path,
                    shorts_mode: bool = False) -> Path:
    bg_hex = _STYLE_BG.get(style, ("0d1437", "1a2d6e"))[0]
    _make_text_card(title, bg_hex, dur, out, 68, True, shorts_mode)
    if not out.exists() or out.stat().st_size < 1000:
        log.warning("  Title card drawtext failed → plain colour")
        _plain_color_card(bg_hex, dur, out, shorts_mode)
    _validate_file(out, "Title card", min_bytes=500)
    return out


def make_outro_card(style: str, dur: float, out: Path,
                    shorts_mode: bool = False) -> Path:
    bg_hex = _STYLE_BG.get(style, ("0d1437", "1a2d6e"))[0]
    _make_text_card("Like  ·  Comment  ·  Subscribe",
                    bg_hex, dur, out, 56, False, shorts_mode)
    if not out.exists() or out.stat().st_size < 1000:
        _plain_color_card(bg_hex, dur, out, shorts_mode)
    _validate_file(out, "Outro card", min_bytes=500)
    return out


def _card_wh(shorts_mode: bool) -> Tuple[int, int]:
    return (SV_W, SV_H) if shorts_mode else (W, H)


def _make_text_card(text: str, bg_hex: str, dur: float, out: Path,
                    font_size: int = 64, is_title: bool = True,
                    shorts_mode: bool = False) -> None:
    cw, ch = _card_wh(shorts_mode)
    safe   = _safe_drawtext(text)
    farg   = (f":fontfile='{_FONT_PATH}'"
              if _FONT_PATH and os.path.exists(_FONT_PATH) else "")
    dt = (f"drawtext=text='{safe}'{farg}"
          f":fontsize={font_size}:fontcolor=white"
          f":x=(w-text_w)/2:y=(h-text_h)/2"
          f":shadowx=3:shadowy=3:shadowcolor=black@0.7"
          f":box=1:boxcolor=black@0.4:boxborderw=14")
    vf = (f"{dt},"
          f"fade=t=in:st=0:d=0.4,"
          f"fade=t=out:st={max(0.1,dur-0.4):.2f}:d=0.4,"
          f"format=yuv420p")
    r = subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c=0x{bg_hex}:size={cw}x{ch}:rate={FPS}",
         "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-an", "-t", str(dur), str(out)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=60)
    if r.returncode != 0:
        log.debug("  _make_text_card error: %s", r.stderr[-200:])


def _plain_color_card(bg_hex: str, dur: float, out: Path,
                      shorts_mode: bool = False) -> None:
    cw, ch = _card_wh(shorts_mode)
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-i", f"color=c=0x{bg_hex}:size={cw}x{ch}:rate={FPS}",
         "-vf", "format=yuv420p",
         "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
         "-an", "-t", str(dur), str(out)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30)


# ══════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ══════════════════════════════════════════════════════════════════

def _probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=15)
    try:
        d = float(r.stdout.strip())
        return d if d > 0 else 3.0
    except Exception:
        return 3.0


def _validate_file(path: Path, label: str, min_bytes: int = 1000) -> None:
    if not path.exists():
        raise RuntimeError(f"{label} was not created: {path}")
    if path.stat().st_size < min_bytes:
        raise RuntimeError(
            f"{label} too small ({path.stat().st_size} B < {min_bytes}): {path}")


def _safe_drawtext(text: str) -> str:
    return (text
            .replace("\\", "\\\\")
            .replace("'",  "\\'")
            .replace(":",  "\\:")
            .replace("%",  "\\%")
            .replace("[",  "\\[")
            .replace("]",  "\\]")
            .replace(",",  "\\,"))


# ══════════════════════════════════════════════════════════════════
#  CONCATENATION  —  hard-cut first, then xfade, then demuxer
# ══════════════════════════════════════════════════════════════════

def concat_video_segments(
    clips:       List[Path],
    out:         Path,
    wdir:        Path,
    xfade_dur:   float = 0.4,
    shorts_mode: bool  = False,
    hard_cut:    bool  = False,    # NEW: skip xfade entirely (reference style)
) -> None:
    """
    Concatenate video clips.

    hard_cut=True  (viral / lifestyle):  concat demuxer → zero-frame transitions
                                         Matches reference video exactly.
    hard_cut=False (standard YouTube):   xfade dissolve → concat demuxer fallback
    """
    missing = [c for c in clips if not c.exists() or c.stat().st_size < 500]
    if missing:
        raise RuntimeError(
            f"concat_video_segments: {len(missing)} clip(s) missing:\n"
            + "\n".join(f"  {c}" for c in missing))

    log.info("  Concat: %d clips  hard_cut=%s  xfade=%.2fs",
             len(clips), hard_cut, xfade_dur)

    if len(clips) == 1:
        shutil.copy2(clips[0], out)
        _validate_file(out, "video_track (single)")
        return

    # ── Hard cut mode (reference video style) ────────────────────
    if hard_cut:
        if _try_concat_demuxer(clips, out, wdir):
            _validate_file(out, "video_track (hard-cut demuxer)")
            return
        log.warning("  Hard-cut demuxer failed → re-encode concat")
        _try_reencode_concat(clips, out, wdir, shorts_mode)
        if out.exists() and out.stat().st_size > 1000:
            return
        raise RuntimeError("Hard-cut concat failed for all methods.")

    # ── Standard mode: xfade dissolve ────────────────────────────
    if _try_xfade(clips, out, xfade_dur):
        _validate_file(out, "video_track (xfade)")
        return

    log.warning("  xfade failed → concat demuxer")
    if _try_concat_demuxer(clips, out, wdir):
        _validate_file(out, "video_track (demuxer)")
        return

    log.warning("  demuxer failed → re-encode concat")
    _try_reencode_concat(clips, out, wdir, shorts_mode)
    if out.exists() and out.stat().st_size > 1000:
        return

    raise RuntimeError(f"All concat methods failed for {len(clips)} clips.")


def _try_xfade(clips: List[Path], out: Path, xfade_dur: float) -> bool:
    durations = [_probe_duration(c) for c in clips]
    inputs    = []
    for c in clips:
        inputs += ["-i", str(c)]
    n, fc, offset, prev = len(clips), [], 0.0, "[0:v]"
    for i in range(1, n):
        offset += max(0.1, durations[i-1] - xfade_dur)
        lbl     = f"[xf{i}]" if i < n - 1 else "[outv]"
        fc.append(
            f"{prev}[{i}:v]xfade=transition=dissolve:"
            f"duration={xfade_dur}:offset={offset:.3f}{lbl}")
        prev = f"[xf{i}]"
    r = subprocess.run(
        ["ffmpeg", "-y"] + inputs
        + ["-filter_complex", ";".join(fc),
           "-map", "[outv]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-an", str(out)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=600)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 1000


def _try_concat_demuxer(clips: List[Path], out: Path, wdir: Path) -> bool:
    lst = wdir / "_concat_list.txt"
    lst.write_text(
        "\n".join(
            "file '" + str(c).replace("\\", "/").replace("'", "'\\''") + "'"
            for c in clips),
        encoding="utf-8")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst),
         "-c:v", "libx264", "-preset", "fast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-an", str(out)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=600)
    lst.unlink(missing_ok=True)
    return r.returncode == 0 and out.exists() and out.stat().st_size > 1000


def _try_reencode_concat(clips: List[Path], out: Path, wdir: Path,
                         shorts_mode: bool = False) -> str:
    ow = SV_W if shorts_mode else W
    oh = SV_H if shorts_mode else H
    tmp = wdir / "_reencode_tmp"
    tmp.mkdir(exist_ok=True)
    last_err, norm = "", []
    for i, c in enumerate(clips):
        nc = tmp / f"norm_{i:03d}.mp4"
        r  = subprocess.run(
            ["ffmpeg", "-y", "-i", str(c),
             "-vf", (f"scale={ow}:{oh}:force_original_aspect_ratio=decrease,"
                     f"pad={ow}:{oh}:(ow-iw)/2:(oh-ih)/2,fps={FPS},format=yuv420p"),
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
             "-an", str(nc)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        last_err = r.stderr
        if r.returncode == 0 and nc.exists():
            norm.append(nc)
    if norm:
        _try_concat_demuxer(norm, out, wdir)
    shutil.rmtree(tmp, ignore_errors=True)
    return last_err


# ══════════════════════════════════════════════════════════════════
#  FINAL ASSEMBLY
# ══════════════════════════════════════════════════════════════════

def assemble(
    video_track:  Path,
    voice_track:  Path,
    subs_path:    Optional[Path],
    music_path:   Optional[Path],
    music_vol:    float,
    total_dur:    float,
    out:          Path,
    wdir:         Path,
    cap_position: str  = "bottom",
    cap_style:    str  = "standard",
    custom_x:     int  = 960,
    custom_y:     int  = 900,
    shorts_mode:  bool = False,
) -> None:
    """
    video + voice + (music) + (subtitles) → final MP4.

    Attempt 1: crf 18  preset slow    — high quality for YouTube/Shorts
    Attempt 2: crf 20  preset fast    — no subs (libass fallback)
    Attempt 3: crf 22  ultrafast      — bare minimum last resort
    """
    _validate_file(video_track, "video_track", min_bytes=1000)
    _validate_file(voice_track, "voice_track", min_bytes=500)
    log.info("  Pre-flight OK: video=%.1f MB  audio=%.1f MB",
             video_track.stat().st_size / 1_048_576,
             voice_track.stat().st_size / 1_048_576)

    inputs   = ["-i", str(video_track), "-i", str(voice_track)]
    fc_parts: List[str] = []
    maps     = ["-map", "0:v"]

    if music_path and music_path.exists() and music_vol > 0:
        inputs += ["-i", str(music_path)]
        fade_start = max(0.0, total_dur - 3.0)
        fc_parts.append(
            f"[1:a]volume=1.0[voice];"
            f"[2:a]volume={music_vol:.3f},"
            f"afade=t=in:st=0:d=2.0,"
            f"afade=t=out:st={fade_start:.1f}:d=3.0[music];"
            f"[voice][music]amix=inputs=2:duration=shortest:"
            f"normalize=0:dropout_transition=2[audio]"
        )
        maps += ["-map", "[audio]"]
    else:
        maps += ["-map", "1:a"]

    cwd = str(wdir)
    subs_filter: List[str] = []
    if subs_path and subs_path.exists():
        dst_subs = wdir / subs_path.name
        if subs_path.resolve() != dst_subs.resolve():
            shutil.copy2(subs_path, dst_subs)
        subs_filter = ["-vf", f"subtitles={dst_subs.name}"]
        log.info("  Subtitles: %s (pos=%s style=%s)", dst_subs.name,
                 cap_position, cap_style)

    fc = ["-filter_complex", ";".join(fc_parts)] if fc_parts else []

    # ── Attempt 1: crf18 slow ────────────────────────────────────
    cmd1 = (["ffmpeg", "-y"]
            + inputs + fc + maps + subs_filter
            + ["-c:v", "libx264", "-preset", "slow", "-crf", "18",
               "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k",
               "-t", str(total_dur), "-movflags", "+faststart", str(out)])
    log.info("  Attempt 1: crf18 slow")
    r1 = subprocess.run(cmd1, capture_output=True, encoding="utf-8",
                        errors="replace", timeout=1200, cwd=cwd)
    if r1.returncode == 0 and out.exists() and out.stat().st_size > 10_000:
        log.info("  Final: %.1f MB ✓", out.stat().st_size / 1_048_576)
        return
    log.warning("  Attempt 1 failed: %s", r1.stderr[-400:])

    # ── Attempt 2: no subtitles ───────────────────────────────────
    if subs_filter:
        cmd2 = (["ffmpeg", "-y"]
                + inputs + fc + maps
                + ["-c:v", "libx264", "-preset", "fast", "-crf", "20",
                   "-pix_fmt", "yuv420p",
                   "-c:a", "aac", "-b:a", "192k",
                   "-t", str(total_dur), "-movflags", "+faststart", str(out)])
        log.info("  Attempt 2: crf20 fast (no subs)")
        r2 = subprocess.run(cmd2, capture_output=True, encoding="utf-8",
                            errors="replace", timeout=600, cwd=cwd)
        if r2.returncode == 0 and out.exists() and out.stat().st_size > 10_000:
            log.info("  Final: %.1f MB (no subs)", out.stat().st_size / 1_048_576)
            return
        log.warning("  Attempt 2 failed: %s", r2.stderr[-300:])

    # ── Attempt 3: bare minimum ───────────────────────────────────
    cmd3 = ["ffmpeg", "-y",
            "-i", str(video_track), "-i", str(voice_track),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(total_dur), "-movflags", "+faststart", str(out)]
    log.info("  Attempt 3: ultrafast bare minimum")
    r3 = subprocess.run(cmd3, capture_output=True, encoding="utf-8",
                        errors="replace", timeout=300, cwd=cwd)
    if r3.returncode == 0 and out.exists() and out.stat().st_size > 10_000:
        log.info("  Final: %.1f MB (bare min)", out.stat().st_size / 1_048_576)
        return

    raise RuntimeError(
        f"Final assembly failed after 3 attempts.\n"
        f"  video: {video_track} ({video_track.stat().st_size} B)\n"
        f"  audio: {voice_track} ({voice_track.stat().st_size} B)\n"
        f"Last error:\n{r3.stderr[-800:]}")
