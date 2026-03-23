"""
Mengelola struktur folder project novel:

projects/
  {novel_id}/
    metadata.json          # info novel (judul, author, url, jumlah bab)
    reference.json         # tokoh, lokasi, istilah (diperbarui tiap bab)
    chapters/
      raw/
        ch_0001.txt        # teks China mentah
      translated/
        ch_0001.txt        # hasil terjemahan
"""

import os
import json
from engines.logger import logger

PROJECTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "projects")
MANUAL_DIR   = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manual_projects")


def _novel_dir(novel_id):
    return os.path.join(PROJECTS_DIR, str(novel_id))


def create_project(novel_data):
    """
    Buat folder project untuk novel.
    novel_data harus punya: id, title, author, url
    Kembalikan path folder project.
    """
    nid = str(novel_data["id"]).replace("/", "_").strip("_")
    path = _novel_dir(nid)

    os.makedirs(os.path.join(path, "chapters", "raw"), exist_ok=True)
    os.makedirs(os.path.join(path, "chapters", "translated"), exist_ok=True)
    os.makedirs(os.path.join(path, "covers"), exist_ok=True)

    meta_file = os.path.join(path, "metadata.json")
    if not os.path.exists(meta_file):
        metadata = {
            "id": nid,
            "title": novel_data.get("title", ""),
            "author": novel_data.get("author", ""),
            "url": novel_data.get("url", ""),
            "chapter_count": novel_data.get("chapter_count", 0),
            "chapters": novel_data.get("chapters", []),
        }
        _write_json(meta_file, metadata)
        logger.info(f"[Project] Project dibuat: {path}")
    else:
        logger.info(f"[Project] Project sudah ada: {path}")

    # Buat reference.json kosong jika belum ada
    ref_file = os.path.join(path, "reference.json")
    if not os.path.exists(ref_file):
        _write_json(ref_file, {"characters": {}, "locations": {}, "terms": {}, "modern_terms": {}})

    return path


def load_metadata(novel_id):
    f = os.path.join(_novel_dir(novel_id), "metadata.json")
    return _read_json(f) if os.path.exists(f) else {}


def update_metadata(novel_id, data):
    f = os.path.join(_novel_dir(novel_id), "metadata.json")
    existing = _read_json(f) if os.path.exists(f) else {}
    existing.update(data)
    _write_json(f, existing)


def load_reference(novel_id):
    f = os.path.join(_novel_dir(novel_id), "reference.json")
    return _read_json(f) if os.path.exists(f) else {"characters": {}, "locations": {}, "terms": {}, "modern_terms": {}}


def save_reference(novel_id, reference):
    f = os.path.join(_novel_dir(novel_id), "reference.json")
    _write_json(f, reference)
    total = sum(len(v) for v in reference.values())
    logger.info(f"[Project] Reference disimpan: {total} entri total")


