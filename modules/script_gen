"""
Script Generation  —  Gemini + Groq AI Chain
=============================================
v6  Two-Provider Edition (no Claude dependency)

Provider priority (auto-detected from .env):
  1. Gemini (Google)  — gemini-1.5-flash    — free tier, 1 500 req/day
  2. Groq             — llama-3.3-70b       — free tier, 14 400 req/day
  3. Local template   — always works, no key required

Set GEMINI_API_KEY and/or GROQ_API_KEY in your .env file.
"""

import json, re, httpx, logging
log = logging.getLogger("ytgen")


# ── Exception ─────────────────────────────────────────────────────

class ProviderError(Exception):
    """Any AI provider failure — next provider in chain should be tried."""

# ── Video styles ──────────────────────────────────────────────────
VIDEO_STYLES = {
    "viral":       {"label": "🔥 Viral Listicle", "tone": "direct, punchy, impossible to scroll past — like top Shorts creators"},
    "lifestyle":   {"label": "💪 Lifestyle",       "tone": "personal, motivational, mindset and self-improvement focused"},
    "educational": {"label": "🎓 Educational",     "tone": "authoritative and clear — TED-Ed style"},
    "documentary": {"label": "🌍 Documentary",     "tone": "cinematic and investigative — Netflix documentary style"},
    "motivational":{"label": "⚡ Motivational",    "tone": "high-energy and inspiring — drives immediate action"},
    "news":        {"label": "📰 News",            "tone": "factual and authoritative — broadcast journalism"},
}

GEMINI_MODEL  = "gemini-1.5-flash"          # free tier: 15 RPM, 1 500 req/day
GROQ_MODEL    = "llama-3.3-70b-versatile"   # free tier: 14 400 req/day

# ── Shared JSON response parser ───────────────────────────────────

def _parse_json_response(raw: str, provider: str = "") -> dict:
    """
    Strip markdown fences, parse JSON, and validate the segments array.
    Raises ValueError on any parse or validation failure.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    result = json.loads(text)
    segs   = result.get("segments", [])
    if not isinstance(segs, list) or len(segs) < 2:
        raise ValueError(
            f"{provider} returned too few segments: {len(segs)}"
        )
    return result

# Segment counts per style: viral = more, shorter clips (4s avg)
_SEGS = {
    "viral":       lambda d: max(8,  min(16, d // 4)),
    "lifestyle":   lambda d: max(7,  min(13, d // 5)),
    "educational": lambda d: max(5,  min(12, d // 10)),
    "documentary": lambda d: max(5,  min(12, d // 10)),
    "motivational":lambda d: max(6,  min(12, d // 6)),
    "news":        lambda d: max(5,  min(10, d // 8)),
}


# ════════════════════════════════════════════════════════════════════
#  CLAUDE PROMPTS
# ════════════════════════════════════════════════════════════════════

async def _viral_prompt(topic, tone, dur, n_segs, api_key):
    """
    Numbered listicle structure that matches the reference video exactly.
    Hook teaser → Setup ("Here are N...") → Numbered items → CTA close.
    """
    n_items  = max(3, n_segs - 3)
    sec_seg  = round(dur / n_segs, 1)
    max_w    = round(sec_seg * 140 / 60)   # words at 140 wpm

    p = f"""You are a viral YouTube Shorts creator. Your videos stop thumbs because every sentence earns the next one.

ASSIGNMENT
Topic    : {topic}
Mood     : {tone}
Length   : {dur}s | {n_segs} segments × ~{sec_seg}s each

━━━ EXACT STRUCTURE ━━━
Segment 1 — TEASER HOOK (≤ 8 words, creates instant curiosity):
  Pattern: "It took me [X] to learn this."
      OR   "Nobody talks about the real [topic]."
      OR   "[Shocking single sentence about topic]."
  NO greetings. NO intros. Pure intrigue.

Segment 2 — SETUP (~{sec_seg}s):
  Reveal the list. Pattern: "Here are {n_items} [uncomfortable truths / cold hard facts / brutal lessons] about [topic]."

Segments 3–{n_segs - 1} — NUMBERED ITEMS ({n_items} items):
  Each opens: "Number [One/Two/Three...]"
  Then 1–2 SHORT sentences. MAX {max_w} words total.
  Use ALL-CAPS for 1–2 power words: "This is BRUTAL", "NEVER do this"
  Be SPECIFIC: "87% of people quit" > "most people fail"

Segment {n_segs} — CTA CLOSE (~3s):
  One punchy takeaway. End: "Follow for more." or a question.

━━━ VISUAL QUERIES (critical for clip quality) ━━━
✗ BAD: "success", "life", "business"
✓ GOOD: "drone aerial city night skyline", "athlete running mountain trail"
Rule: 3–6 words, filmable scene, DIFFERENT for every segment.
Great queries: aerial drone, ocean waves, city skyline, mountain runner, dark road, luxury car

━━━ ON_SCREEN_TEXT ━━━
3–5 ALL-CAPS words — the gut-punch punchline of that segment.

