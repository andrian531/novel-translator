# Novel Translator

A tool for translating web novels (Chinese/Japanese/Korean) with context awareness, terminology consistency, and multi-engine support.

## Features

- **Multi-engine translation**: Gemini + Ollama, Gemini-only, Ollama-only, or specific local models
- **Context-aware**: Extracts characters, locations, terms, and modern loanwords via Gemini
- **Character profiles**: Age, gender, aliases (with annotation on first use per chapter), and relationships (family, sect seniority, bets/wagers) — injected into every translation prompt
- **Translation guide**: Per-project style guide (tone, naming conventions, key phrases)
- **Chapter context**: Rolling narrative summary passed between chapters for continuity
- **Rolling context**: Last sentences of previous chunk passed to next chunk within a chapter
- **Crash recovery**: Progress saved to `temp/` inside each project folder — portable across machines
- **Explicit content support**: Professional translator role prompt for adult fiction
- **Website scraper**: Auto-explore and analyze novel websites, generate site configs; SPA sites (Vue/React `#/` routing) auto-detected and rendered via Playwright
- **Add Raw Chapter**: Input chapter URL → auto-fetch → save to raw/; loops for next URL automatically (Enter to exit); unknown mirror auto-detected from project metadata
- **Duplicate detection**: Project menu auto-detects raw chapters with identical content and flags them with `[!!]`
- **Re-translate chapter**: Pick any translated chapter and re-translate it with the latest reference; supports single or batch selection (range `1-5`, list `1,3,5`, or combination `1-3,7`), engine chosen once for the whole batch
- **Translation stats** `[D]`: Per-project dashboard — progress bar, translated/pending counts, engine breakdown from translation log, last translated chapter timestamp, total and average character counts
- **Auto chapter count**: Chapter count in metadata auto-updates when raw chapter files exceed the recorded total — no manual `[U]` needed
- **Quality scan**: After each translation, automatically checks for remaining CJK characters and warns if any are found
- **Translation log**: `translation_log.json` records which engine was used for each chapter, with timestamp and NLLB model info if applicable
- **Pinyin annotations toggle** `[P]`: Per-project toggle — ON adds romanized annotations on first occurrence of new terms; OFF strips pinyin from reference values and instructs the model to translate cultural terms directly, while still preserving proper nouns listed in reference
- **Term enforcement**: High-priority block injected at the end of every translation prompt listing key terms with mandatory verbatim usage
- **Continuity check**: Scan all translated chapters for character name inconsistencies (fuzzy match vs `character_profiles`); indexed by `character_appearances.json` to reduce false positives — only characters known to appear in a chapter are checked against it
- **Name spelling enforcement**: Character `romanized_name` injected as fixed spelling rule — Gemini warned not to create variant spellings
- **Sync Reference**: Detect changes in `reference.json` (vs snapshot), show full replacement report with line numbers, confirm once, apply across all translated chapters, write `sync_log.txt`
- **Search novel**: Browse rankings, search, scaffold project structure; results filtered by personal settings (exclude tags, display language)
- **Search settings**: Auto-configured on first use, saved to `config/settings.json` (gitignored)
- **Manual projects**: Copy raw chapters yourself, translate at your own pace

## Translation Engines

| Option | Analysis | Translator | Notes |
|--------|----------|------------|-------|
| 1 | Gemini | Ollama (all models, source-lang priority) | Efficient — Gemini only for guide |
| 2 | — | Ollama (all models) | Fully offline |
| 3 | Gemini | Gemini (Ollama as backup) | Best quality, uses API quota |
| 4 | Gemini | gemma3 only | Fast, consistent |
| 5 | Gemini | translategemma only | Best for explicit Chinese novels |
| 6 *(exp)* | Gemini | NLLB → Gemini refine | ⚠ Not recommended for CJK — pivot causes info loss |
| 7 *(exp)* | Gemini | NLLB → translategemma refine | ⚠ Not recommended for CJK |
| 8 *(exp)* | Gemini | NLLB → gemma3 refine | ⚠ Not recommended for CJK |

**Recommendation for explicit Chinese novels:** Use option 5 (translategemma). qwen models tend to self-censor and fall back, causing slower and inconsistent output. gemma3/translategemma are more faithful for this content type.

