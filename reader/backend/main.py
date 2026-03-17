"""
Novel Reader — FastAPI backend
Serves novel list, chapter list, and chapter content from manual_projects/.
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Novel Reader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Path ke manual_projects — dua level di atas backend/
BASE_DIR = Path(__file__).parent.parent.parent
PROJECTS_DIR = BASE_DIR / "manual_projects"


def _load_json(path: Path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _list_translated(project_id: str) -> list[str]:
    path = PROJECTS_DIR / project_id / "chapters" / "translated"
    if not path.exists():
        return []
    return sorted(f for f in os.listdir(path) if f.endswith(".txt"))


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get("/api/novels")
def list_novels():
    """List semua novel project yang tersedia."""
    if not PROJECTS_DIR.exists():
        return []
    novels = []
    for item in sorted(PROJECTS_DIR.iterdir()):
        if not item.is_dir():
            continue
        meta = _load_json(item / "metadata.json")
        translated = _list_translated(item.name)
        novels.append({
            "id": item.name,
            "title": meta.get("title", item.name),
            "title_translated": meta.get("title_translated", ""),
            "author": meta.get("author", ""),
            "source_language": meta.get("source_lang", ""),
            "target_language": meta.get("target_lang", "Indonesian"),
            "content_rating": meta.get("content_rating", "general"),
            "synopsis": meta.get("synopsis", ""),
            "translated_count": len(translated),
            "total_chapters": meta.get("total_chapters", 0),
        })
    return novels


@app.get("/api/novels/{project_id}")
def get_novel(project_id: str):
    """Detail novel + daftar chapter yang sudah ditranslate."""
    project_path = PROJECTS_DIR / project_id
    if not project_path.exists():
        raise HTTPException(status_code=404, detail="Novel not found")

    meta = _load_json(project_path / "metadata.json")
    translated = _list_translated(project_id)

    return {
        "id": project_id,
        "title": meta.get("title", project_id),
        "title_translated": meta.get("title_translated", ""),
        "author": meta.get("author", ""),
        "source_language": meta.get("source_lang", ""),
        "target_language": meta.get("target_lang", "Indonesian"),
        "content_rating": meta.get("content_rating", "general"),
        "synopsis": meta.get("synopsis", ""),
        "total_chapters": meta.get("total_chapters", 0),
        "chapters": translated,
    }


@app.get("/api/novels/{project_id}/chapters/{filename}")
def get_chapter(project_id: str, filename: str):
    """Konten satu chapter."""
    if not filename.endswith(".txt") or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    chapter_path = PROJECTS_DIR / project_id / "chapters" / "translated" / filename
    if not chapter_path.exists():
        raise HTTPException(status_code=404, detail="Chapter not found")

    content = chapter_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # Baris pertama sebagai judul jika terlihat seperti judul (pendek, bukan paragraf)
    title = ""
    body = content
    if lines and len(lines[0]) < 100 and not lines[0].endswith((".", "!", "?")):
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

    # Daftar semua chapter untuk navigasi prev/next
    all_chapters = _list_translated(project_id)
    idx = all_chapters.index(filename) if filename in all_chapters else -1
    prev_ch = all_chapters[idx - 1] if idx > 0 else None
    next_ch = all_chapters[idx + 1] if idx < len(all_chapters) - 1 else None

    return {
        "filename": filename,
        "title": title,
        "content": body,
        "prev": prev_ch,
        "next": next_ch,
        "index": idx + 1,
        "total": len(all_chapters),
    }
