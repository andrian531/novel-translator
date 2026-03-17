# Novel Translator

A tool for translating web novels (Chinese/Japanese/Korean) with context awareness, terminology consistency, and multi-engine support.

## Features

- **Multi-engine translation**: Gemini + Ollama, Gemini-only, Ollama-only, or specific local models
- **Context-aware**: Extracts characters, locations, terms, and modern loanwords via Gemini
- **Translation guide**: Per-project style guide (tone, naming conventions, key phrases)
- **Chapter context**: Rolling narrative summary passed between chapters for continuity
- **Rolling context**: Last sentences of previous chunk passed to next chunk within a chapter
- **Crash recovery**: Progress saved to temp file mid-translation
- **Explicit content support**: Professional translator role prompt for adult fiction
- **Website scraper**: Auto-explore and analyze novel websites, generate site configs
- **Search novel**: Browse rankings, search, scaffold project structure
- **Manual projects**: Copy raw chapters yourself, translate at your own pace

## Translation Engines

| Option | Analysis | Translator | Notes |
|--------|----------|------------|-------|
| 1 | Gemini | Ollama (all models, source-lang priority) | Hemat — Gemini only for guide |
| 2 | — | Ollama (all models) | Fully offline |
| 3 | Gemini | Gemini (Ollama as backup) | Best quality, uses API quota |
| 4 | Gemini | gemma3 only | Fast, consistent |
| 5 | Gemini | translategemma only | Best for explicit Chinese novels |

**Recommendation for explicit Chinese novels:** Use option 5 (translategemma). qwen models tend to self-censor and fall back, causing slower and inconsistent output. gemma3/translategemma are more faithful for this content type.

## Project Structure

```
novel-translator/
├── main.py                    # Main menu
├── engines/
│   ├── translator.py          # Translation pipeline (Gemini + Ollama)
│   ├── novel_search.py        # Search novels, scaffold projects
│   ├── site_analyzer.py       # Auto-analyze and add new websites
│   ├── scraper_manager.py     # Load scrapers from JSON configs
│   └── scrapers/
│       └── generic_scraper.py # Universal scraper (reads JSON config)
├── config/
│   ├── site_map.json          # List of active site configs
│   └── sites/                 # Per-site JSON configs
│       ├── 69shuba.json
│       └── bq730.json
└── manual_projects/
    └── [ProjectName]/
        ├── metadata.json          # Title, author, source URL, content rating
        ├── reference.json         # Characters, locations, terms (auto-filled by research)
        ├── translation_guide.json # Style guide (English, auto-generated)
        ├── chapter_context.json   # Rolling chapter summaries (English)
        └── chapters/
            ├── raw/               # Source chapters (copy manually or via scraper)
            └── translated/        # Output translations
```

## Getting Started

1. Run `python main.py`
2. **New Translate Project** — research a novel, generate guide and reference
3. Place raw chapter files in `manual_projects/[Name]/chapters/raw/`
4. **Manage Projects** — translate chapters with your chosen engine

## Adding a New Website

1. Menu → **Add Website**
2. Enter the homepage URL
3. Program auto-explores: homepage → listing → novel detail → chapter
4. Gemini generates a JSON config, saved to `config/sites/`

## Requirements

- Python 3.10+
- `gemini` CLI (Gemini API)
- [Ollama](https://ollama.com/) with at least one model installed
- `pip install -r requirements.txt`
