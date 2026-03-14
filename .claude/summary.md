# Novel Translator — Project Summary

> Last updated: 2026-03-14

---

## Overview

CLI tool to translate CJK (Chinese/Japanese/Korean) web novels into a target language (default: Indonesian).
Dual-engine architecture:
- **Gemini CLI** — director/analyst: extracts characters, locations, terms from raw chapters
- **Ollama** — primary translation engine (local, offline)
  Model priority: `gemma3 > gemma2 > gemma > [other non-dolphin]`
  Fallback: `dolphin-mistral > dolphin-llama3 > dolphin`

---

## Main File Structure

```
novel-translator/
├── main.py                        # CLI entrypoint, menus, project management
├── engines/
│   ├── translator.py              # Translation pipeline (Gemini + Ollama)
│   ├── project_manager.py         # Project management, scaffolding, metadata
│   ├── scraper_manager.py         # Web novel scraper
│   └── logger.py                  # Centralized logger
├── config/                        # Global configuration
├── projects/                      # Scraper projects
└── manual_projects/               # Manual translation projects (gitignored)
```

---

## Implemented Features

### 1. Engine Mode Selection (main.py)
Three engine options with accurate descriptions:
```
1. Gemini + Ollama fallback  (Gemini analyzes, Ollama translates — token-efficient)
2. Ollama only               (local, offline, no rate limits)
3. Gemini only               (Gemini for everything — token-heavy, rate limit risk)
```

### 2. Reference System (translator.py + project_manager.py)
Per-project `reference.json` with 4 sections:
- `characters` — character names: `{"李明": "Li Ming"}`
- `locations` — places: `{"长安城": "Kota Chang'an"}`
- `terms` — special terms: `{"修炼": "kultivasi"}`
- `modern_terms` — English loanwords ONLY: `{"直播": "live stream", "界面": "interface"}`

### 3. Annotation Rules (translator.py — annotation_rule)
Applied in both translation prompt and analysis prompt:
1. Annotate ONLY on FIRST occurrence; later occurrences: no parentheses
2. Chinese slang/concepts with a good target-lang equivalent: **translate DIRECTLY** — no romanized form, no annotation
   - e.g. `躺平→rebahan`, `内卷→persaingan ketat` — NEVER write `Tang Ping (rebahan)` or `Tang Ping (Lying flat)`
3. Geographic suffixes: **translate directly, no annotation**
   - `城=Kota`, `殿=Aula`, `宫=Istana`, `河/水=Sungai`, `山=Gunung`, `门=Gerbang`
   - e.g. `Kota Chang'an`, `Aula Xiande`, `Sungai Wei` — never leave suffix romanized
4. For proper nouns / cultivation concepts with no direct translation: `Romanized (Meaning in target lang)` on first occurrence
   - e.g. `Dong Gong (Istana Timur)`, `Dan Tian (Pusat Energi)` — meaning MUST be in target language, never English
5. WRONG examples: `Era Wude (Era Wude)`, `System (Sistem)`, `Tang Ping (rebahan)`, `Tang Ping (Lying flat)`

### 4. modern_terms Rule
Only for **English loanwords** used in modern novel context (system, game, streaming):
- `host`, `live stream`, `interface`, `quest`, `level`, `boss`
- NOT for Chinese slang: `躺平` → goes in `terms` as `rebahan` (translated directly)

### 5. Chapter Scaffolding (project_manager.py — scaffold_raw_chapters)
On project init / chapter count update:
- Creates empty files `chapter_001.txt` through `chapter_NNN.txt`
- Digit width adapts to total chapter count (minimum 3 digits)
- On count reduction: **only deletes empty files** (0 bytes), never deletes filled chapters
- Returns: `(created, deleted)` tuple

### 6. Chapter Status Markers (main.py — manual_project_menu)
Three-state markers in chapter list:
```
  [✓] already translated  [x] empty file  [ ] pending translation
   1. [✓] chapter_001.txt
   2. [x] chapter_002.txt
   3. [ ] chapter_003.txt
```

### 7. [U] Update Chapter Count Menu (main.py)
- Prompts for new total chapter count
- Runs `scaffold_raw_chapters()` to create/delete files accordingly
- Updates `total_chapters` in project metadata

