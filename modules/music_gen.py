"""
Background Music  —  No API key required
=========================================
Priority:
  1. Local MP3/WAV files in the music/ folder
  2. FFmpeg sine-wave ambient pad synthesis (always works offline)

The synthesised pad uses layered harmonics with tremolo + reverb
so it sounds like proper ambient background music, not a test tone.
"""

import subprocess, logging, struct, math, random
from pathlib import Path
from typing import Optional

log = logging.getLogger("ytgen")

# ─── Chord definitions per style ─────────────────────────────────
# Each chord = list of (frequency_hz, relative_amplitude)
_CHORDS = {
    "educational":  [(220.0,1.0),(261.6,0.8),(329.6,0.6),(392.0,0.4),(440.0,0.25)],
    "documentary":  [(174.6,1.0),(207.7,0.8),(261.6,0.6),(311.1,0.4),(349.2,0.2)],
    "explainer":    [(261.6,1.0),(329.6,0.8),(392.0,0.6),(523.3,0.4),(659.3,0.2)],
    "motivational": [(329.6,1.0),(392.0,0.9),(493.9,0.7),(659.3,0.5),(783.9,0.3)],
    "news":         [(196.0,1.0),(246.9,0.7),(293.7,0.5),(369.9,0.3),(440.0,0.2)],
}


def _generate_wav(dur: float, style: str) -> bytes:
    """
    Pure-Python WAV synthesis.  Produces a layered ambient chord pad
    with slow tremolo + 1-octave harmonics for richness.
    No external libraries.  Returns raw WAV bytes.
    """
    SR = 44100
    TWO_PI = 2.0 * math.pi
    n = int(SR * dur)

    chord  = _CHORDS.get(style, _CHORDS["educational"])
    total_amp = sum(a for _, a in chord) * 1.8   # normalisation factor

    samples = []
    for i in range(n):
        t        = i / SR
        # Slow tremolo modulator  (0.15 Hz, depth 12%)
        tremolo  = 1.0 - 0.12 * (0.5 + 0.5 * math.sin(TWO_PI * 0.15 * t))
        # Build chord
        val = 0.0
        for freq, amp in chord:
            # Fundamental
            val += amp * math.sin(TWO_PI * freq * t)
            # Octave harmonic at 30% amplitude
            val += amp * 0.30 * math.sin(TWO_PI * freq * 2 * t)
        val = val * tremolo / total_amp * 0.22   # master volume 22%
        # Fade in (2s) / fade out (3s)
        if t < 2.0:
            val *= t / 2.0
        elif t > dur - 3.0:
            val *= (dur - t) / 3.0
        samples.append(max(-32767, min(32767, int(val * 32767))))

    # Build WAV
    data = struct.pack(f"<{n}h", *samples)
    hdr  = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(data), b"WAVE",
        b"fmt ", 16,
        1, 1,                    # PCM, mono
        SR, SR * 2,              # sample rate, byte rate
        2, 16,                   # block align, bits per sample
        b"data", len(data),
    )
    return hdr + data


def _synth_music(dur: float, style: str, out: Path) -> bool:
    """Synthesise ambient pad, convert to AAC via FFmpeg."""
    wav_path = out.with_suffix(".wav")
    try:
        wav_path.write_bytes(_generate_wav(dur + 4.0, style))
    except Exception as e:
        log.warning("  Music synthesis failed: %s", e)
        return False

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(wav_path),
         "-af", f"aecho=0.8:0.88:250:0.25,aecho=0.8:0.88:500:0.15",
         "-c:a", "aac", "-b:a", "128k", str(out)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=30)
    wav_path.unlink(missing_ok=True)
    return r.returncode == 0


def get_music(style: str, duration: float,
              music_dir: Path, wdir: Optional[Path] = None) -> Optional[Path]:
    """
    Return a path to background music of the given duration.
    Uses local files first, then synthesises if none exist.
    """
    # 1. Look for local files
    local = sorted([
        p for p in music_dir.glob("**/*")
        if p.suffix.lower() in (".mp3", ".wav", ".aac", ".m4a", ".ogg")
    ])
    if local:
        chosen = random.choice(local)
        log.info("  Music: using local file  %s", chosen.name)
        return chosen

    # 2. Synthesise
    out = (wdir or music_dir) / f"_synth_{style}.aac"
    if out.exists():
        return out   # reuse from this session

    log.info("  Music: synthesising ambient pad (%s, %.0fs)…", style, duration)
    if _synth_music(duration, style, out):
        log.info("  Music: synthesised OK")
        return out

    log.warning("  Music: synthesis failed — video will have no background music")
    return None