**NLLB pivot pipeline (modes 6–8):** Not recommended for CJK (Chinese/Japanese/Korean) novels. Gemini reads CJK natively — adding an NLLB intermediate step (source→English) introduces a "telephone game" information loss with no benefit. NLLB pivot is only useful when the source language is one Gemini handles poorly. Requires `facebook/nllb-200-3.3B` (or smaller) downloaded via `install.bat`.

## Project Structure

```
novel-translator/
├── main.py                    # Main menu
├── engines/
│   ├── translator.py          # Translation pipeline (Gemini + Ollama + NLLB pivot)
│   ├── nllb.py                # NLLB local model wrapper (name placeholders, CJK scan)
│   ├── novel_search.py        # Search novels, scaffold projects
│   ├── site_analyzer.py       # Auto-analyze and add new websites
│   ├── scraper_manager.py     # Load scrapers from JSON configs
│   ├── settings_manager.py    # Search preferences (language, exclude tags)
│   └── scrapers/
│       └── generic_scraper.py # Universal scraper (reads JSON config)
├── config/
│   ├── site_map.json          # List of active site configs
│   ├── settings.example.json  # Template for settings.json (gitignored)
│   └── sites/                 # Per-site JSON configs
│       ├── 69shuba.json
│       └── bq730.json
├── reader/
│   ├── backend/
│   │   ├── main.py            # FastAPI — serves novels from manual_projects/
│   │   ├── requirements.txt
│   │   └── run.bat            # Double-click to start backend
│   └── frontend/              # Vue 3 + Vite + Tailwind
│       └── src/
│           ├── views/
│           │   ├── HomeView.vue    # Novel grid
│           │   ├── NovelView.vue   # Novel info + chapter list
│           │   └── ChapterView.vue # Chapter reader with sidebar TOC
│           └── router/index.js
└── manual_projects/
    └── [ProjectName]/
        ├── metadata.json              # Title, author, source URL, content rating
        ├── reference.json             # Characters, locations, terms, character_profiles
        ├── reference_snapshot.json    # Snapshot of reference at last sync (diff baseline)
        ├── character_appearances.json # Per-chapter index of which characters appear (continuity check)
        ├── translation_guide.json     # Style guide (English, auto-generated)
        ├── chapter_context.json       # Rolling chapter summaries (capped at 5 entries, 350 chars each)
        ├── translation_log.json       # Per-chapter engine log (engine, timestamp, nllb_model)
        ├── sync_log.txt               # Append-only log of all Sync Reference runs
        ├── temp/                      # Crash recovery (gitignored, portable with project)
        │   └── translate_progress.json
        └── chapters/
            ├── raw/                   # Source chapters (copy manually or via [A] Add Raw)
            └── translated/            # Output translations
```

## reference.json — character_profiles

Each character entry includes:
- **age** — integer or null
- **gender** — male/female/unknown
- **aliases** — alternative names/titles with context; annotated on first use per chapter only
- **relationships** — who calls whom what, and why (age, sect seniority, bet/wager, rank, family)

Research re-run includes already-translated chapters as consistency reference — existing names and terms are preserved.

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

## Web Reader

Read translated novels in a browser.

**Backend** (FastAPI):
```bash
cd reader/backend
# double-click run.bat  OR:
pip install -r requirements.txt
uvicorn main:app --reload
# → http://localhost:8000
```

**Frontend** (Vue + Tailwind):
```bash
cd reader/frontend
npm install
npm run dev
# → http://localhost:5173
```

The frontend proxies `/api` to `localhost:8000`. Displays translated novels with `title_translated` (target language title) when available, falling back to the original title.

Reader features:
- Collapsible sidebar (left) listing all chapters, current chapter highlighted
- Dark mode toggle — respects system preference on first load, saved to localStorage
- Font size controls (`A−` / `A+`) in chapter header, saved to localStorage
- Keyboard navigation: `←` / `→` arrow keys for prev/next chapter
- Reading progress saved per novel — "Continue reading" shortcut on HomeView and NovelView

## License

MIT License — see [LICENSE](LICENSE)

## Requirements

- Python 3.10+
- `gemini` CLI (Gemini API)
- [Ollama](https://ollama.com/) with at least one model installed
- `pip install -r requirements.txt`