### 8. Research Spread Algorithm (main.py — _select_spread)
Deterministic, interval-based — Gemini is NOT used to select chapters:
```
3 head chapters + mid zone samples (1 per 50 chapters in mid zone, max 15) + 2 tail chapters
```
- ≤ 5 chapters: take all
- Small novel (mid < 10): 1 mid sample if any
- Large novel (500+ chapters): up to 20 total samples
- Only **non-empty** chapters are processed (filtered before spread)

### 9. Empty Chapter Filter Before Research (main.py)
```python
nonempty_chapters = [f for f in chapters if not pm.is_raw_chapter_empty(project_id, f)]
```
Prevents Gemini from hanging/getting stuck when most chapters are still empty (0 bytes).

### 10. Untranslated CJK Detection + Retry (translator.py)
Post-translation validation: if translated output still contains >3 CJK characters, it means some text was not translated (common with classical Chinese / 文言文).

**Retry flow in `translate_with_gemini_primary`:**
1. Try Gemini → if CJK remains in output → fall back to Ollama
2. Try each Ollama model → if CJK remains → try next model, save as candidate
3. If all Ollama models have CJK → retry Gemini with **classical note** (`文言文` warning in prompt)
4. If still failing → use best Ollama candidate even with remaining CJK
5. Engine label: `Gemini`, `Ollama(model)`, `Gemini(klasik)`, `Ollama(model)+CJK`

**Retry flow in `translate_with_ollama_only`:**
1. Try each Ollama model → if CJK remains → try next model
2. If all have CJK → use first candidate (best available)

**Detection function:**
```python
def _has_untranslated_cjk(text):
    # Returns True if >3 CJK characters found in translated output
    # Covers: CJK Unified (U+4E00-9FFF), Extension A (U+3400-4DBF),
    #         Hiragana/Katakana (U+3040-30FF), Hangul (U+AC00-D7AF)
```

---

## Optimizations & Fixes Applied

| # | Problem | Solution |
|---|---------|----------|
| 1 | Redundant annotation `Era Wude (Era Wude)` | Rule: don't annotate if translation equals original name |
| 2 | Annotation in English `Tang Ping (Lying flat)` | Rule: parenthetical meaning MUST be in target language |
| 3 | `Chang'an Cheng (Kota Chang'an)` — suffix not translated | Rule: translate geographic suffix directly |
| 4 | `System (Sistem)` — unnecessary annotation | Rule: English loanwords recognizable to readers → no annotation |
| 5 | Research stuck at [1/3] | Filter empty chapters + replace Gemini selection with deterministic spread |
| 6 | Mid zone too sparse for large novels | Interval-based: 1 sample per 50 chapters, max 15 |
| 7 | Engine description was inaccurate | Fixed: Gemini+Ollama = token-efficient, not Gemini-only |
| 8 | CJK remaining in output (classical/archaic text) | Post-translation CJK detection + retry cascade |
| 9 | `modern_terms` filled with Chinese slang | Clarified: modern_terms = English loanwords ONLY |

---

## Pending / Not Yet Implemented

### P1 — High Priority
- [ ] **Fix bq730 scraper "Total Rankings"** — chapter fetch broken
- [ ] **Fix shuba_69 scraper** — chapter fetch broken

### P2 — Medium Priority
- [ ] **Verify `scaffold_raw_chapters` regex bug** — potential bug in regex pattern:
  ```python
  m = _re.match(r'^chapter_(\d+)\.txt, fname, _re.IGNORECASE)
  # closing quote may be misplaced — needs verification
  ```
- [ ] **Manual test of CJK retry logic** — not yet tested with real 文言文 chapter
- [ ] **Report CJK chunks in translation summary** — show which chunks still had CJK after all retries

### P3 — Nice to Have
- [ ] **Auto dedup reference after analysis** — `dedup_reference()` exists but not called automatically
- [ ] **Visual progress bar for chunks** — currently plain text `[1/3] Chunk 2/10 → Gemini`
- [ ] **Export translation to EPUB/PDF**

---

## .gitignore

```
manual_projects/
manual_translations/
scraper_logs/
temp_single_translate.txt
```

---

## Architecture Notes

- **Gemini CLI** called via `subprocess` (`gemini` shell command) — not direct API
- **Ollama** called via REST API `http://localhost:11434` + subprocess `ollama run`
- Translation chunks: default 2000 chars, split by paragraph boundaries
- Reference block built once per chapter, reused across all chunks
- Full logs written to `scraper_logs/` (gitignored)