Return ONLY valid JSON, no markdown:
{{
  "title": "Punchy YouTube Shorts title ≤ 55 chars",
  "description": "80-word description. 5 hashtags at end.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "segments": [
    {{"id":1,"type":"hook","narration":"≤8 word teaser","visual_query":"3-6 word scene","on_screen_text":"3-5 ALL-CAPS"}},
    {{"id":2,"type":"setup","narration":"Here are {n_items} things about {topic}.","visual_query":"different scene","on_screen_text":"{n_items} THINGS TO KNOW"}},
    {{"id":3,"type":"body","narration":"Number One. [point]. MAX {max_w} words.","visual_query":"cinematic scene","on_screen_text":"ALL CAPS PUNCHLINE"}}
  ]
}}"""
    return await _call_claude(p, api_key)


async def _shorts_prompt(topic, tone, dur, n_segs, api_key):
    """Hook → punchy body → CTA. For lifestyle/motivational Shorts."""
    sec_seg = round(dur / n_segs, 1)
    max_w   = round(sec_seg * 140 / 60)

    p = f"""You are an elite YouTube Shorts scriptwriter. Viral because: FAST, PUNCHY, impossible to scroll past.

ASSIGNMENT
Topic    : {topic}
Mood     : {tone}
Length   : {dur}s | {n_segs} segments × ~{sec_seg}s each

━━━ HOOK (segment 1, ≤ 3s) ━━━
Open with a SHOCKING stat, bold question, or counter-intuitive claim.
First 5 words must make someone STOP scrolling.
No intros. No "Hey guys". Proven patterns:
  "X% of people never learn this..."
  "Nobody talks about [uncomfortable truth]..."
  "I spent [time] learning what I'll tell you in [duration]..."

━━━ BODY (segments 2–{n_segs-1}) ━━━
ONE point per segment. MAX {max_w} words. Short sentences (≤ 12 words each).
ALL-CAPS for 1–2 key words. Specific examples beat vague claims.

━━━ CLOSE (segment {n_segs}) ━━━
Aha-moment in one sentence. End: "Follow for more." or thought-provoking question.

━━━ VISUAL QUERIES ━━━
3–6 words: subject + action + setting. DIFFERENT per segment.
Great: "athlete cold morning training", "city aerial golden hour drone", "person journaling window light"

ON_SCREEN_TEXT: 3–5 ALL-CAPS words — segment punchline.

Return ONLY valid JSON, no markdown:
{{
  "title": "YouTube Shorts title ≤ 55 chars",
  "description": "80-word description. 5 hashtags at end.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "segments": [
    {{"id":1,"type":"hook","narration":"Hook. MAX {max_w} words.","visual_query":"3-6 word scene","on_screen_text":"ALL-CAPS HOOK"}},
    {{"id":2,"type":"body","narration":"Point. MAX {max_w} words.","visual_query":"different scene","on_screen_text":"ALL-CAPS POINT"}}
  ]
}}"""
    return await _call_claude(p, api_key)


async def _standard_prompt(topic, tone, dur, n_segs, api_key):
    """Long-form YouTube: hook + structured body + conclusion."""
    p = f"""You are a world-class YouTube scriptwriter.

ASSIGNMENT
Topic    : {topic}
Style    : {tone}
Duration : {dur}s | {n_segs} segments

STRUCTURE:
  Seg 1          — HOOK: bold stat / provocative question. First 3 words make viewers stop.
  Segs 2–{n_segs-1} — BODY: one specific concrete point each. Real examples. No filler.
  Seg {n_segs}         — CONCLUSION: key takeaway + subscribe CTA.

