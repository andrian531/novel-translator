"""
settings_manager.py — Global user preferences for novel-translator.
Stored at config/settings.json (tracked by git).
"""
import json
import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_PATH = os.path.join(_BASE_DIR, "config", "settings.json")

_DEFAULTS = {
    "display_language": "",          # e.g. "Indonesian" — empty = not set yet
    "search": {
        "exclude_tags": [],          # e.g. ["BL", "yaoi", "boys love"]
        "exclude_keywords": [],      # raw keywords matched against title/synopsis
    }
}


def load() -> dict:
    """Load settings. Returns defaults if file doesn't exist."""
    if not os.path.exists(SETTINGS_PATH):
        return _deep_copy(_DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge missing keys from defaults
        merged = _deep_copy(_DEFAULTS)
        _deep_merge(merged, data)
        return merged
    except Exception:
        return _deep_copy(_DEFAULTS)


def save(settings: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)


def is_configured(settings: dict) -> bool:
    """True if essential settings have been filled."""
    return bool(settings.get("display_language"))


def setup_interactive(settings: dict) -> dict:
    """
    Walk user through first-time setup or full re-configure.
    Returns updated settings dict (also saved to disk).
    """
    from engines.novel_search import _pick_language  # avoid circular at module level

    print("\n" + "=" * 56)
    print("  SEARCH SETTINGS")
    print("=" * 56)

    # Display language
    current_lang = settings.get("display_language") or ""
    if current_lang:
        print(f"  Current display language: {current_lang}")
    lang = _pick_language()
    settings["display_language"] = lang

    # Exclude tags
    current_excl = settings["search"].get("exclude_tags", [])
    print(f"\n  Exclude genres/tags from search results.")
    print(f"  Current: {', '.join(current_excl) if current_excl else '(none)'}")
    print(f"  Enter tags to exclude, comma-separated. Leave blank to keep current.")
    print(f"  Example: BL, yaoi, boys love, shounen ai, 耽美")
    raw = input("  > ").strip()
    if raw:
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        settings["search"]["exclude_tags"] = tags
    elif not current_excl:
        settings["search"]["exclude_tags"] = []

    # Exclude keywords
    current_kw = settings["search"].get("exclude_keywords", [])
    print(f"\n  Exclude raw keywords (matched against title/synopsis).")
    print(f"  Current: {', '.join(current_kw) if current_kw else '(none)'}")
    print(f"  Leave blank to keep current.")
    raw_kw = input("  > ").strip()
    if raw_kw:
        kws = [k.strip() for k in raw_kw.split(",") if k.strip()]
        settings["search"]["exclude_keywords"] = kws

    save(settings)
    print(f"\n  [OK] Settings saved.")
    return settings


def _deep_copy(d):
    return json.loads(json.dumps(d))


def _deep_merge(base, override):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
