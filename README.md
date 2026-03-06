# AI YouTube Shorts Generator

Generate viral YouTube Shorts with AI script, neural voice, Pexels background, and animated captions.

## Stack
- **Backend**: FastAPI + FFmpeg + gTTS + Pexels API
- **AI Script**: Claude (Anthropic API) with fallback templates
- **Captions**: libass (8 styles × 3 placements)
- **Deploy**: Render.com

## Local Setup

```bash
pip install -r requirements.txt
python main.py
# Open http://127.0.0.1:8000
```

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (optional — falls back to templates) |
| `PEXELS_API_KEY` | Pexels video API key (optional — falls back to gradient) |
| `OUTPUT_DIR` | Video output path (default: `./output`) |
| `ALLOWED_ORIGINS` | Comma-separated allowed CORS origins |

## Background Music

Drop royalty-free MP3s into the `music/` folder named by mood:
`motivational.mp3`, `calm.mp3`, `thriller.mp3`, `educational.mp3`,
`comedy.mp3`, `documentary.mp3`, `horror.mp3`, `business.mp3`

Free tracks: [Pixabay Music](https://pixabay.com/music) · [Free Music Archive](https://freemusicarchive.org)
