"""
novel_search.py — Search novels from configured sites using AI filter.
When a novel is selected, creates manual_projects folder structure + metadata + empty raw files.
"""
import json
import os
import re
import subprocess
from datetime import datetime

from engines.logger import logger

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANUAL_DIR = os.path.join(_BASE_DIR, "manual_projects")
TEMP_DIR = os.path.join(_BASE_DIR, "temp")
SEARCH_CACHE_FILE = os.path.join(TEMP_DIR, "search_cache.json")

PAGE_SIZE = 10


# ------------------------------------------------------------------
# Gemini helpers
# ------------------------------------------------------------------

def _run_gemini(prompt, timeout=120):
    try:
        result = subprocess.run(
            "gemini",
            input=prompt,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.warning(f"[novel_search] Gemini returncode={result.returncode} stderr={result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning(f"[novel_search] Gemini timeout after {timeout}s")
    except Exception as e:
        logger.error(f"[novel_search] Gemini error: {e}")
    return None


def _parse_json_array(text):
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError as e:
        logger.warning(f"[novel_search] JSON parse error: {e}")
    return None


# ------------------------------------------------------------------
# Search result cache
# ------------------------------------------------------------------

def _save_search_cache(results, query, target_lang, enriched_pages=None):
    os.makedirs(TEMP_DIR, exist_ok=True)
    cache = {
        "query": query,
        "target_lang": target_lang,
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "results": results,
        "enriched_pages": enriched_pages or [],
    }
    with open(SEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _load_search_cache():
    if not os.path.exists(SEARCH_CACHE_FILE):
        return None
    try:
        with open(SEARCH_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _update_cache_page_results(cache, page_idx, updated_novels):
    """Write enriched page results back to cache file."""
    start = page_idx * PAGE_SIZE
    end = start + PAGE_SIZE
    cache["results"][start:end] = updated_novels
    if page_idx not in cache.get("enriched_pages", []):
        cache.setdefault("enriched_pages", []).append(page_idx)
    with open(SEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Search + filter
# ------------------------------------------------------------------

def _collect_novels_from_site(scraper, site_name, max_pages=2):
    """
    Collect novels from all rankings on a site (max max_pages per ranking).
    Returns deduplicated list by URL.
    """
    rankings = scraper.get_supported_rankings()
    if not rankings:
        logger.warning(f"[novel_search] {site_name}: no rankings configured")
        return []

    all_novels = {}
    # Priority order: Completed > Monthly Popular > All-time > rest
    priority_order = ["Completed Novels", "Monthly Popular", "All-time Popular",
                      "完本小说", "都市言情", "玄幻奇幻"]
    rank_keys = sorted(rankings.keys(), key=lambda k: (
        0 if k in priority_order[:2] else
        1 if k in priority_order[2:4] else
        2 if k in priority_order[4:] else 3
    ))
    # Limit to 3 rankings to avoid long wait
    rank_keys = rank_keys[:3]

    # Keywords that indicate a ranking contains only completed novels
    _COMPLETED_RANK_HINTS = {"completed", "complete", "full", "finish", "完本", "完结", "tamat"}

    for rank_name in rank_keys:
        rank_is_completed = any(h in rank_name.lower() for h in _COMPLETED_RANK_HINTS)
        print(f"    -> {site_name} / {rank_name}...", end=" ", flush=True)
        collected = 0
        for page in range(1, max_pages + 1):
            try:
                novels = scraper.get_ranking_list(rank_name, page)
                for n in novels:
                    url = n.get("url", "")
                    if url and url not in all_novels:
                        # Use ranking name as reliable status hint when listing page has none
                        if rank_is_completed and not n.get("status_raw"):
                            n["status_raw"] = "完结"
                        all_novels[url] = n
                collected += len(novels)
                if not novels:
                    break
            except Exception as e:
                logger.warning(f"[novel_search] {site_name}/{rank_name} page {page} error: {e}")
                break
        print(f"{collected} novels")

    return list(all_novels.values())


def _filter_and_translate_with_gemini(novels, user_prompt, target_lang):
    """
    Send novel list to Gemini with user criteria.
    Gemini filters + translates title & synopsis.
    Returns list: [{"original_title", "translated_title", "synopsis", "url", "status_translated", "site", "author"}]
    """
    if not novels:
        return []

    # Compress data for Gemini (only essential fields)
    batch = [
        {
            "i": i,
            "title": n.get("title", ""),
            "author": n.get("author", ""),
            "synopsis": n.get("synopsis", "")[:200],
            "url": n.get("url", ""),
            "site": n.get("site", ""),
            "status_raw": n.get("status_raw", ""),
            "chapter_count": n.get("chapter_count", ""),
            "last_update": n.get("last_update", ""),
        }
        for i, n in enumerate(novels)
    ]
    batch_json = json.dumps(batch, ensure_ascii=False)

    prompt = (
        f"User is looking for: \"{user_prompt}\"\n"
        f"Language to display results: {target_lang}\n\n"
        f"From the novel list below, select ALL novels that match the user's search criteria.\n"
        f"Return every matching novel, ranked by relevance. If nothing matches, return an empty array.\n\n"
        f"For each selected novel:\n"
        f"- Translate 'title' to {target_lang}\n"
        f"- Translate 'synopsis' to {target_lang} (natural, concise, max 3 sentences)\n"
        f"- Keep 'url', 'author', 'site', 'chapter_count', 'last_update' exactly as-is\n"
        f"- Keep 'i' (index) exactly as-is\n"
        f"- Add 'status_translated': translate 'status_raw' to {target_lang}. "
        f"Use 'Completed' / 'Ongoing' (or equivalent in {target_lang}). "
        f"IMPORTANT: If 'status_raw' is empty or blank, set 'status_translated' to empty string \"\". "
        f"Do NOT guess or infer status from title or synopsis — only translate what is explicitly in 'status_raw'.\n"
        f"- Add 'content_rating': assess the content based on title and synopsis.\n"
        f"  Use ONLY one of these values:\n"
        f"  'general'  — safe for all audiences\n"
        f"  'mature'   — violence, dark themes, but no explicit sexual content\n"
        f"  'explicit' — contains explicit sexual content (harem, adult, r18, NTR, monster girl, goblin+female, etc.)\n"
        f"  When in doubt from synopsis alone, use 'mature'. Only use 'explicit' if synopsis clearly implies adult content.\n\n"
        f"Rules:\n"
        f"- Character names: keep in Pinyin (e.g. 夏青 -> Xia Qing)\n"
        f"- Genre tags in brackets: translate naturally\n"
        f"- Return ONLY a valid JSON array — no markdown, no explanation\n\n"
        f"Output format:\n"
        f"[{{\"i\": 0, \"original_title\": \"...\", \"translated_title\": \"...\", "
        f"\"author\": \"...\", \"synopsis\": \"...\", \"url\": \"...\", \"site\": \"...\", "
        f"\"status_translated\": \"...\", \"chapter_count\": \"...\", \"last_update\": \"...\", "
        f"\"content_rating\": \"general|mature|explicit\"}}]\n\n"
        f"Input novels:\n{batch_json}"
    )

    print(f"  [*] Filtering & translating results with Gemini...", end="\r", flush=True)
    result = _run_gemini(prompt, timeout=120)
    if not result:
        print(f"  [!] Gemini did not respond. Showing raw results.      ")
        return [{"original_title": n["title"], "translated_title": n["title"],
                 "author": n.get("author", ""), "synopsis": n.get("synopsis", ""),
                 "url": n["url"], "site": n.get("site", ""), "status_translated": ""}
                for n in novels[:10]]

    filtered = _parse_json_array(result)
    if not filtered:
        print(f"  [!] Failed to parse Gemini output.                      ")
        return []

    print(f"  [OK] Gemini found {len(filtered)} relevant novels.         ")
    return filtered


_COMPLETED_STATUS_KEYWORDS = {"完结", "完本", "completed", "tamat", "selesai", "finish"}
_ONGOING_STATUS_KEYWORDS = {"连载", "连载中", "ongoing", "berlangsung", "sedang", "active"}


def _map_status(raw_status):
    """Map raw status string to canonical English 'Completed' or 'Ongoing'."""
    low = raw_status.lower()
    if any(k in low for k in _COMPLETED_STATUS_KEYWORDS):
        return "Completed"
    if any(k in low for k in _ONGOING_STATUS_KEYWORDS):
        return "Ongoing"
    return raw_status  # Return as-is if unknown


def _enrich_with_details(results, manager):
    """
    Fetch novel detail pages for ALL filtered results to get reliable
    chapter count and status. Detail page data always overrides listing/Gemini values.
    """
    if not results:
        return results

    print(f"\n  [*] Fetching detail pages for {len(results)} novel(s) to verify chapter/status...")

    for n in results:
        novel_url = n.get("url", "")
        site_name = n.get("site", "")
        if not novel_url or not site_name:
            continue

        scraper = manager.get_scraper_by_name(site_name)
        if not scraper:
            continue

        print(f"    -> {n.get('original_title', novel_url)[:45]}...", end=" ", flush=True)
        try:
            details = scraper.get_novel_details(novel_url)
            if details:
                # Always override chapter count from detail page
                ch = details.get("chapter_count", 0)
                if ch:
                    n["chapter_count"] = str(ch)

                # Always override last_update from detail page
                upd = details.get("last_update", "")
                if upd:
                    n["last_update"] = upd

                # Always override status from detail page (more reliable than listing/Gemini)
                raw_status = details.get("status", "")
                if raw_status:
                    n["status_translated"] = _map_status(raw_status)

                print(f"ch={n.get('chapter_count', '-')} | status={n.get('status_translated', '-')}")
            else:
                print("no data")
        except Exception as e:
            logger.warning(f"[novel_search] enrich detail error for {novel_url}: {e}")
            print(f"error: {e}")

    return results


def _display_results(page_results, page_num, total_pages, total_count, user_prompt, target_lang):
    """Display one page of search results."""
    print("\n" + "=" * 60)
    print(f'  SEARCH RESULTS: "{user_prompt}"')
    print(f"  Language: {target_lang} | Found: {total_count} novels | Page {page_num}/{total_pages}")
    print("  '-' means data not available from site listing.")
    print("=" * 60)

    _RATING_BADGE = {"explicit": "[18+]", "mature": "[M]", "general": ""}

    for local_i, n in enumerate(page_results, 1):
        global_i = (page_num - 1) * PAGE_SIZE + local_i
        badge = _RATING_BADGE.get(n.get("content_rating", ""), "")
        print(f"\n[{local_i}] {n.get('original_title', '')}  ({n.get('translated_title', '')}) {badge}")
        print(f"    Author  : {n.get('author', 'Unknown')}")

        status = n.get("status_translated", "") or "-"
        chapters = n.get("chapter_count", "") or "-"
        updated = n.get("last_update", "") or "-"
        print(f"    Status: {status}  |  Chapters: {chapters}  |  Updated: {updated}  |  Source: {n.get('site', '-')}")

        if n.get("synopsis"):
            syn = n["synopsis"]
            words = syn.split()
            line = "    Synopsis: "
            for word in words:
                if len(line) + len(word) + 1 > 72:
                    print(line)
                    line = "              " + word + " "
                else:
                    line += word + " "
            if line.strip():
                print(line)
        print(f"    URL     : {n.get('url', '')}")
        print("-" * 60)

    nav = []
    if page_num < total_pages:
        nav.append("N=Next")
    if page_num > 1:
        nav.append("B=Back")
    nav.append("1-10=Select")
    nav.append("Q=Quit")
    print(f"\n  Navigation: {' | '.join(nav)}")


# ------------------------------------------------------------------
# Project scaffold
# ------------------------------------------------------------------

def _slugify(text):
    """Create a folder-safe slug from title."""
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text.strip())
    return text[:60]


def _suggest_project_names(original_title, synopsis, author):
    """
    Ask Gemini to suggest 3 short English folder names for the project.
    Returns list of slugified name strings. Falls back to slugified title on failure.
    """
    prompt = (
        f"Suggest 3 short English project folder names for this novel.\n"
        f"Original title: {original_title}\n"
        f"Author: {author}\n"
        f"Synopsis: {synopsis[:300]}\n\n"
        f"Rules:\n"
        f"- Each name must be in English only\n"
        f"- Short: 2-5 meaningful words\n"
        f"- Use Title_Case with underscores (e.g. Supreme_Martial_God)\n"
        f"- No punctuation, no numbers\n"
        f"- Capture the novel's core theme, not a literal translation\n"
        f"- Return ONLY a JSON array of 3 strings, nothing else\n\n"
        f"Example output: [\"Supreme_Martial_God\", \"Eternal_War_Saint\", \"Path_of_the_Sovereign\"]"
    )
    result = _run_gemini(prompt, timeout=30)
    if result:
        names = _parse_json_array(result)
        if names and isinstance(names, list):
            return [_slugify(str(n)) for n in names if n][:3]
    return []


def _scaffold_project(novel_info, details, target_lang="Indonesian"):
    """
    Create manual_projects/{project_name}/ folder structure.
    Gemini suggests 3 English folder names; user picks one or enters custom.
    """
    original_title = novel_info.get("original_title", details.get("title", ""))
    synopsis = novel_info.get("synopsis", details.get("synopsis", ""))
    author = novel_info.get("author", details.get("author", ""))

    print("\n  [*] Asking AI to suggest project folder names...")
    suggestions = _suggest_project_names(original_title, synopsis, author)

    fallback = _slugify(novel_info.get("translated_title", "") or original_title)
    if not suggestions:
        suggestions = [fallback]

    print("\n  Select project folder name:")
    for i, name in enumerate(suggestions, 1):
        print(f"    {i}. {name}")
    print(f"    C. Enter custom name")
    print(f"  (Enter = option 1: '{suggestions[0]}')")

    raw = input("  > ").strip()
    if not raw:
        project_name = suggestions[0]
    elif raw.upper() == "C":
        custom = input("  Custom name: ").strip()
        project_name = _slugify(custom) if custom else suggestions[0]
    elif raw.isdigit() and 1 <= int(raw) <= len(suggestions):
        project_name = suggestions[int(raw) - 1]
    else:
        project_name = _slugify(raw) if raw else suggestions[0]

    project_dir = os.path.join(MANUAL_DIR, project_name)
    if os.path.exists(project_dir):
        print(f"  [!] Folder '{project_name}' already exists.")
        overwrite = input("  Continue and overwrite? (y/n): ").strip().lower()
        if overwrite != "y":
            print("  [!] Cancelled.")
            return None

    raw_dir = os.path.join(project_dir, "chapters", "raw")
    translated_dir = os.path.join(project_dir, "chapters", "translated")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(translated_dir, exist_ok=True)

    # metadata.json
    metadata = {
        "id": project_name,
        "title": original_title,
        "english_name": project_name,
        "source_lang": details.get("source_language", novel_info.get("site_source_lang", "Chinese")),
        "target_lang": target_lang,
        "synopsis": details.get("synopsis", ""),
        "source_url": novel_info.get("url", details.get("url", "")),
        "site": novel_info.get("site", ""),
        "author": novel_info.get("author", details.get("author", "")),
        "created_at": datetime.now().isoformat(),
        "type": "manual",
        "title_translated": novel_info.get("translated_title", ""),
        "synopsis_translated": novel_info.get("synopsis", ""),
        "total_chapters": details.get("chapter_count", 0),
        "content_rating": novel_info.get("content_rating", "general"),
    }
    _write_json(os.path.join(project_dir, "metadata.json"), metadata)

    _write_json(os.path.join(project_dir, "reference.json"), {
        "characters": {},
        "locations": {},
        "terms": {},
        "modern_terms": {}
    })
    _write_json(os.path.join(project_dir, "translation_guide.json"), {})
    _write_json(os.path.join(project_dir, "chapter_context.json"), {})

    # Create empty raw chapter files with source URL as comment
    chapters = details.get("chapters", [])
    chapter_count = len(chapters) or details.get("chapter_count", 0)

    if not chapter_count:
        print(f"\n  [!] Could not fetch chapter list automatically.")
        print(f"  How many empty chapter files to create? (Enter = skip):")
        raw_count = input("  > ").strip()
        if raw_count.isdigit() and int(raw_count) > 0:
            chapter_count = int(raw_count)
        else:
            chapter_count = 0

    created_files = 0
    for idx in range(chapter_count):
        filename = f"chapter_{idx + 1:03d}.txt"
        filepath = os.path.join(raw_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                if idx < len(chapters):
                    ch = chapters[idx]
                    f.write(f"# SOURCE: {ch.get('url', '')}\n")
                    f.write(f"# TITLE: {ch.get('title', '')}\n")
                    f.write(f"# Delete the # lines above, then paste the chapter content here\n\n")
            created_files += 1

    return {
        "project_dir": project_dir,
        "project_name": project_name,
        "chapter_count": chapter_count,
        "created_files": created_files,
    }


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# Language picker
# ------------------------------------------------------------------

_LANGUAGES = [
    ("ID", "Indonesian"),
    ("EN", "English"),
    ("ZH", "Chinese (Simplified)"),
    ("JA", "Japanese"),
    ("KO", "Korean"),
    ("MS", "Malay"),
    ("TH", "Thai"),
    ("VI", "Vietnamese"),
    ("ES", "Spanish"),
    ("FR", "French"),
    ("DE", "German"),
    ("PT", "Portuguese"),
    ("AR", "Arabic"),
    ("TR", "Turkish"),
    ("RU", "Russian"),
]

def _pick_language(default_code="ID"):
    """
    Show a numbered language list.
    User can enter a number OR a country code (e.g. ID, EN, ZH).
    Returns the full language name string.
    """
    code_map = {code: name for code, name in _LANGUAGES}
    default_name = code_map.get(default_code, "Indonesian")

    print("  Select display language for results:")
    cols = 3
    rows = (len(_LANGUAGES) + cols - 1) // cols
    for row in range(rows):
        line = ""
        for col in range(cols):
            idx = col * rows + row
            if idx < len(_LANGUAGES):
                code, name = _LANGUAGES[idx]
                entry = f"  {idx + 1:2}. [{code}] {name}"
                line += f"{entry:<28}"
        print(line)
    print()
    print(f"  Enter number or country code (Enter = {default_code} / {default_name}):")
    raw = input("  > ").strip().upper()

    if not raw:
        return default_name

    # Try as number
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(_LANGUAGES):
            return _LANGUAGES[n - 1][1]
        print(f"  [!] Invalid number. Using default: {default_name}")
        return default_name

    # Try as country code
    if raw in code_map:
        return code_map[raw]

    print(f"  [!] Unknown code '{raw}'. Using default: {default_name}")
    return default_name


# ------------------------------------------------------------------
# Main flow
# ------------------------------------------------------------------

def _enrich_page_if_needed(cache, page_idx, manager):
    """
    Lazily enrich a single page's novels with detail-page data if not yet done.
    Updates cache in-place and writes back to disk.
    """
    if page_idx in cache.get("enriched_pages", []):
        return  # already enriched

    start = page_idx * PAGE_SIZE
    end = start + PAGE_SIZE
    page_novels = cache["results"][start:end]

    enriched = _enrich_with_details(page_novels, manager)
    _update_cache_page_results(cache, page_idx, enriched)


def _handle_novel_selection(local_choice, page_idx, cache, manager, target_lang):
    """
    Handle a numeric selection (1-10) on the current page.
    Returns True to stay in loop, False to exit.
    """
    start = page_idx * PAGE_SIZE
    page_novels = cache["results"][start:start + PAGE_SIZE]

    try:
        local_idx = int(local_choice) - 1
        if not (0 <= local_idx < len(page_novels)):
            raise ValueError
    except ValueError:
        print(f"  [!] Invalid selection. Enter 1-{len(page_novels)}, N, B, or Q.")
        return True

    selected = page_novels[local_idx]
    novel_url = selected.get("url", "")
    site_name = selected.get("site", "")

    if not novel_url:
        print("  [!] Novel URL not available.")
        return True

    print(f"\n  Fetching novel details from {novel_url}...")
    scraper = manager.get_scraper_by_name(site_name)
    details = {}
    if scraper:
        try:
            details = scraper.get_novel_details(novel_url)
            if details:
                ch_count = details.get("chapter_count", 0)
                print(f"  [OK] '{details.get('title', '')}' — {ch_count} chapters")
            else:
                print("  [!] Failed to fetch details. Creating project without chapter list.")
        except Exception as e:
            logger.warning(f"[novel_search] get_novel_details error: {e}")
            print(f"  [!] Error: {e}")
    else:
        print(f"  [!] Scraper '{site_name}' not found. Continuing without chapter list.")

    site_source_lang = selected.get("site_source_lang", "Chinese")
    if details:
        details["source_language"] = site_source_lang

    result = _scaffold_project(selected, details, target_lang)
    if not result:
        return True

    project_name = result["project_name"]
    chapter_count = result["chapter_count"]

    print(f"\n  {'=' * 50}")
    print(f"  [OK] Project '{project_name}' created!")
    print(f"  Path: manual_projects/{project_name}/")
    print(f"\n  {chapter_count} empty raw chapter files created.")
    print(f"  Each file contains the source URL to help you copy-paste.")
    print(f"\n  Next steps:")
    print(f"  1. Open: chapters/raw/chapter_001.txt")
    print(f"  2. Delete the # lines, paste chapter content from the source site")
    print(f"  3. Repeat for remaining chapters")
    print(f"  4. Use 'Manage Projects' menu to start translating")
    print(f"  {'=' * 50}")

    cont = input("\n  Create another project? (y/n): ").strip().lower()
    return cont == "y"


def search_novel_menu(manager):
    """
    Interactive Search Novel menu with paginated results (10 per page).
    manager: ScraperManager instance
    """
    sites = manager.list_available_sites()

    print("\n" + "=" * 60)
    print("  SEARCH NOVEL — Find Novels from Configured Sites")
    print("=" * 60)

    if not sites:
        print("  [!] No sites configured.")
        print("  Use 'Add Website' menu to add a site first.")
        input("\n  Press Enter to return...")
        return

    print(f"  Configured sites: {', '.join(sites)}")
    print()

    target_lang = _pick_language()

    user_prompt = input("  Search criteria (e.g. 'best completed urban fantasy Chinese'): ").strip()
    if not user_prompt:
        print("  [!] Empty search criteria. Cancelled.")
        input("\n  Press Enter to return...")
        return

    print()

    # Collect novels from all sites
    all_novels = []
    for site_name in sites:
        scraper = manager.get_scraper_by_name(site_name)
        if not scraper:
            print(f"  [!] Could not load scraper for '{site_name}'.")
            continue
        print(f"  [{site_name}] Fetching novel list...")
        novels = _collect_novels_from_site(scraper, site_name, max_pages=2)
        site_lang = manager._site_configs.get(site_name, {}).get("source_language", "Chinese")
        for n in novels:
            n["site_source_lang"] = site_lang
        all_novels.extend(novels)
        print(f"  [{site_name}] Total: {len(novels)} novels collected")

    if not all_novels:
        print("\n  [!] No novels could be fetched from any site.")
        input("\n  Press Enter to return...")
        return

    print(f"\n  Total {len(all_novels)} novels from all sites. Filtering with AI...")

    results = _filter_and_translate_with_gemini(all_novels, user_prompt, target_lang)

    if not results:
        print("  [!] No novels matched the search criteria.")
        input("\n  Press Enter to return...")
        return

    # Save all results to cache; enrichment will happen lazily per page
    cache = {
        "query": user_prompt,
        "target_lang": target_lang,
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "results": results,
        "enriched_pages": [],
    }
    _save_search_cache(results, user_prompt, target_lang)

    total_pages = (len(results) + PAGE_SIZE - 1) // PAGE_SIZE
    page_idx = 0  # 0-based internally

    while True:
        # Lazy enrichment for current page
        _enrich_page_if_needed(cache, page_idx, manager)

        start = page_idx * PAGE_SIZE
        page_novels = cache["results"][start:start + PAGE_SIZE]
        page_num = page_idx + 1

        _display_results(page_novels, page_num, total_pages, cache["total"], user_prompt, target_lang)

        raw = input("  > ").strip().upper()

        if raw == "Q" or raw == "":
            break
        elif raw == "N":
            if page_idx < total_pages - 1:
                page_idx += 1
            else:
                print("  [!] Already on the last page.")
        elif raw == "B":
            if page_idx > 0:
                page_idx -= 1
            else:
                print("  [!] Already on the first page.")
        elif raw.isdigit():
            keep_going = _handle_novel_selection(raw, page_idx, cache, manager, target_lang)
            if not keep_going:
                break
        else:
            print("  [!] Unknown command. Use N, B, 1-10, or Q.")

    input("\n  Press Enter to return to menu...")