def save_chapter_raw(novel_id, chapter_num, text):
    path = os.path.join(_novel_dir(novel_id), "chapters", "raw", f"ch_{chapter_num:04d}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info(f"[Project] Raw bab {chapter_num} disimpan ({len(text)} karakter)")
    return path


def save_chapter_translated(novel_id, chapter_num, text):
    path = os.path.join(_novel_dir(novel_id), "chapters", "translated", f"ch_{chapter_num:04d}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info(f"[Project] Terjemahan bab {chapter_num} disimpan ({len(text)} karakter)")
    return path


def load_chapter_raw(novel_id, chapter_num):
    path = os.path.join(_novel_dir(novel_id), "chapters", "raw", f"ch_{chapter_num:04d}.txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def list_projects():
    if not os.path.exists(PROJECTS_DIR):
        return []
    return [d for d in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, d))]


# ---------------------------------------------------------------------------
# Manual Projects
# ---------------------------------------------------------------------------

def _manual_dir(project_id):
    return os.path.join(MANUAL_DIR, project_id)


def create_manual_project(title, source_lang, target_lang, synopsis="",
                           english_name="", source_url=""):
    """
    Buat folder manual project.
    folder_name berasal dari english_name (huruf latin) bukan dari judul asli.
    Kembalikan (project_id, path).
    """
    import re
    from datetime import datetime

    # Folder selalu pakai english_name (ASCII) bukan judul asli
    slug_source = english_name.strip() if english_name.strip() else title
    safe = re.sub(r'[^\w\-]', '_', slug_source)[:50].strip('_') or "novel"
    base = safe
    path = os.path.join(MANUAL_DIR, base)
    counter = 2
    while os.path.exists(path):
        base = f"{safe}_{counter}"
        path = os.path.join(MANUAL_DIR, base)
        counter += 1

    project_id = base
    os.makedirs(os.path.join(path, "chapters", "raw"),        exist_ok=True)
    os.makedirs(os.path.join(path, "chapters", "translated"), exist_ok=True)
    os.makedirs(os.path.join(path, "covers"),                 exist_ok=True)

    _write_json(os.path.join(path, "metadata.json"), {
        "id":           project_id,
        "title":        title,           # judul asli (China/Japan/dll)
        "english_name": english_name,    # judul/nama English untuk folder & platform
        "source_lang":  source_lang,
        "target_lang":  target_lang,
        "synopsis":     synopsis,
        "source_url":   source_url,
        "created_at":   datetime.now().isoformat(),
        "type":         "manual",
    })
    _write_json(os.path.join(path, "reference.json"),
                {"characters": {}, "locations": {}, "terms": {}})

    logger.info(f"[Manual] Project dibuat: {path}")
    return project_id, path


def list_manual_projects():
    if not os.path.exists(MANUAL_DIR):
        return []
    return sorted(
        d for d in os.listdir(MANUAL_DIR)
        if os.path.isdir(os.path.join(MANUAL_DIR, d))
        and os.path.exists(os.path.join(MANUAL_DIR, d, "metadata.json"))
    )


def load_manual_metadata(project_id):
    f = os.path.join(_manual_dir(project_id), "metadata.json")
    return _read_json(f) if os.path.exists(f) else {}


def save_manual_metadata(project_id, data):
    f = os.path.join(_manual_dir(project_id), "metadata.json")
    _write_json(f, data)


def update_manual_metadata(project_id, data):
    f = os.path.join(_manual_dir(project_id), "metadata.json")
    existing = _read_json(f) if os.path.exists(f) else {}
    existing.update(data)
    _write_json(f, existing)


def load_manual_reference(project_id):
    f = os.path.join(_manual_dir(project_id), "reference.json")
    ref = _read_json(f) if os.path.exists(f) else {}
    ref.setdefault("characters", {})
    ref.setdefault("locations", {})
    ref.setdefault("terms", {})
    ref.setdefault("modern_terms", {})
    ref.setdefault("character_profiles", [])
    return ref


def save_manual_reference(project_id, reference):
    f = os.path.join(_manual_dir(project_id), "reference.json")
    _write_json(f, reference)
    total = sum(len(v) for v in reference.values() if isinstance(v, dict))
    logger.info(f"[Manual] Reference disimpan: {total} entri")


def get_raw_chapters_path(project_id):
    return os.path.join(_manual_dir(project_id), "chapters", "raw")


def list_raw_chapters(project_id):
    """Scan chapters/raw/ → list filename .txt terurut."""
    raw_dir = get_raw_chapters_path(project_id)
    if not os.path.exists(raw_dir):
        return []
    return sorted(f for f in os.listdir(raw_dir) if f.lower().endswith(".txt"))


def scaffold_raw_chapters(project_id, total):
    """
    Buat file chapter kosong chapter_001.txt … chapter_NNN.txt di chapters/raw/.
    - Jika total lebih besar dari yang ada: buat file baru yang belum ada.
    - Jika total lebih kecil: hapus file kosong yang melebihi total (tidak hapus file berisi konten).
    Kembalikan (created, deleted).
    """
    raw_dir = get_raw_chapters_path(project_id)
    os.makedirs(raw_dir, exist_ok=True)
    digits = max(3, len(str(total)))
    created = 0
    deleted = 0

    # Buat file yang belum ada sampai total
    for n in range(1, total + 1):
        fname = f"chapter_{str(n).zfill(digits)}.txt"
        fpath = os.path.join(raw_dir, fname)
        if not os.path.exists(fpath):
            open(fpath, "w", encoding="utf-8").close()
            created += 1

    # Hapus file kosong chapter_NNN.txt yang melebihi total
    for fname in os.listdir(raw_dir):
        if not fname.lower().endswith(".txt"):
            continue
        import re as _re
        m = _re.match(r'^chapter_(\d+)\.txt$', fname, _re.IGNORECASE)
        if not m:
            continue
        n = int(m.group(1))
        if n > total:
            fpath = os.path.join(raw_dir, fname)
            if os.path.getsize(fpath) == 0:  # hanya hapus jika kosong
                os.remove(fpath)
                deleted += 1

    return created, deleted


def is_raw_chapter_empty(project_id, filename):
    """Return True jika file raw chapter ada tapi kosong (belum diisi konten)."""
    path = os.path.join(_manual_dir(project_id), "chapters", "raw", filename)
    return os.path.exists(path) and os.path.getsize(path) == 0


def is_chapter_translated(project_id, filename):
    path = os.path.join(_manual_dir(project_id), "chapters", "translated", filename)
    return os.path.exists(path)


def list_translated_chapters(project_id):
    """Return sorted list of translated chapter filenames."""
    path = os.path.join(_manual_dir(project_id), "chapters", "translated")
    if not os.path.exists(path):
        return []
    return sorted(f for f in os.listdir(path) if f.endswith(".txt"))


def load_translated_chapter(project_id, filename):
    path = os.path.join(_manual_dir(project_id), "chapters", "translated", filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_raw_chapter(project_id, filename):
    path = os.path.join(_manual_dir(project_id), "chapters", "raw", filename)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_translation_guide(project_id):
    f = os.path.join(_manual_dir(project_id), "translation_guide.json")
    return _read_json(f) if os.path.exists(f) else {}


def save_translation_guide(project_id, guide):
    f = os.path.join(_manual_dir(project_id), "translation_guide.json")
    _write_json(f, guide)
    logger.info(f"[Manual] Translation guide disimpan")


def save_manual_chapter_translated(project_id, filename, text):
    path = os.path.join(_manual_dir(project_id), "chapters", "translated", filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info(f"[Manual] Terjemahan disimpan: {filename} ({len(text)} karakter)")
    return path


def load_chapter_context(project_id):
    """
    Muat chapter_context.json — memori naratif ringan per-project.
    Berisi: last_translated, chapter_summaries (rolling 5 terakhir),
            current_arc, mood, recent_characters_active.
    """
    f = os.path.join(_manual_dir(project_id), "chapter_context.json")
    if not os.path.exists(f):
        return {
            "last_translated": None,
            "chapter_summaries": [],   # list of {chapter, summary}
            "current_arc": "",
            "mood": "",
            "recent_characters_active": [],
        }
    return _read_json(f)


def save_chapter_context(project_id, context):
    """Simpan chapter_context.json. Jaga rolling summaries max 5 entry, tiap summary max 350 char."""
    summaries = context.get("chapter_summaries", [])
    # Truncate individual summary text to prevent prompt bloat
    for s in summaries:
        if len(s.get("summary", "")) > 350:
            s["summary"] = s["summary"][:347] + "..."
    if len(summaries) > 5:
        context["chapter_summaries"] = summaries[-5:]
    f = os.path.join(_manual_dir(project_id), "chapter_context.json")
    _write_json(f, context)
    logger.info(f"[Manual] chapter_context.json diperbarui: last={context.get('last_translated','-')}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