RULES:
• Conversational contractions. Sound human.
• NEVER: "In this video", "Today we'll", "Welcome", "Hello everyone"
• ALL-CAPS for 1–2 emphasis words per segment.
• ~{dur//n_segs}s per segment at 145 wpm.

VISUAL QUERIES: 3–7 words, subject + action + setting, different per segment.
ON_SCREEN_TEXT: 4–8 word punchy headline per segment.

Return ONLY valid JSON, no markdown:
{{
  "title": "YouTube title ≤ 65 chars",
  "description": "150-200 word SEO description. 5 hashtags at end.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "segments": [
    {{"id":1,"type":"hook","narration":"2-4 sentences.","visual_query":"3-7 word scene","on_screen_text":"4-8 word headline"}}
  ]
}}"""
    return await _call_claude(p, api_key)



# ── Google Gemini HTTP call ────────────────────────────────────────
#
# Free tier (AI Studio key):
#   • Gemini 1.5 Flash  — 15 RPM · 1 000 000 TPM · 1 500 req/day
#   • Get key: https://aistudio.google.com/app/apikey  (no credit card)

async def _call_gemini(prompt: str, api_key: str) -> dict:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta"
        f"/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 2500,
            "temperature":     0.75,
            "topP":            0.95,
        },
    }
    timeout = httpx.Timeout(connect=8.0, read=90.0, write=8.0, pool=8.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=body,
                              headers={"content-type": "application/json"})

    if r.status_code == 400:
        msg = r.json().get("error", {}).get("message", r.text[:120])
        raise ProviderError(f"Gemini 400: {msg}")
    if r.status_code == 401:
        raise ProviderError(f"Gemini 401 Unauthorized — check GEMINI_API_KEY")
    if r.status_code == 429:
        raise ProviderError("Gemini 429 rate limited")
    if r.status_code != 200:
        raise ProviderError(f"Gemini {r.status_code}: {r.text[:200]}")

    try:
        raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ProviderError(f"Gemini unexpected response shape: {e}")

    return _parse_json_response(raw, "Gemini")


# ── Groq HTTP call ─────────────────────────────────────────────────
#
# Free tier (no credit card):
#   • llama-3.3-70b-versatile — 14 400 req/day · 500 RPM
#   • Get key: https://console.groq.com  → API Keys

async def _call_groq(prompt: str, api_key: str) -> dict:
    timeout = httpx.Timeout(connect=8.0, read=90.0, write=8.0, pool=8.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}",
                     "content-type": "application/json"},
            json={"model": GROQ_MODEL,
                  "max_tokens": 2500,
                  "temperature": 0.75,
                  "messages": [{"role": "user", "content": prompt}]},
        )

    if r.status_code == 401:
        raise ProviderError("Groq 401 Unauthorized — check GROQ_API_KEY")
    if r.status_code == 429:
        raise ProviderError("Groq 429 rate limited")
    if r.status_code != 200:
        raise ProviderError(f"Groq {r.status_code}: {r.text[:200]}")

    try:
        raw = r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ProviderError(f"Groq unexpected response shape: {e}")

    return _parse_json_response(raw, "Groq")


# ════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINTS
# ════════════════════════════════════════════════════════════════════

async def _run_provider_prompt(topic, style, duration_sec,
                                caller, api_key, label):
    """
    Build the right prompt for this style and call `caller(prompt, api_key)`.
    `caller` is one of _call_gemini or _call_groq (both accept (prompt, key)).
    """
    tone   = VIDEO_STYLES.get(style, VIDEO_STYLES["educational"])["tone"]
    n_segs = _SEGS.get(style, _SEGS["educational"])(duration_sec)

    # Re-use the same prompt builders; just swap out the _call_* at the end.
    # We extract the prompt string by temporarily calling the builder with a
    # sentinel API key that will never fire a real HTTP request.
    # Actually simpler: the prompt builders return the result of _call_* — we
    # can't intercept them cleanly.  Instead replicate the prompt selection
    # logic here and call the provider directly.

    if style == "viral":
        n_items  = max(3, n_segs - 3)
        sec_seg  = round(duration_sec / n_segs, 1)
        max_w    = round(sec_seg * 140 / 60)
        p = (
            f"You are a viral YouTube Shorts creator.\n"
            f"Topic: {topic}\nMood: {tone}\n"
            f"Length: {duration_sec}s | {n_segs} segments × ~{sec_seg}s each\n\n"
            f"STRUCTURE:\n"
            f"Seg 1 — TEASER HOOK (≤8 words, instant curiosity)\n"
            f"Seg 2 — SETUP: 'Here are {n_items} things about {topic}.'\n"
            f"Segs 3-{n_segs-1} — NUMBERED ITEMS: 'Number One/Two/…' then 1-2 short sentences. MAX {max_w} words.\n"
            f"Seg {n_segs} — CTA CLOSE: one punchline + 'Follow for more.'\n\n"
            f"VISUAL QUERIES: 3-6 words, filmable scene, different every segment.\n"
            f"ON_SCREEN_TEXT: 3-5 ALL-CAPS words — the punchline.\n\n"
            f"Return ONLY valid JSON, no markdown:\n"
            f'{{"title":"≤55 char title","description":"80-word desc. 5 hashtags.","tags":["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10"],'
            f'"segments":[{{"id":1,"type":"hook","narration":"≤8 word teaser","visual_query":"scene","on_screen_text":"CAPS"}}]}}'
        )
    elif style in ("lifestyle", "motivational") or style == "shorts":
        sec_seg = round(duration_sec / n_segs, 1)
        max_w   = round(sec_seg * 140 / 60)
        p = (
            f"You are an elite YouTube Shorts scriptwriter.\n"
            f"Topic: {topic}\nMood: {tone}\n"
            f"Length: {duration_sec}s | {n_segs} segments × ~{sec_seg}s\n\n"
            f"HOOK (seg 1, ≤3s): shocking stat OR bold question. No intros.\n"
            f"BODY (segs 2-{n_segs-1}): ONE point, MAX {max_w} words, ALL-CAPS 1-2 key words.\n"
            f"CLOSE (seg {n_segs}): aha-moment + 'Follow for more.'\n\n"
            f"VISUAL QUERIES: 3-6 words each. ON_SCREEN_TEXT: 3-5 ALL-CAPS.\n\n"
            f"Return ONLY valid JSON, no markdown:\n"
            f'{{"title":"≤55 chars","description":"80-word desc. 5 hashtags.","tags":["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10"],'
            f'"segments":[{{"id":1,"type":"hook","narration":"hook text","visual_query":"scene","on_screen_text":"CAPS"}}]}}'
        )
    else:
        sec_seg = round(duration_sec / n_segs, 1)
        p = (
            f"You are a professional YouTube scriptwriter.\n"
            f"Topic: {topic}\nStyle: {tone}\n"
            f"Length: {duration_sec}s | {n_segs} segments × ~{sec_seg}s\n\n"
            f"Seg 1: HOOK — bold opening that demands attention.\n"
            f"Segs 2-{n_segs-1}: body points, vivid and specific.\n"
            f"Seg {n_segs}: memorable close + call to action.\n\n"
            f"VISUAL QUERIES: 3-7 words, cinematic, different per segment.\n"
            f"ON_SCREEN_TEXT: 4-8 word headline per segment.\n\n"
            f"Return ONLY valid JSON, no markdown:\n"
            f'{{"title":"≤65 char title","description":"150-200 word desc. 5 hashtags.","tags":["t1","t2","t3","t4","t5","t6","t7","t8","t9","t10"],'
            f'"segments":[{{"id":1,"type":"hook","narration":"2-4 sentences.","visual_query":"3-7 word scene","on_screen_text":"4-8 word headline"}}]}}'
        )

    log.info("  %s: style=%s  n=%d  dur=%ds", label, style, n_segs, duration_sec)
    return await caller(p, api_key)


async def generate_script(topic, style, duration_sec,
                           gemini_key  = "",
                           groq_key    = "",
                           shorts_mode = False,
                           # claude_key accepted but ignored — kept only so old
                           # call-sites don't break with TypeError
                           claude_key  = "",
                           api_key     = None):
    """
    Main entry point — Gemini + Groq AI chain.

    Provider priority (first available key wins):
      1. Gemini  (GEMINI_API_KEY) — free 1 500 req/day, no credit card
      2. Groq    (GROQ_API_KEY)   — free 14 400 req/day, Llama 3.3 70B
      3. Local template           — always works, zero API calls

    The `_source` key in the returned dict tells you which was used:
      "gemini" | "groq" | "local_template"
    """
    _ph_gemini = "your-gemini-key-here"
    _ph_groq   = "your-groq-key-here"

    def _valid(key, placeholder):
        return bool(key and key not in (placeholder, "", "your-key-here"))

    has_gemini = _valid(gemini_key, _ph_gemini)
    has_groq   = _valid(groq_key,   _ph_groq)

    # ── 1. Gemini ─────────────────────────────────────────────────
    if has_gemini:
        try:
            result = await _run_provider_prompt(
                topic, style, duration_sec, _call_gemini, gemini_key, "Gemini")
            result["_source"] = "gemini"
            log.info("  ✅  Script source: Gemini (gemini-1.5-flash)")
            return result
        except ProviderError as e:
            log.warning("  Gemini failed: %s — trying Groq", str(e)[:100])
        except Exception as e:
            log.warning("  Gemini error (%s: %s) — trying Groq",
                        type(e).__name__, str(e)[:80])
    else:
        log.info("  Gemini not configured  →  add GEMINI_API_KEY to .env"
                 "  (free: aistudio.google.com/app/apikey)")

    # ── 2. Groq ───────────────────────────────────────────────────
    if has_groq:
        try:
            result = await _run_provider_prompt(
                topic, style, duration_sec, _call_groq, groq_key, "Groq")
            result["_source"] = "groq"
            log.info("  ✅  Script source: Groq (llama-3.3-70b-versatile)")
            return result
        except ProviderError as e:
            log.warning("  Groq failed: %s — using local template", str(e)[:100])
        except Exception as e:
            log.warning("  Groq error (%s: %s) — using local template",
                        type(e).__name__, str(e)[:80])
    else:
        if not has_gemini:
            log.info("  Groq not configured   →  add GROQ_API_KEY to .env"
                     "  (free: console.groq.com)")

    # ── 3. Local template ─────────────────────────────────────────
    if has_gemini or has_groq:
        log.warning("  All AI providers failed — falling back to local template")
    else:
        log.info("  No AI keys set — using local template script")

    result = _fallback_shorts(topic, style, duration_sec)
    result["_source"] = "local_template"
    return result



# ════════════════════════════════════════════════════════════════════
#  FALLBACK SCRIPT GENERATOR  (used when no AI keys are configured
#  or all AI providers fail)
#
#  Structure enforced for every video style:
#    1. HOOK          — scroll-stopping first sentence
#    2. CONTEXT       — brief framing of why this matters
#    3. INTERESTING FACT(S) — the meat; 1–N specific points
#    4. ENDING / CTA  — memorable close + call to action
# ════════════════════════════════════════════════════════════════════

# Words too generic to use as a visual query keyword
_KW_STOP = frozenset({
    "a","an","the","and","but","or","so","if","in","on","at","to","for",
    "of","with","by","is","are","was","were","be","this","that","it",
    "we","you","i","me","my","your","our","they","them","their",
    "not","no","never","always","here","there","just","than","more",
    "most","will","can","do","does","did","have","has","had","how",
    "what","why","when","who","which","all","one","two","three","four",
    "five","about","from","into","out","up","its","very","also","each",
    "every","some","few","many","get","got","make","made","know","think",
    "want","need","see","say","said","much","way","even","really","thing",
    "things","good","great","best","better","new","old","big","small",
    "time","year","day","world","life","people","person","human",
})

def _extract_topic_keywords(topic: str, n: int = 4) -> list:
    """
    Pull the most meaningful words from the topic string.
    Returns up to n lowercase keywords suitable for Pexels queries.

    Example:
      "Why waking up at 5am changes your brain" →
      ["waking", "brain", "changes", "5am"]
    """
    words = re.sub(r"[^\w\s]", "", topic.lower()).split()
    seen: set = set()
    result = []
    for w in words:
        if len(w) >= 3 and w not in _KW_STOP and w not in seen:
            seen.add(w)
            result.append(w)
        if len(result) >= n:
            break
    return result


def _visual_for_kw(kw: list, index: int, style: str) -> str:
    """
    Build a Pexels-ready visual query from topic keywords + style context.
    Rotates through different cinematic contexts per segment index.
    """
    subject = " ".join(kw[:2]) if kw else style
    contexts = [
        "cinematic aerial drone shot",
        "close-up dramatic lighting",
        "wide angle outdoor landscape",
        "person focus shallow depth",
        "night city timelapse motion",
        "sunrise golden hour natural",
    ]
    ctx = contexts[index % len(contexts)]
    return f"{subject} {ctx}"


# ── Segment templates per structure section ──────────────────────

def _build_hook(p: str, P: str, style: str) -> tuple:
    """Returns (narration, visual_query, on_screen_text) for the hook segment."""
    hooks = {
        "viral":        (f"Nobody tells you the real truth about {p}.",
                         "aerial drone city night lights dramatic",
                         "THE REAL TRUTH"),
        "lifestyle":    (f"Most people spend years on {p} and still get it wrong.",
                         "person walking alone morning fog bridge",
                         "STOP DOING THIS"),
        "educational":  (f"Almost everything you know about {p} is missing the key part.",
                         "scientist researcher laboratory data",
                         "WHAT THEY MISS"),
        "documentary":  (f"The story of {p} begins where most people stop looking.",
                         "aerial drone wide mysterious landscape dawn",
                         "WHERE IT BEGAN"),
        "motivational": (f"Everything between you and mastering {p} is one decision.",
                         "athlete mountain summit determination",
                         "ONE DECISION AWAY"),
        "news":         (f"New evidence is forcing experts to rethink {p} entirely.",
                         "news studio broadcast professional anchor",
                         f"BREAKING: {P[:18].upper()}"),
    }
    return hooks.get(style, hooks["educational"])


def _build_context(p: str, P: str, style: str, kw: list) -> tuple:
    """Returns (narration, visual_query, on_screen_text) for the context segment."""
    contexts = {
        "viral":        (f"Here is what actually happens when you understand {p} at a deep level.",
                         "person studying reading books focused",
                         "WHAT CHANGES"),
        "lifestyle":    (f"The gap between knowing about {p} and actually living it is enormous.",
                         "notebook journal writing morning coffee window",
                         "THE REAL GAP"),
        "educational":  (f"{P} is one of those topics where the standard explanation leaves out the most important piece.",
                         "whiteboard diagram explanation academic",
                         "THE MISSING PIECE"),
        "documentary":  (f"For decades the full picture of {p} stayed just out of public view.",
                         "archival footage film grain dramatic shadow",
                         "HIDDEN FOR DECADES"),
        "motivational": (f"The people succeeding at {p} right now are not more talented. They simply started sooner.",
                         "focused person working desk early light",
                         "THEY STARTED EARLIER"),
        "news":         (f"Three independent sources are now pointing to the same conclusion about {p}.",
                         "research data graph statistics analyst",
                         "STUDIES AGREE"),
    }
    return contexts.get(style, contexts["educational"])


def _build_facts(p: str, P: str, style: str, n: int, kw: list) -> list:
    """
    Returns a list of (narration, visual_query, on_screen_text) tuples
    for the interesting-fact body segments. Always generates exactly `n` items.
    """
    banks = {
        "viral": [
            (f"Number One. The single biggest mistake people make with {p} is focusing on outcomes instead of systems.",
             "athlete training sunrise discipline habit",
             "WRONG FOCUS"),
            (f"Number Two. Eighty seven percent of people quit {p} right before it gets easy.",
             "empty dark road forest leading forward",
             "QUIT TOO EARLY"),
            (f"Number Three. Your environment shapes your results far more than willpower ever will.",
             "modern glass architecture forest mist light",
             "ENVIRONMENT WINS"),
            (f"Number Four. The compound effect of small daily actions on {p} cannot be appreciated until you live it.",
             "plant growing time-lapse progress morning",
             "COMPOUND EFFECT"),
            (f"Number Five. The one percent who succeed at {p} are not gifted. They are ruthlessly consistent.",
             "businessman walking city glass reflection",
             "1% MINDSET"),
            (f"Number Six. Ninety days of consistency with {p} beats one week of intensity every single time.",
             "time-lapse city traffic night long exposure",
             "90 DAYS BEATS ALL"),
            (f"Number Seven. You will never feel completely ready. The moment you wait for rarely arrives.",
             "luxury car coastal road golden hour drive",
             "START BEFORE READY"),
            (f"Number Eight. The people who master {p} protect their focus the same way others protect their money.",
             "person meditating calm ocean sunrise alone",
             "PROTECT YOUR FOCUS"),
        ],
        "lifestyle": [
            (f"Habit One. Begin before you feel ready. Readiness is the story your brain tells you to stay safe.",
             "runner starting empty road dawn horizon",
             "START NOW"),
            (f"Habit Two. Track the process not just the result. Results are delayed processes.",
             "notebook journal pen writing coffee",
             "TRACK THE PROCESS"),
            (f"Habit Three. Your social circle is your ceiling. Upgrade who you spend time with.",
             "friends rooftop city view success laughing",
             "UPGRADE YOUR CIRCLE"),
            (f"Habit Four. Discomfort is the price of growth. Get comfortable being uncomfortable.",
             "athlete cold training discipline focus",
             "EMBRACE DISCOMFORT"),
            (f"Habit Five. Your morning sets everything. Win the morning and you win the day.",
             "morning gym weights dark early discipline",
             "WIN YOUR MORNING"),
            (f"Habit Six. Protect your energy with the same urgency you protect your time.",
             "person reading calm peaceful interior light",
             "ENERGY IS MONEY"),
        ],
        "educational": [
            (f"Point One. Understand the core mechanism first. {P} works on one fundamental principle most people skip.",
             "magnifying glass close-up research detail",
             "CORE MECHANISM"),
            (f"Point Two. The gap between theory and practice in {p} is where most learners get lost.",
             "puzzle pieces connecting together solution",
             "THE MISSING LINK"),
            (f"Point Three. Real-world examples reveal patterns you cannot see from textbook descriptions alone.",
             "data visualization graph analytics rising",
             "PATTERNS IN DATA"),
            (f"Point Four. Once you understand {p} at this depth you will recognise it everywhere.",
             "lightbulb realisation person window morning",
             "THE AHA MOMENT"),
            (f"Point Five. The practical side of {p} is simpler than the theory once you remove the jargon.",
             "hands-on workshop practical demonstration",
             "SIMPLER THAN THOUGHT"),
        ],
        "documentary": [
            (f"Three independent investigators found the same pattern hidden inside {p}.",
             "investigator examining documents close-up",
             "THE EVIDENCE"),
            (f"Local communities felt the shift long before any institution acknowledged it.",
             "community people gathering town square",
             "THEY KNEW FIRST"),
            (f"The turning point came when an insider finally decided to speak about {p}.",
             "silhouette interview dramatic lighting dark",
             "THE TURNING POINT"),
            (f"What followed changed the accepted understanding of {p} permanently.",
             "dramatic storm sky time-lapse moving clouds",
             "EVERYTHING CHANGED"),
            (f"Experts who spent decades studying {p} say they are still finding new layers.",
             "scientists meeting conference serious",
             "STILL DISCOVERING"),
        ],
        "motivational": [
            (f"Most people quit {p} at the exact moment they are about to break through.",
             "athlete pushing exhaustion finish line",
             "DON'T QUIT NOW"),
            (f"Every person winning at {p} started from scratch made every mistake and kept going anyway.",
             "starting line road journey forward empty",
             "EVERYONE STARTED HERE"),
            (f"The system for {p} is simple. The discipline to execute it daily is the hard part.",
             "discipline routine morning habit focus",
             "SYSTEM BEATS MOTIVATION"),
            (f"You don't need more information about {p}. You need to make the decision right now.",
             "decision crossroads two paths person",
             "DECIDE RIGHT NOW"),
            (f"The compound effect of working on {p} every single day will astonish you in one year.",
             "sunrise mountain peak clouds horizon",
             "ONE YEAR FROM NOW"),
        ],
        "news": [
            (f"Industry insiders say the pace of change around {p} is faster than any public forecast predicted.",
             "executive boardroom serious discussion city",
             "FASTER THAN FORECAST"),
            (f"The raw numbers tell a story that mainstream headlines have consistently understated.",
             "statistics data graph rising analyst screen",
             "THE REAL NUMBERS"),
            (f"Both critics and supporters are finding unexpected common ground on {p}.",
             "debate discussion two people agreement",
             "BOTH SIDES AGREE"),
            (f"Analysts say this moment with {p} is structurally unlike any previous period on record.",
             "expert television interview serious light",
             "UNPRECEDENTED MOMENT"),
            (f"Early indicators suggest the situation around {p} will accelerate significantly over the next year.",
             "forecast chart projection trend upward",
             "WHAT COMES NEXT"),
        ],
    }

    bank = banks.get(style, banks["educational"])
    # Cycle through the bank if more items are requested than exist
    return [bank[i % len(bank)] for i in range(n)]


def _build_ending(p: str, P: str, style: str) -> tuple:
    """Returns (narration, visual_query, on_screen_text) for the CTA segment."""
    endings = {
        "viral":        (f"If this changed how you see {p}, follow for more. The next one hits harder.",
                         "person silhouette watching sunset horizon",
                         "FOLLOW FOR MORE"),
        "lifestyle":    (f"The secret to {p} is not a secret. It is just hard. And most people quit before it gets easy.",
                         "sunset dramatic golden sky mountain",
                         "DO THE HARD THING"),
        "educational":  (f"This is the depth of understanding most people never reach with {p}. Subscribe to go further.",
                         "person studying books confident smile",
                         "SUBSCRIBE FOR MORE"),
        "documentary":  (f"The story of {p} continues. Subscribe — this investigation is far from over.",
                         "camera reporter journalism city night",
                         "INVESTIGATION CONTINUES"),
        "motivational": (f"You have everything you need to start with {p} right now. The question is will you.",
                         "open road horizon golden light car",
                         "START RIGHT NOW"),
        "news":         (f"We are tracking {p} closely. Subscribe — this story is far from over.",
                         "reporter microphone camera breaking live",
                         "STAY INFORMED"),
    }
    return endings.get(style, endings["educational"])


def _fallback_shorts(topic: str, style: str, duration_sec: int) -> dict:
    """
    Local fallback script generator.

    Produces a fully structured Shorts script without the Claude API.
    Structure:
      1. HOOK           — stops the scroll
      2. CONTEXT        — frames why this matters
      3. INTERESTING FACTS (1–N, topic-specific)
      4. ENDING / CTA   — memorable close

    Topic keywords are extracted and injected into every visual_query
    so Pexels clip searches stay relevant to the actual subject.
    """
    p   = topic.strip().rstrip(".") or "this topic"
    P   = p.title()
    n   = _SEGS.get(style, _SEGS["educational"])(duration_sec)
    kw  = _extract_topic_keywords(topic)

    # How many fact segments fit between context (1) and ending (1)
    # minimum 1 fact, maximum fills the remaining slots
    n_facts = max(1, n - 3)   # slots: hook + context + facts + ending

    hook    = _build_hook(p, P, style)
    context = _build_context(p, P, style, kw)
    facts   = _build_facts(p, P, style, n_facts, kw)
    ending  = _build_ending(p, P, style)

    # Enrich every visual_query with a topic keyword for better Pexels hits
    def _enrich(vq: str, idx: int) -> str:
        if kw:
            return f"{kw[0]} {vq}" if kw[0].lower() not in vq.lower() else vq
        return vq

    segments = []

    segments.append({
        "id": 1, "type": "hook",
        "narration":     hook[0],
        "visual_query":  _enrich(hook[1], 0),
        "on_screen_text": hook[2],
    })

    segments.append({
        "id": 2, "type": "context",
        "narration":     context[0],
        "visual_query":  _enrich(context[1], 1),
        "on_screen_text": context[2],
    })

    for i, (narr, vq, txt) in enumerate(facts, start=3):
        segments.append({
            "id": i, "type": "fact",
            "narration":     narr,
            "visual_query":  _enrich(vq, i),
            "on_screen_text": txt,
        })

    segments.append({
        "id": len(segments) + 1, "type": "ending",
        "narration":     ending[0],
        "visual_query":  _enrich(ending[1], len(segments)),
        "on_screen_text": ending[2],
    })

    kw_str = ", ".join(kw) if kw else p
    return {
        "title":       f"{P}: What Nobody Tells You",
        "description": (f"The real story behind {p}. No filler, no fluff — just the "
                        f"truth. #{p.replace(' ', '')} #{style} #shorts #viral #facts"),
        "tags":        [p, P, style, "shorts", "viral", "facts",
                        "mindset", f"{p} tips", "motivation", kw_str],
        "segments":    segments,
        "_source":     "local_fallback",   # internal marker — not sent to frontend
    }



    p = topic.strip().rstrip(".") or "this topic"
    P = p.title()
    n = _SEGS.get(style, _SEGS["educational"])(duration_sec)

    BANKS = {
        # ── VIRAL ─────────────────────────────────────────────────
        "viral": [
            (f"Nobody tells you the REAL truth about {p}.",
             "aerial drone city night skyline lights", "THE REAL TRUTH"),
            (f"Here are {max(3,n-3)} uncomfortable truths about {p}.",
             "winding empty road cinematic horizon", f"{max(3,n-3)} HARD TRUTHS"),
            (f"Number One. Most people approach {p} COMPLETELY wrong. They focus on the outcome instead of the system.",
             "athlete training alone early morning", "WRONG APPROACH"),
            (f"Number Two. No one who mastered {p} did it without FAILURE first.",
             "person standing cliff edge dramatic clouds", "FAILURE IS REQUIRED"),
            (f"Number Three. The gap between KNOWING and DOING is where most people live permanently.",
             "empty dark road forest leading forward", "KNOWING VS DOING"),
            (f"Number Four. You will NEVER feel completely ready. Start anyway.",
             "luxury car coastal road golden hour", "START BEFORE READY"),
            (f"Number Five. The people winning at {p} are NOT smarter. They just started earlier.",
             "aerial drone ocean waves coastline", "THEY STARTED EARLIER"),
            (f"Number Six. Your environment shapes your results MORE than willpower ever will.",
             "modern architecture glass building forest mist", "ENVIRONMENT WINS"),
            (f"Number Seven. Ninety days of CONSISTENCY beats one week of intensity every single time.",
             "time-lapse city traffic night long exposure", "90 DAYS CHANGES ALL"),
            (f"Number Eight. The one thing about {p} most people skip is exactly why they fail.",
             "suspension bridge aerial misty morning", "THE ONE THING"),
            (f"Number Nine. The top one percent are not GIFTED. They are ruthlessly consistent.",
             "businessman walking glass city reflection", "1% MINDSET"),
            (f"Number Ten. Mastering {p} is the BEST investment you will ever make.",
             "sunrise dramatic mountain peak clouds", "BEST INVESTMENT EVER"),
            (f"If this changed how you see {p}, follow for more. The next one will hit even harder.",
             "person silhouette watching sunset alone horizon", "FOLLOW FOR MORE"),
        ],
        # ── LIFESTYLE ─────────────────────────────────────────────
        "lifestyle": [
            (f"Most people spend years on {p} and still wonder why nothing changes.",
             "person walking alone foggy bridge morning", "YEARS OF NOTHING"),
            (f"Here are the habits that ACTUALLY move the needle on {p}.",
             "early morning sunrise person stretching rooftop", "HABITS THAT WORK"),
            (f"Habit One. Start before you feel READY. Readiness is a lie your brain tells you to stay safe.",
             "runner starting empty road dawn", "START NOW"),
            (f"Habit Two. Track the process, not just the result. RESULTS are delayed processes.",
             "notebook journal pen writing morning coffee", "TRACK THE PROCESS"),
            (f"Habit Three. Your social circle is your CEILING. Upgrade who you spend time with.",
             "friends rooftop city view success laughing", "UPGRADE YOUR CIRCLE"),
            (f"Habit Four. Discomfort is the price of GROWTH. Get comfortable being uncomfortable.",
             "athlete cold water training discipline", "EMBRACE DISCOMFORT"),
            (f"Habit Five. Your morning sets the tone. WIN the morning and you win the day.",
             "morning gym weights dark early discipline", "WIN YOUR MORNING"),
            (f"The people who master {p} protect their ENERGY like money.",
             "person meditating ocean calm sunrise alone", "PROTECT YOUR ENERGY"),
            (f"The secret to {p} is not a secret. It is just HARD. And most people quit before it gets easy.",
             "silhouette person mountain top dramatic sky", "DO THE HARD THING"),
            (f"Follow for daily mindset shifts. Your future self will thank you.",
             "sunset dramatic golden sky horizon horizon", "FOLLOW FOR MORE"),
        ],
        # ── EDUCATIONAL ───────────────────────────────────────────
        "educational": [
            (f"Almost everything you've been taught about {p} misses the most important part.",
             "scientist researcher data screen laboratory", "MISSING THE POINT"),
            (f"Here's the framework that actually explains how {p} works.",
             "whiteboard diagram academic explanation clear", "THE REAL FRAMEWORK"),
            (f"Step One. Understand the CORE mechanism. {P} operates on one fundamental principle.",
             "magnifying glass close-up research detail", "CORE MECHANISM"),
            (f"Step Two. Most explanations skip the connective layer between theory and practice.",
             "puzzle pieces connecting together solution", "THE MISSING LINK"),
            (f"Step Three. The practical side of {p} is SIMPLER than the theory once you remove jargon.",
             "hands-on workshop practical demonstration", "SIMPLER THAN YOU THINK"),
            (f"Step Four. Real-world examples reveal patterns you cannot see from textbook descriptions.",
             "data visualization graph analytics rising", "PATTERNS IN DATA"),
            (f"Step Five. Once you understand {p} at this level you will recognise it EVERYWHERE.",
             "lightbulb realisation person window morning", "THE AHA MOMENT"),
            (f"This is the level of understanding most people never reach with {p}. Subscribe to go deeper.",
             "person studying books confident smile", "SUBSCRIBE FOR MORE"),
        ],
        # ── DOCUMENTARY ───────────────────────────────────────────
        "documentary": [
            (f"The story of {p} begins in a place most people never think to look.",
             "aerial drone wide mysterious landscape", "WHERE IT BEGAN"),
            (f"For decades the full picture of {p} remained hidden from public view.",
             "archival footage film grain dramatic light", "HIDDEN FOR DECADES"),
            (f"Three independent sources confirmed what investigators had long suspected.",
             "investigator examining documents close-up", "THE EVIDENCE"),
            (f"Local communities felt the impact long before any institution acknowledged it.",
             "community people gathering town square", "COMMUNITIES KNEW FIRST"),
            (f"The turning point came when an insider finally decided to speak.",
             "person silhouette interview dramatic lighting", "THE TURNING POINT"),
            (f"What followed changed our understanding of {p} permanently.",
             "dramatic storm sky time-lapse moving", "EVERYTHING CHANGED"),
            (f"Experts who spent decades on {p} are still debating what happens next.",
             "scientists meeting conference serious discussion", "WHAT COMES NEXT"),
            (f"The story continues. Subscribe to follow the full investigation.",
             "camera investigative journalism city night", "INVESTIGATION CONTINUES"),
        ],
        # ── MOTIVATIONAL ──────────────────────────────────────────
        "motivational": [
            (f"Everything between you and mastering {p} comes down to ONE decision.",
             "athlete mountain summit determination sunrise", "ONE DECISION AWAY"),
            (f"The people succeeding at {p} right now are NOT more gifted than you. They started earlier.",
             "focused person working desk early morning", "THEY STARTED EARLIER"),
            (f"Most people quit {p} at the EXACT moment they are about to break through.",
             "athlete pushing exhaustion finish line", "DON'T QUIT NOW"),
            (f"The compound effect of daily work on {p} cannot be appreciated until you live it.",
             "plant growing time-lapse progress daily", "COMPOUND EFFECT"),
            (f"Every person WINNING at {p} started from scratch made mistakes and kept going.",
             "starting line road journey forward", "EVERYONE STARTED HERE"),
            (f"The system for {p} is simple. The DISCIPLINE to execute it daily is the hard part.",
             "discipline routine morning habit focus", "SYSTEM OVER MOTIVATION"),
            (f"You don't need more information. You need to make the DECISION right now.",
             "decision crossroads two paths person", "DECIDE RIGHT NOW"),
        ],
        # ── NEWS ──────────────────────────────────────────────────
        "news": [
            (f"New developments in {p} are forcing experts to revise decades of assumptions.",
             "news studio anchor broadcast professional", f"BREAKING: {P[:20].upper()}"),
            (f"Three independent teams published findings pointing to the SAME conclusion.",
             "research scientist laboratory data analysis", "STUDIES CONVERGE"),
            (f"Industry insiders say the pace of change is FASTER than any public forecast.",
             "executive boardroom serious discussion city", "FASTER THAN EXPECTED"),
            (f"The raw numbers tell a story that headlines have CONSISTENTLY understated.",
             "statistics graph data rising analyst", "THE REAL NUMBERS"),
            (f"Both critics and supporters are finding unexpected COMMON GROUND.",
             "debate discussion two people agreement", "BOTH SIDES AGREE"),
            (f"Analysts say this moment is structurally UNLIKE any previous period.",
             "expert television interview serious light", "UNPRECEDENTED MOMENT"),
            (f"We are tracking this story. Subscribe — this is far from over.",
             "reporter microphone camera breaking live", "STAY INFORMED"),
        ],
    }

    bank = BANKS.get(style, BANKS["educational"])
    # Always use first (hook) and last (CTA); evenly sample body items
    if n >= len(bank):
        body = bank[1:-1]
    else:
        body_src = bank[1:-1]
        step = max(1, len(body_src) / max(1, n - 2))
        body = [body_src[min(int(i * step), len(body_src) - 1)]
                for i in range(n - 2)]

    segs = [{"id": 1, "type": "hook",
             "narration": bank[0][0],
             "visual_query": bank[0][1],
             "on_screen_text": bank[0][2]}]
    for i, (narr, vq, txt) in enumerate(body, 2):
        segs.append({"id": i, "type": "body",
                     "narration": narr, "visual_query": vq, "on_screen_text": txt})
    segs.append({"id": len(segs)+1, "type": "cta",
                 "narration": bank[-1][0],
                 "visual_query": bank[-1][1],
                 "on_screen_text": bank[-1][2]})

    return {
        "title": f"{P}: {len(segs)} Things Nobody Tells You",
        "description": (f"The truth about {p} — no fluff, no filler. "
                        f"#{p.replace(' ','')} #{style} #shorts #viral #mindset"),
        "tags": [p, P, style, "shorts", "viral", "motivation",
                 "mindset", f"{p} tips", "success", "learn"],
        "segments": segs,
    }
