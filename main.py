import os
import sys
import json
from engines.scraper_manager import ScraperManager
from engines.logger import tail_log, get_log_path
from engines import project_manager as pm
from engines import translator as tr

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def main_menu():
    manager = ScraperManager()

    while True:
        clear_screen()
        print("========================================")
        print("      NOVEL TRANSLATOR - CLI v0.3")
        print("========================================")
        print("  1. New Translate Project")
        print("  2. Manage Projects")
        print("  ────────────────────────────────────")
        print("  3. Search Novel")
        print("  4. Add Website")
        print("  ────────────────────────────────────")
        print("  5. Settings")
        print("  ────────────────────────────────────")
        print("  6. Exit")
        print("----------------------------------------")

        choice = input("Select an option: ").strip()

        if choice == '1':
            manual_project_new()
        elif choice == '2':
            manual_project_select()
        elif choice == '3':
            from engines.novel_search import search_novel_menu
            search_novel_menu(manager)
        elif choice == '4':
            from engines.site_analyzer import analyze_website
            analyze_website(manager)
        elif choice == '5':
            from engines import settings_manager as sm
            settings = sm.load()
            sm.setup_interactive(settings)
            input("\n  Press Enter to continue...")
        elif choice == '6':
            print("Goodbye!")
            break
        else:
            input("Invalid choice. Press Enter to continue...")

def browse_sites(manager):
    sites = manager.list_available_sites()
    if not sites:
        print("[-] No scrapers configured in site_map.json")
        input("Press Enter to return...")
        return

    clear_screen()
    print("--- Select a Website ---")
    for i, site in enumerate(sites):
        print(f"{i+1}. {site}")
    print(f"{len(sites)+1}. < Back")
    
    idx = input("\nSelect site: ").strip()
    if not idx.isdigit() or int(idx) > len(sites) + 1:
        return
    
    if int(idx) == len(sites) + 1:
        return

    selected_site_name = sites[int(idx)-1]
    scraper = manager.get_scraper_by_name(selected_site_name)
    if not scraper:
        input("[-] Failed to load scraper. Press Enter...")
        return
    
    browse_rankings(scraper)

def browse_rankings(scraper):
    rankings = scraper.get_supported_rankings()
    if not rankings:
        print("[-] This site doesn't support ranking discovery.")
        input("Press Enter...")
        return

    labels = list(rankings.keys())
    
    while True:
        clear_screen()
        print(f"--- {scraper.base_url} Rankings ---")
        for i, label in enumerate(labels):
            print(f"{i+1}. {label}")
        print(f"{len(labels)+1}. < Back")
        
        idx = input("\nSelect ranking: ").strip()
        if not idx.isdigit(): continue
        
        if int(idx) == len(labels) + 1:
            break
            
        if 1 <= int(idx) <= len(labels):
            rank_label = labels[int(idx)-1]
            rank_id = rankings[rank_label]

            # Pilih bahasa SEBELUM fetch
            clear_screen()
            print(f"--- {rank_label} ---")
            print("Pilih bahasa tampilan:")
            print("  1. Indonesian")
            print("  2. English")
            print("  3. Tampilkan asli (China)")
            lang_choice = input("\nPilihan [1]: ").strip()
            if lang_choice == "2":
                display_lang = "English"
            elif lang_choice == "3":
                display_lang = None
            else:
                display_lang = "Indonesian"

            show_rank_results(scraper, rank_id, rank_label, display_lang)

def show_rank_results(scraper, rank_id, rank_label, display_lang=None):
    page = 1
    while True:
        clear_screen()
        print(f"--- {rank_label} (Page {page}) ---")
        if display_lang:
            print(f"Fetching & translating to {display_lang}... harap tunggu.")
        else:
            print("Fetching results...")

        novels = scraper.get_ranking_list(rank_id, page)

        if novels and display_lang:
            novels = scraper.translate_results(novels, target_lang=display_lang)

        clear_screen()
        label_info = f"{rank_label} (Page {page})"
        if display_lang:
            label_info += f" [{display_lang}]"
        print(f"--- {label_info} ---")

        if not novels:
            print("[-] No results found or site blocked access (403).")
            print("[TIP] Check scraper_logs/ atau coba site lain.")
            input("\nPress Enter to go back...")
            break

        for i, n in enumerate(novels):
            print(f"{i+1}. {n['title']} | Author: {n['author']}")
            syn = n['synopsis'][:160] + "..." if len(n['synopsis']) > 160 else n['synopsis']
            print(f"   > {syn}")
            print("-" * 40)

        print(f"\n[N] Next | [P] Prev | [L] View Log | [1-{len(novels)}] Pilih Novel | [B] Back")
        cmd = input("Choice: ").strip().lower()

        if cmd == 'n': page += 1
        elif cmd == 'p': page = max(1, page - 1)
        elif cmd == 'b': break
        elif cmd == 'l':
            clear_screen()
            print(f"--- Log Terbaru ({get_log_path()}) ---\n")
            print(tail_log(40))
            input("\nPress Enter untuk kembali...")
        elif cmd.isdigit() and 1 <= int(cmd) <= len(novels):
            selected = novels[int(cmd)-1]
            init_project_menu(selected, scraper)
            break

def init_project_menu(novel_data, scraper):
    clear_screen()
    print("=" * 50)
    print("  INITIALIZE NOVEL PROJECT")
    print("=" * 50)
    print(f"  Judul  : {novel_data['title']}")
    print(f"  Author : {novel_data['author']}")
    print(f"  URL    : {novel_data['url']}")
    print("-" * 50)

    # Step 1: Fetch chapter list
    print("[1/5] Mengambil daftar chapter...")
    details = scraper.get_novel_details(novel_data['url'])
    if not details or not details.get("chapters"):
        print("[-] Gagal mengambil daftar chapter. Cek log untuk detail.")
        input("\nPress Enter untuk kembali...")
        return

    chapter_count = details["chapter_count"]
    chapters = details["chapters"]
    print(f"     Ditemukan {chapter_count} chapter.")
    print(f"     Chapter pertama: {chapters[0]['title'] if chapters else '-'}")
    print("-" * 50)

    confirm = input("Lanjutkan inisialisasi? (y/n): ").strip().lower()
    if confirm != 'y':
        return

    # Merge info detail ke novel_data
    novel_data.update(details)

    # Step 2: Buat folder project
    print("\n[2/5] Membuat folder project...")
    nid = str(novel_data["id"]).replace("/", "_").strip("_")
    project_path = pm.create_project(novel_data)
    print(f"     Folder: {project_path}")

    # Step 3: Download bab 1
    print("\n[3/5] Mendownload bab 1...")
    ch1 = chapters[0]
    raw_text = scraper.fetch_chapter(ch1["url"])
    if not raw_text:
        print("[-] Gagal mendownload bab 1. Cek log untuk detail.")
        input("\nPress Enter untuk kembali...")
        return
    pm.save_chapter_raw(nid, 1, raw_text)
    print(f"     Tersimpan ({len(raw_text)} karakter)")

    # Step 4: Gemini analisis entitas
    print("\n[4/5] Analisis tokoh/lokasi/istilah dengan Gemini...")
    entities = tr.analyze_chapter(raw_text)
    reference = pm.load_reference(nid)
    reference = tr.merge_reference(reference, entities)
    pm.save_reference(nid, reference)

    chars = len(reference.get("characters", {}))
    locs = len(reference.get("locations", {}))
    terms = len(reference.get("terms", {}))
    print(f"     Tokoh: {chars} | Lokasi: {locs} | Istilah: {terms}")
    if chars + locs + terms == 0:
        print("     [!] Tidak ada entitas terdeteksi — Gemini mungkin tidak terinstall.")
        print("         Terjemahan tetap dilanjutkan tanpa referensi.")

    # Tampilkan referensi singkat
    if chars > 0:
        sample = list(reference["characters"].items())[:5]
        print("     Tokoh sample:", ", ".join(f"{k}→{v}" for k, v in sample))

    # Step 5: Translate bab 1
    print("\n[5/5] Menterjemahkan bab 1 dengan Ollama...")
    target = input("     Bahasa tujuan (ID: Indonesian, EN: English) [ID]: ").strip().lower()
    lang = "English" if target == "en" else "Indonesian"

    models = tr.get_available_models()
    if not models:
        print("[-] Tidak ada model Ollama tersedia. Pastikan Ollama berjalan.")
        input("\nPress Enter untuk kembali...")
        return

    print(f"     Model tersedia: {', '.join(models[:5])}")
    print(f"     Menerjemahkan ke {lang}... (mungkin beberapa menit)")

    translated, used_model = tr.translate_chapter(raw_text, reference, lang, models)
    if not translated:
        print("[-] Terjemahan gagal. Cek log di scraper_logs/ untuk detail.")
        input("\nPress Enter untuk kembali...")
        return

    pm.save_chapter_translated(nid, 1, translated)
    print(f"     Selesai! Model: {used_model} | {len(translated)} karakter")

    # Tampilkan preview 5 baris pertama
    print("\n" + "=" * 50)
    print("  PREVIEW TERJEMAHAN BAB 1")
    print("=" * 50)
    preview = "\n".join(translated.splitlines()[:10])
    print(preview)
    print("\n...")
    print(f"\n[OK] Project tersimpan di: {project_path}")
    print(f"     Log detail: {get_log_path()}")
    input("\nPress Enter untuk kembali...")


def init_project_from_url(manager):
    url = input("\nEnter novel URL: ").strip()
    if not url:
        return

    scraper = manager.get_scraper(url)
    if not scraper:
        print("[-] Unsupported URL or site.")
        input("Press Enter...")
        return

    print("[*] Fetching novel data...")
    details = scraper.get_novel_details(url)
    if not details:
        print("[-] Gagal mengambil data novel.")
        input("Press Enter...")
        return

    # Gunakan URL path terakhir sebagai id fallback
    novel_data = details.copy()
    if "id" not in novel_data:
        novel_data["id"] = url.rstrip("/").split("/")[-1].replace(".htm", "")

    init_project_menu(novel_data, scraper)

def _paste_multiline(prompt_text):
    """Baca input multiline. Ketik '---' di baris baru untuk selesai."""
    print(prompt_text)
    print("(Paste teks, lalu ketik '---' di baris baru dan tekan Enter)")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "---":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def manual_translate_menu():
    """Sub-menu: project baru atau project yang sudah ada."""
    while True:
        clear_screen()
        print("=" * 52)
        print("  TRANSLATE")
        print("=" * 52)
        print("1. New Project")
        print("2. Existing Project")
        print("3. Back")
        print("-" * 52)
        c = input("Choice: ").strip()
        if c == '1':
            manual_project_new()
        elif c == '2':
            manual_project_select()
        elif c == '3':
            break


def manual_project_new():
    """Wizard buat project manual baru."""
    clear_screen()
    print("--- New Project ---\n")

    title = input("Novel title (original): ").strip()
    if not title:
        print("[-] Title is required.")
        input("Press Enter...")
        return

    print("Source language: 1.Chinese  2.Japanese  3.Korean  4.Other")
    sc = input("Choice [1]: ").strip()
    source_lang = {"2": "Japanese", "3": "Korean"}.get(sc, "Chinese")
    if sc == "4":
        source_lang = input("Source language: ").strip() or "Chinese"

    print("Target language: 1.Indonesian  2.English  3.Other")
    tc = input("Choice [1]: ").strip()
    target_lang = {"2": "English"}.get(tc, "Indonesian")
    if tc == "3":
        target_lang = input("Target language: ").strip() or "Indonesian"

    synopsis = input("Short synopsis (Enter to skip): ").strip()
    source_url = input("Source novel URL (Enter to skip): ").strip()
    total_chapters_str = input("Total chapter count (Enter to skip): ").strip()
    total_chapters = int(total_chapters_str) if total_chapters_str.isdigit() and int(total_chapters_str) > 0 else 0

    # Gemini suggest English folder name
    print("\n[*] Gemini is reading title & synopsis to suggest a folder name...\n")
    import re as _re
    slug_prompt = (
        f"You are helping name a novel translation project folder.\n"
        f"Original title: {title}\n"
        f"Source language: {source_lang}\n"
        f"Synopsis: {synopsis or '(tidak tersedia)'}\n\n"
        f"Generate 5 short English folder name suggestions for this novel project.\n"
        f"Rules:\n"
        f"- ASCII only, no spaces (use underscores), max 30 chars each\n"
        f"- Capture the essence of the story (not a literal translation of the title)\n"
        f"- Mix styles: one descriptive, one dramatic, one concise, one thematic, one creative\n"
        f"- Format: return ONLY a numbered list, one per line, just the name itself\n"
        f"Example format:\n1. Tang_Dynasty_System\n2. Live_Broadcast_Betrayal\n3. ..."
    )
    slug_out = tr._run_gemini(slug_prompt, timeout=45)
    suggestions = []
    if slug_out:
        for line in slug_out.splitlines():
            m = _re.match(r'\d+\.\s*([A-Za-z0-9_\-]+)', line.strip())
            if m:
                suggestions.append(m.group(1)[:40])

    if suggestions:
        print("Choose folder name (Gemini recommendations):\n")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s}")
        print(f"  {len(suggestions)+1}. Type manually")
        print()
        pick = input(f"Choice [1]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(suggestions):
            eng_name = suggestions[int(pick)-1]
        elif pick == str(len(suggestions)+1) or not pick.isdigit():
            eng_name = input("Folder name: ").strip()
        else:
            eng_name = suggestions[0]
    else:
        print("Project folder name (Latin/English characters, no spaces).")
        eng_name = input("Folder name: ").strip()

    if not eng_name:
        eng_name = _re.sub(r'[^\w]', '_', title[:20]).strip('_') or "novel"
    eng_name = _re.sub(r'[^\w\-]', '_', eng_name).strip('_')

    print("\n[*] Creating project folder...")
    project_id, path = pm.create_manual_project(
        title, source_lang, target_lang,
        synopsis=synopsis, english_name=eng_name, source_url=source_url
    )

    # If synopsis provided, Gemini can build initial reference
    if synopsis:
        print("[*] Gemini is analyzing synopsis for initial reference...")
        ctx = f"Novel title: {title}\nSynopsis: {synopsis}\n"
        entities = tr.analyze_chapter_with_context(synopsis, ctx)
        ref = pm.load_manual_reference(project_id)
        ref = tr.merge_reference(ref, entities)
        ref = tr.dedup_reference(ref)
        pm.save_manual_reference(project_id, ref)
        chars = len(ref.get("characters", {}))
        locs  = len(ref.get("locations", {}))
        terms = len(ref.get("terms", {}))
        print(f"     Initial reference: {chars} characters, {locs} locations, {terms} terms")

    raw_path = pm.get_raw_chapters_path(project_id)
    print(f"\n[OK] Project created!")

    if total_chapters > 0:
        created, _ = pm.scaffold_raw_chapters(project_id, total_chapters)
        pm.update_manual_metadata(project_id, {"total_chapters": total_chapters})
        print(f"[OK] {created} empty chapter files created (chapter_001 … chapter_{str(total_chapters).zfill(max(3,len(str(total_chapters))))}.txt)")

    # Translate title + synopsis to target_lang and save in metadata
    if title or synopsis:
        _translate_metadata(project_id)

    if total_chapters == 0:
        print(f"\n  Copy chapter files (.txt) to:")
        print(f"  {raw_path}")
        print(f"\n  One file = one chapter. Any filename works, e.g.:")
        print(f"    chapter_001.txt, ch01.txt, bab_1.txt, etc.")
    else:
        print(f"\n  Empty chapter files are ready at:")
        print(f"  {raw_path}")
        print(f"  Fill each file with the chapter content.")
    input("\nPress Enter to open project menu...")
    manual_project_menu(project_id)


def manual_project_select():
    """Pilih project yang sudah ada."""
    while True:
        clear_screen()
        print("--- Existing Projects ---\n")
        projects = pm.list_manual_projects()
        if not projects:
            print("No projects found.")
            input("\nPress Enter...")
            return

        for i, pid in enumerate(projects, 1):
            meta        = pm.load_manual_metadata(pid)
            title_orig  = meta.get("title", pid)
            title_trans = meta.get("title_translated", "")
            src         = meta.get("source_lang", "?")
            tgt         = meta.get("target_lang", "?")
            raws        = len(pm.list_raw_chapters(pid))
            syn_trans   = meta.get("synopsis_translated", "")
            display     = title_trans if title_trans else title_orig
            print(f"{i}. {display} [{src}→{tgt}] | {raws} chapter")
            if title_trans:
                print(f"   ({title_orig})")
            if syn_trans:
                prev = syn_trans[:120] + ("..." if len(syn_trans) > 120 else "")
                print(f"   {prev}")
            print()

        print(f"\n{len(projects)+1}. Back")
        c = input("\nSelect project: ").strip()
        if not c.isdigit():
            continue
        idx = int(c) - 1
        if idx == len(projects):
            break
        if 0 <= idx < len(projects):
            manual_project_menu(projects[idx])


def _parse_chapter_selection(text, max_n):
    """
    Parse input chapter selection:
      "3"       → [3]
      "1-5"     → [1, 2, 3, 4, 5]
      "1,3,5"   → [1, 3, 5]
      "1-3,7,9" → [1, 2, 3, 7, 9]
    Kembalikan list int yang sudah deduplicated dan terurut, atau [] jika invalid.
    """
    result = set()
    parts = text.replace(" ", "").split(",")
    for part in parts:
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                lo, hi = int(bounds[0]), int(bounds[1])
                if 1 <= lo <= hi <= max_n:
                    result.update(range(lo, hi + 1))
        elif part.isdigit():
            n = int(part)
            if 1 <= n <= max_n:
                result.add(n)
    return sorted(result)


def manual_project_menu(project_id):
    """Menu utama project: refresh, pilih chapter, lihat reference."""
    while True:
        clear_screen()
        meta        = pm.load_manual_metadata(project_id)
        title_orig  = meta.get("title", project_id)
        title_trans = meta.get("title_translated", "")
        src         = meta.get("source_lang", "?")
        tgt         = meta.get("target_lang", "?")
        ref         = pm.load_manual_reference(project_id)
        chars       = len(ref.get("characters", {}))
        locs        = len(ref.get("locations", {}))
        terms       = len(ref.get("terms", {}))
        raw_path    = pm.get_raw_chapters_path(project_id)

        print("=" * 56)
        if title_trans:
            print(f"  {title_trans}")
            print(f"  ({title_orig})")
        else:
            print(f"  {title_orig}")
        print(f"  {src} → {tgt}  |  Ref: {chars} tokoh, {locs} lokasi, {terms} istilah")
        print("=" * 56)

        chapters = pm.list_raw_chapters(project_id)
        if not chapters:
            print(f"\n  No chapter files found in raw/.")
            print(f"  Copy .txt files to:")
            print(f"  {raw_path}\n")
        else:
            # Detect duplicate raw chapters by content hash
            import hashlib as _hl
            _hash_to_first = {}   # md5 -> first filename
            _duplicate_of  = {}   # filename -> original filename
            for _fname in chapters:
                _raw = pm.load_raw_chapter(project_id, _fname)
                if _raw:
                    _h = _hl.md5(_raw.encode("utf-8", errors="ignore")).hexdigest()
                    if _h in _hash_to_first:
                        _duplicate_of[_fname] = _hash_to_first[_h]
                    else:
                        _hash_to_first[_h] = _fname

            print()
            print("  [✓] translated  [x] empty  [ ] pending  [!!] duplicate")
            print()
            for i, fname in enumerate(chapters, 1):
                if pm.is_chapter_translated(project_id, fname):
                    mark = "[✓]"
                elif pm.is_raw_chapter_empty(project_id, fname):
                    mark = "[x]"
                else:
                    mark = "[ ]"
                dup_note = f"  ← DUP of {_duplicate_of[fname]}" if fname in _duplicate_of else ""
                print(f"  {i:3}. {mark} {fname}{dup_note}")
            print()

            if _duplicate_of:
                print(f"  [!!] {len(_duplicate_of)} duplicate(s) detected — same content as another chapter.")
                print()

        guide_exists  = bool(pm.load_translation_guide(project_id).get("guide_text"))
        guide_mark    = "[✓]" if guide_exists else "[ ]"
        has_trans_meta = bool(meta.get("title_translated") or meta.get("synopsis_translated"))
        trans_mark    = "[✓]" if has_trans_meta else "[ ]"
        total_ch = meta.get("total_chapters", 0)
        total_mark = f" ({total_ch} ch)" if total_ch else ""
        print(f"[R] Refresh  [V] Reference  [S] Research {guide_mark}  [T] Translate Meta {trans_mark}")
        print(f"[U] Update Chapter Count{total_mark}  [G] Alt Titles  [I] Image Prompt  [A] Add Raw  [B] Back")
        print(f"[X] Re-translate chapter  [C] Continuity check  [Y] Sync Reference")
        if chapters:
            print(f"[1-{len(chapters)}] Translate chapter")
        print("-" * 56)
        cmd = input("Choice: ").strip().lower()

        if cmd == 'r':
            pass
        elif cmd == 'b':
            break
        elif cmd == 'v':
            _show_reference(ref)
        elif cmd == 's':
            manual_research_project(project_id)
        elif cmd == 't':
            _translate_metadata(project_id)
        elif cmd == 'u':
            cur = meta.get("total_chapters", 0)
            prompt_cur = f" (current: {cur})" if cur else ""
            new_total_str = input(f"Total chapter count{prompt_cur}: ").strip()
            if new_total_str.isdigit() and int(new_total_str) > 0:
                new_total = int(new_total_str)
                created, deleted = pm.scaffold_raw_chapters(project_id, new_total)
                pm.update_manual_metadata(project_id, {"total_chapters": new_total})
                msg = f"[OK] Total: {new_total} chapters."
                if created:
                    msg += f" +{created} new files created."
                if deleted:
                    msg += f" -{deleted} empty files deleted."
                print(msg)
            else:
                print("[-] Invalid input.")
            input("Press Enter...")
        elif cmd == 'a':
            add_raw_chapter_from_url(project_id)
        elif cmd == 'x':
            retranslate_chapter(project_id)
        elif cmd == 'c':
            continuity_check(project_id)
        elif cmd == 'y':
            sync_reference(project_id)
        elif cmd == 'g':
            generate_alt_titles(project_id)
        elif cmd == 'i':
            generate_image_prompt(project_id)
        else:
            # Parse single number, range (1-5), or comma list (1,3,5)
            selected = _parse_chapter_selection(cmd, len(chapters))
            if selected and chapters:
                valid = [i for i in selected if 1 <= i <= len(chapters)]
                if len(valid) == 1:
                    manual_translate_chapter(project_id, chapters[valid[0]-1])
                elif len(valid) > 1:
                    batch_translate_chapters(project_id, [chapters[i-1] for i in valid])


def add_raw_chapter_from_url(project_id):
    """
    Fetch chapter content (+ title) dari URL lalu simpan ke raw folder.
    Loop: setelah save otomatis minta URL berikutnya. Enter kosong = kembali ke menu.
    """
    from engines.scraper_manager import ScraperManager
    sm = ScraperManager()

    print("\n[Add Raw Chapter from URL]  (Enter kosong = kembali ke menu)")
    while True:
        url = input("\nChapter URL: ").strip()
        if not url:
            return
        _add_raw_single(project_id, url, sm=sm)


def _add_raw_single(project_id, url, sm=None):
    """Fetch dan simpan satu chapter dari URL. Dipanggil dari loop add_raw_chapter_from_url."""
    import os, json as _json
    from urllib.parse import urlparse
    from engines.scraper_manager import ScraperManager

    if sm is None:
        sm = ScraperManager()
    scraper = sm.get_scraper(url)

    # Domain tidak dikenali → cari site dari source_url metadata proyek
    if not scraper:
        url_netloc = urlparse(url).netloc
        new_mirror = f"{urlparse(url).scheme}://{url_netloc}"

        meta = pm.load_manual_metadata(project_id)
        source_url = meta.get("source_url", "")
        site_name  = meta.get("site", "")

        # Cari scraper berdasarkan site name di metadata, atau domain source_url
        target_cfg = None
        if site_name and site_name in sm._site_configs:
            target_cfg = sm._site_configs[site_name]
        elif source_url:
            src_domain = urlparse(source_url).netloc.replace("www.", "")
            ref = sm.get_scraper_by_domain(src_domain)
            if ref:
                target_cfg = ref.config

        if not target_cfg:
            print(f"\n  [-] Cannot determine site for this URL.")
            print(f"  Set 'source_url' in metadata or use 'Add Website' menu.")
            input("Press Enter...")
            return

        # Tambah mirror otomatis
        target_cfg["mirrors"] = target_cfg.get("mirrors", [target_cfg.get("base_url", "")]) + [new_mirror]
        config_path = sm.get_config_path(target_cfg["name"])
        if config_path and os.path.exists(config_path):
            with open(config_path, "w", encoding="utf-8") as _f:
                _json.dump(target_cfg, _f, ensure_ascii=False, indent=4)
            print(f"  [~] '{url_netloc}' auto-added as mirror to {os.path.basename(config_path)}")
        else:
            print("  [-] Could not update config file.")
            input("Press Enter...")
            return

        from engines.scrapers.generic_scraper import GenericScraper
        scraper = GenericScraper(target_cfg)

    display = scraper.config.get("display_name", scraper.site_name)
    print(f"  [*] Site  : {display}")
    print(f"  [*] Fetching chapter...")

    result = scraper.fetch_chapter_full(url)
    content = result.get("content", "")
    title   = result.get("title", "")
    title_conf   = result.get("title_confidence", "low")
    content_conf = result.get("content_confidence", "low")
    first_para   = result.get("first_para", "")

    if not content:
        print("  [-] Failed to fetch chapter content. Check the URL or site config.")
        input("Press Enter...")
        return

    # --- Konfirmasi title (hanya jika confidence rendah) ---
    if title_conf == "low":
        print(f"\n  Title detected (low confidence): {title or '(none)'}")
        ans = input("  Is this correct? [Y/n/type new title]: ").strip()
        if ans.lower() == "n":
            title = input("  Enter correct title: ").strip()
        elif ans and ans.lower() != "y":
            title = ans  # user langsung ketik judul baru

    # --- Konfirmasi paragraf pertama (hanya jika confidence rendah) ---
    if content_conf == "low":
        preview = first_para[:120] + ("..." if len(first_para) > 120 else "")
        print(f"\n  First paragraph (low confidence):")
        print(f"  \"{preview}\"")
        ans = input("  Does this look like chapter content? [Y/n]: ").strip().lower()
        if ans == "n":
            print("  [-] Content may be incorrect. Saving anyway — please verify manually.")

    # --- Nama file --- auto next sequential number
    existing = pm.list_raw_chapters(project_id)
    next_num = len(existing) + 1
    fname = f"chapter_{next_num:03d}.txt"

    # Gabungkan title + content
    full_content = f"{title}\n\n{content}" if title else content

    # Simpan
    raw_path = pm.get_raw_chapters_path(project_id)
    out_path = os.path.join(raw_path, fname)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full_content)

    print(f"\n  [OK] Saved: {fname} ({len(full_content)} chars)")
    if title:
        print(f"  Title: {title}")


def _ensure_content_rating(project_id, meta):
    """
    If content_rating not set in metadata, prompt user and save.
    Returns updated meta dict.
    """
    if meta.get("content_rating"):
        return meta
    print("  Content rating not set for this project.")
    print("  1. General  — safe for all audiences")
    print("  2. Mature   — violence/dark themes, no explicit sexual content")
    print("  3. Explicit — contains explicit sexual content [18+]")
    rc = input("  Set rating (Enter = general): ").strip()
    meta["content_rating"] = {"2": "mature", "3": "explicit"}.get(rc, "general")
    pm.save_manual_metadata(project_id, meta)
    print(f"  [OK] Content rating set to '{meta['content_rating']}' and saved.\n")
    return meta


def manual_research_project(project_id):
    """
    Riset project 2 tahap:
    Tahap 1 → Gemini baca daftar chapter + sinopsis → pilih chapter terbaik untuk diriset
    Tahap 2 → Gemini baca chapter terpilih → hasilkan laporan + reference + translation guide
    """
    clear_screen()
    meta     = pm.load_manual_metadata(project_id)
    title    = meta.get("title", "")
    src_lang = meta.get("source_lang", "Chinese")
    tgt_lang = meta.get("target_lang", "Indonesian")
    synopsis = meta.get("synopsis", "")
    chapters = pm.list_raw_chapters(project_id)

    print("=" * 56)
    print("  PROJECT RESEARCH")
    print("=" * 56)
    print(f"  Novel : {title}")
    print(f"  Lang  : {src_lang} → {tgt_lang}")
    print(f"  Available chapters: {len(chapters)}")
    print()

    if not chapters and not synopsis:
        print("[-] No raw chapters and synopsis is empty.")
        print("    Copy chapters to raw/ or fill in the synopsis first.")
        input("Press Enter...")
        return

    # ── TAHAP 1: Pilih chapter dengan algoritma spread ───────────────────────
    import re

    # Hanya chapter yang tidak kosong yang berguna untuk riset
    nonempty_chapters = [f for f in chapters if not pm.is_raw_chapter_empty(project_id, f)]

    def _select_spread(chaps):
        """
        Pilih chapter spread: 3 head + mid (interval per ~50 ch di mid zone) + 2 tail.
        Semakin banyak chapter, semakin banyak titik mid yang diambil.

        Contoh:
          n=10  → 3+1+2 = 6
          n=50  → 3+1+2 = 6  (mid zone 45ch, 1 titik)
          n=100 → 3+2+2 = 7  (mid zone 95ch, ~50ch/titik)
          n=200 → 3+4+2 = 9  (mid zone 195ch, ~49ch/titik)
          n=300 → 3+6+2 = 11
          n=500 → 3+10+2 = 15 (capped)
          n=1000→ 3+15+2 = 20 (hard cap 15 mid)
        """
        n = len(chaps)
        if n <= 5:
            return chaps[:]

        HEAD, TAIL = 3, 2
        head_list = chaps[:HEAD]
        tail_list = chaps[n - TAIL:]
        mid_zone  = chaps[HEAD: n - TAIL]
        m = len(mid_zone)

        # 1 titik per 50 chapter di mid zone, minimum 1, maksimum 15
        mid_count = max(1, min(15, m // 50)) if m >= 10 else (1 if m > 0 else 0)

        mid_list = []
        if mid_count > 0 and m > 0:
            step = m / (mid_count + 1)
            mid_list = [mid_zone[int(step * (i + 1))] for i in range(mid_count)]

        # Gabung jaga urutan & hindari duplikat
        seen, result = set(), []
        for f in head_list + mid_list + tail_list:
            if f not in seen:
                seen.add(f)
                result.append(f)
        return result

    if nonempty_chapters:
        selected = _select_spread(nonempty_chapters)
        n_all = len(nonempty_chapters)
        print(f"[1/3] Selecting chapters for research ({n_all} with content out of {len(chapters)} total)...")
        print(f"      Selected {len(selected)}: {', '.join(selected)}")
    elif chapters:
        selected = []
        print("[1/3] All chapters are empty — researching from synopsis only.")
    else:
        selected = []
        print("[1/3] No chapters — researching from synopsis only.")

    # ── PHASE 2: Read selected chapters + comprehensive analysis ─────────────
    print("\n[2/3] Loading chapters and sending to Gemini for deep analysis...")
    print("      Please wait — this may take 1-2 minutes.\n")

    content_parts = []
    if synopsis:
        content_parts.append(f"[SINOPSIS]\n{synopsis}")

    MAX_PER_CHAPTER = 4000
    for fname in selected:
        text = pm.load_raw_chapter(project_id, fname)
        if text:
            content_parts.append(f"[RAW: {fname}]\n{text[:MAX_PER_CHAPTER]}")

    # Sertakan sample translated chapters untuk konsistensi naming
    translated_all = pm.list_translated_chapters(project_id)
    if translated_all:
        translated_sample = _select_spread(translated_all)
        MAX_PER_TRANSLATED = 1500
        trans_parts = []
        for fname in translated_sample:
            text = pm.load_translated_chapter(project_id, fname)
            if text:
                trans_parts.append(f"[TRANSLATED: {fname}]\n{text[:MAX_PER_TRANSLATED]}")
        if trans_parts:
            content_parts.append(
                "=== TRANSLATED CHAPTERS (for naming consistency reference — preserve ALL names/terms already used here) ===\n"
                + "\n\n".join(trans_parts)
                + "\n=== END TRANSLATED ==="
            )
            print(f"      + {len(trans_parts)} translated chapter(s) included for consistency.")

    combined = "\n\n".join(content_parts)

    # Kirim existing reference ke Gemini untuk deduplicate
    existing_ref = pm.load_manual_reference(project_id)
    existing_ref_json = json.dumps(existing_ref, ensure_ascii=False, indent=2)
    has_existing = any(existing_ref.get(k) for k in ("characters", "locations", "terms", "modern_terms"))
    existing_block = (
        f"=== EXISTING REFERENCE (may contain duplicates/errors to fix) ===\n"
        f"{existing_ref_json}\n=== END EXISTING REFERENCE ===\n\n"
        if has_existing else ""
    )

    analysis_prompt = (
        f"You are a senior literary analyst and {tgt_lang} translation director.\n"
        f"Novel: {title} | Source: {src_lang} | Target: {tgt_lang}\n\n"
        f"IMPORTANT: Content marked [TRANSLATED: ...] shows chapters already translated. "
        f"These are provided ONLY for naming/term consistency — do NOT change any romanization, "
        f"character name, or term that is already established in those translations.\n\n"
        f"{existing_block}"
        f"=== NOVEL CONTENT ===\n{combined}\n=== END ===\n\n"
        f"Produce THREE clearly marked sections:\n\n"

        f"### SECTION 1: LAPORAN RISET ###\n"
        f"Write in {tgt_lang}:\n"
        f"## GAMBARAN UMUM\n"
        f"(Genre, tema, tone keseluruhan)\n\n"
        f"## PROFIL KARAKTER\n"
        f"(Nama asli | Peran | Sifat | Relasi — untuk setiap karakter yang muncul)\n\n"
        f"## DUNIA & SETTING\n"
        f"(Era, tempat, sistem kekuatan, tatanan sosial)\n\n"
        f"## GLOSARIUM\n"
        f"(Istilah teknis: jabatan, level, mata uang, item — + penjelasan singkat)\n\n"
        f"## FLAG KONTEN\n"
        f"(Dewasa/kekerasan/politik sensitif? Sebutkan atau tulis 'Aman')\n\n"

        f"### SECTION 2: TRANSLATION GUIDE ###\n"
        f"Write ENTIRELY IN ENGLISH. This guide is injected into every translation prompt and must be understood "
        f"by all LLMs including small local models — English ensures maximum compliance.\n"
        f"When referencing target-language ({tgt_lang}) terms or output examples, put them in quotes.\n\n"
        f"## TARGET STYLE\n"
        f"(Formal/informal, serious/lighthearted, light novel/literary — match the original tone)\n\n"
        f"## NAMING CONVENTIONS\n"
        f"(How to render names: full pinyin / abbreviated / combined with title, etc.)\n\n"
        f"## KEY PHRASES & EQUIVALENTS\n"
        f"(Signature expressions of this novel + their consistent, natural {tgt_lang} translations in quotes)\n\n"
        f"## SPECIAL INSTRUCTIONS FOR TRANSLATOR\n"
        f"(What MUST be preserved: term consistency, idioms, humor nuance, etc.)\n"
        f"REQUIRED: Does this novel use internet/modern terms (live stream, host, etc.)? "
        f"If yes, write: 'English loanwords already common in {tgt_lang} (host, live stream, "
        f"streaming, online, boss, level, etc.) MUST NOT be translated into stiff formal equivalents.'\n\n"

        f"### SECTION 3: REFERENCE JSON ###\n"
        f"Output ONLY valid JSON:\n"
        f"```json\n"
        f'{{"content_rating":"general|mature|explicit",'
        f'"characters":{{"OriginalName":"Romanized"}},'
        f'"locations":{{"OriginalName":"translated value"}},'
        f'"terms":{{"OriginalTerm":"Romanized (Meaning)"}},'
        f'"modern_terms":{{"OriginalTerm":"English loanword"}},'
        f'"character_profiles":['
        f'{{"original_name":"OriginalName","romanized_name":"Romanized","age":25,"gender":"male/female/unknown",'
        f'"aliases":[{{"original":"AliasInSourceLang","romanized":"RomanizedAlias","context":"when/why used"}}],'
        f'"relationships":[{{"with":"OtherRomanized","call_them":"honorific used","they_call_me":"honorific back","reason":"age/sect seniority/bet/rank/family"}}]}}'
        f']}}\n'
        f"```\n"
        f"character_profiles rules:\n"
        f"- Include ALL named characters found in the text.\n"
        f"- age: integer if stated or clearly implied, else null.\n"
        f"- aliases: ALL alternative names, nicknames, titles used for this character.\n"
        f"  context: when/why used (e.g. 'informal', 'imperial title', 'nickname by close friend').\n"
        f"  If none found, use [].\n"
        f"- relationships: only if an honorific or kinship term is used between characters.\n"
        f"  Include relationships established by bets/wagers — note the wager condition in 'reason'.\n"
        f"  If no relationship found for a character, use empty array [].\n"
        f"content_rating rules:\n"
        f"- 'general'  : no adult content\n"
        f"- 'mature'   : violence or dark themes, but no explicit sexual content\n"
        f"- 'explicit' : contains explicit sexual content (rape, harem, r18, monster+human sexual acts, etc.)\n"
        f"Base your rating on the actual content you read above, not just the title.\n\n"
        f"JSON rules:\n"
        f"- characters: romanized (pinyin/romaji) ONLY, never translate the name meaning.\n"
        f"- locations: translate geographic suffixes into {tgt_lang}, keep the proper name romanized.\n"
        f"  城(Cheng)=Kota, 殿(Dian)=Aula, 宫(Gong)=Istana, 河/水(He/Shui)=Sungai, 山(Shan)=Gunung, 门(Men)=Gerbang.\n"
        f"  e.g. 长安城→'Kota Chang\\'an', 显德殿→'Aula Xiande', 渭水→'Sungai Wei'.\n"
        f"  For places whose full name is meaningful (not just a suffix), use 'Romanized (Meaning)'.\n"
        f"  e.g. 东宫→'Dong Gong (Istana Timur)' because Dong=Timur adds meaning to the whole name.\n"
        f"  NEVER duplicate: do NOT write 'Kota Chang\\'an (Kota Chang\\'an)' or similar.\n"
        f"- terms: cultivation levels, titles, cultural concepts — write 'Romanized (Meaning in {tgt_lang})'.\n"
        f"  Meaning MUST be in {tgt_lang}, NEVER in English.\n"
        f"  EXCEPTION — Chinese internet slang with a good {tgt_lang} equivalent: translate DIRECTLY, no romanization.\n"
        f"  e.g. 躺平→'rebahan', 内卷→'persaingan ketat', 卷王→'Raja Kompetisi', 摸鱼→'bermalas-malasan',\n"
        f"       划水→'buang-buang waktu', 内耗→'konflik batin', 躺赢→'menang tanpa usaha'.\n"
        f"  WRONG: 'Tang Ping (rebahan)', 'Juan Wang (Raja Kompetisi)', 'Mo Yu (Slacking off)' — all wrong.\n"
        f"  RIGHT: just 'rebahan', 'Raja Kompetisi', 'bermalas-malasan' — no parentheses, no romanization.\n"
        f"  Do NOT write near-identical pairs like 'System (Sistem)' or 'Mission (Misi)'.\n"
        f"- modern_terms: internet/modern culture words specific to THIS novel that should STAY\n"
        f"  as English loanwords in {tgt_lang} translation. e.g. 主播→'host/streamer',\n"
        f"  直播→'live stream', 弹幕→'live chat', 系统→'System', 签到→'check-in',\n"
        f"  任务→'quest/mission', 积分→'points', 界面→'interface'. ONLY include if found in the text.\n"
        f"- Include ALL proper nouns found in the text.\n"
        f"DEDUPLICATION RULES (if EXISTING REFERENCE was provided above):\n"
        f"- Merge the existing reference with new findings into ONE clean, final reference.\n"
        f"- Remove duplicate entries that refer to the same entity (keep the most complete/correct one).\n"
        f"- Normalize inconsistent keys: if '李世民' appears as both '李世民' and 'Li Shimin' (a value used as key), "
        f"  keep the original {src_lang} form as key.\n"
        f"- Fix any wrong romanizations or mistranslations from the existing reference.\n"
        f"- The output JSON is the NEW AUTHORITATIVE reference — it will REPLACE the old one entirely."
    )

    raw_output = tr._run_gemini(analysis_prompt, timeout=240)

    if not raw_output:
        print("[-] Gemini did not respond. Check connection or try again.")
        input("Press Enter...")
        return

    print("[3/3] Processing and saving results...\n")

    # ── Parse 3 section ───────────────────────────────────────────────────────
    # Split by section headers
    sec1_match = re.search(r"###\s*SECTION 1.*?###([\s\S]*?)(?=###\s*SECTION 2|$)", raw_output)
    sec2_match = re.search(r"###\s*SECTION 2.*?###([\s\S]*?)(?=###\s*SECTION 3|$)", raw_output)
    json_match  = re.search(r"```json\s*([\s\S]*?)\s*```", raw_output)

    report_text = sec1_match.group(1).strip() if sec1_match else raw_output[:3000]
    guide_text  = sec2_match.group(1).strip() if sec2_match else ""
    new_entities = None

    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
            for k in ("characters", "locations", "terms", "modern_terms"):
                parsed.setdefault(k, {})
            parsed.setdefault("character_profiles", [])
            new_entities = {k: v for k, v in parsed.items()
                            if k in ("characters", "locations", "terms", "modern_terms", "character_profiles")}
            # Extract and save content_rating from Gemini's assessment
            detected_rating = parsed.get("content_rating", "").lower()
            if detected_rating in ("general", "mature", "explicit"):
                meta["content_rating"] = detected_rating
                pm.save_manual_metadata(project_id, meta)
                print(f"     [✓] Content rating detected by AI: '{detected_rating}'")
        except json.JSONDecodeError:
            pass

    # Riset ulang → REPLACE reference (Gemini sudah deduplicate)
    # Jika parse gagal, fallback ke merge agar tidak kehilangan data lama
    if new_entities:
        pm.save_manual_reference(project_id, new_entities)
        ref = new_entities
        print("     [✓] Reference updated (deduplicated by Gemini)")
    else:
        ref = pm.load_manual_reference(project_id)
        print("     [!] JSON parse failed — old reference retained")

    # Simpan translation guide sebagai JSON + teks
    guide_obj = {
        "source_lang":  src_lang,
        "target_lang":  tgt_lang,
        "guide_text":   guide_text,
        "analyzed_chapters": selected,
    }
    pm.save_translation_guide(project_id, guide_obj)

    # Simpan laporan lengkap
    raw_dir    = pm.get_raw_chapters_path(project_id)
    report_dir = os.path.join(os.path.dirname(raw_dir), "research")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, "project_research.txt")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"LAPORAN RISET PROJECT\nNovel: {title} | {src_lang} → {tgt_lang}\n")
        f.write(f"Chapter dianalisis: {', '.join(selected) or '(sinopsis saja)'}\n")
        f.write("=" * 56 + "\n\n")
        f.write("=== LAPORAN ===\n\n")
        f.write(report_text)
        f.write("\n\n=== PANDUAN TERJEMAHAN ===\n\n")
        f.write(guide_text)

    # Tampilkan ringkasan
    chars = len(ref.get("characters", {}))
    locs  = len(ref.get("locations", {}))
    terms = len(ref.get("terms", {}))

    clear_screen()
    print("=" * 56)
    print("  RESEARCH RESULTS")
    print("=" * 56)
    print(report_text[:2000])
    if len(report_text) > 2000:
        print(f"\n... (open file for full report)")

    if guide_text:
        print(f"\n{'─'*56}")
        print("  TRANSLATION GUIDE (will be used in all translations):")
        print("─" * 56)
        print(guide_text[:800])
        if len(guide_text) > 800:
            print("  ...")

    print(f"\n{'='*56}")
    print(f"  Reference : {chars} characters | {locs} locations | {terms} terms")
    print(f"  Guide     : translation_guide.json saved")
    print(f"  Report    : {report_file}")
    print(f"{'='*56}")
    input("\nPress Enter to go back...")


def _translate_metadata(project_id):
    """Minta Gemini terjemahkan title + synopsis ke target_lang, simpan di metadata."""
    meta     = pm.load_manual_metadata(project_id)
    title    = meta.get("title", "")
    synopsis = meta.get("synopsis", "")
    tgt_lang = meta.get("target_lang", "Indonesian")

    if not title and not synopsis:
        print("[-] Tidak ada judul/sinopsis untuk diterjemahkan.")
        input("Press Enter...")
        return

    print(f"[*] Gemini menerjemahkan judul & sinopsis ke {tgt_lang}...")
    prompt = (
        f"Translate the following novel title and synopsis into {tgt_lang}.\n"
        f"Return ONLY valid JSON with keys 'title' and 'synopsis'. No markdown, no explanation.\n\n"
        f"Title: {title}\n"
        f"Synopsis: {synopsis or '(kosong)'}\n\n"
        f"Output format:\n"
        f'{{ "title": "...", "synopsis": "..." }}'
    )
    out = tr._run_gemini(prompt, timeout=90)
    if not out:
        print("[-] Gemini tidak merespons.")
        input("Press Enter...")
        return

    import re as _re
    m = _re.search(r'\{[\s\S]*\}', out)
    if not m:
        print("[-] No JSON found in Gemini output.")
        input("Press Enter...")
        return

    try:
        data = json.loads(m.group())
        updates = {}
        if data.get("title"):
            updates["title_translated"] = data["title"]
        if data.get("synopsis"):
            updates["synopsis_translated"] = data["synopsis"]
        if updates:
            pm.update_manual_metadata(project_id, updates)
            print(f"     Title   : {updates.get('title_translated', '-')}")
            syn_prev = updates.get("synopsis_translated", "")
            print(f"     Synopsis: {syn_prev[:120]}{'...' if len(syn_prev) > 120 else ''}")
            print("[OK] Translation metadata saved.")
        else:
            print("[-] No translation found in output.")
    except json.JSONDecodeError:
        print("[-] Failed to parse JSON from Gemini.")
    input("Press Enter...")


def _show_reference(ref):
    clear_screen()
    print("--- Reference ---\n")
    for section, label in (
        ("characters", "CHARACTERS"),
        ("locations", "LOCATIONS"),
        ("terms", "TERMS"),
        ("modern_terms", "MODERN TERMS (kept as English loanwords)"),
    ):
        items = ref.get(section, {})
        if not items:
            continue
        print(f"[{label}] ({len(items)} entries)")
        for k, v in items.items():
            print(f"  {k} → {v}")
        print()
    input("Press Enter...")


def manual_translate_chapter(project_id, filename, engine_mode=None, batch_mode=False):
    """
    Proses translate satu chapter: Gemini analisis → translate per chunk.
    engine_mode: jika None, user diminta pilih. Jika sudah diisi (batch), langsung pakai.
    batch_mode : jika True, skip preview interaktif dan langsung return.
    """
    if not batch_mode:
        clear_screen()
    meta     = pm.load_manual_metadata(project_id)
    target   = meta.get("target_lang", "Indonesian")

    print(f"--- Translate: {filename} ---\n")

    raw_text = pm.load_raw_chapter(project_id, filename)
    _temp_dir = os.path.join(pm.MANUAL_DIR, project_id, "temp")
    if not raw_text:
        print(f"[-] {filename}: File not found or empty — skipped.")
        if not batch_mode:
            input("Press Enter...")
        return False

    print(f"  Text: {len(raw_text)} characters")
    print(f"  Target: {target}\n")

    # Select engine — hanya jika belum ditentukan (single mode)
    if engine_mode is None:
        import engines.nllb as _nllb
        nllb_info = _nllb.get_model_info() if _nllb.is_available() else "NOT INSTALLED"
        print("Translation engine:")
        print("  1. Gemini + Ollama           (Gemini: guide/analysis only — Ollama: all translation, hemat)")
        print("  2. Ollama only               (local, offline, no Gemini at all)")
        print("  3. Gemini primary + Ollama backup  (Gemini tiap chunk, Ollama backup jika Gemini gagal)")
        print("  4. Gemini + gemma3           (Gemini: guide/analysis only — gemma3: semua terjemahan)")
        print("  5. Gemini + translategemma   (Gemini: guide/analysis only — translategemma: semua terjemahan)")
        print(f"  --- [EXPERIMENT] NLLB: {nllb_info} ---")
        print("  6. NLLB + Gemini             (NLLB: CN→EN pivot — Gemini: EN→ID refine, Ollama fallback)")
        print("  7. NLLB + translategemma     (NLLB: CN→EN pivot — translategemma: EN→ID, Gemini guide)")
        print("  8. NLLB + gemma3             (NLLB: CN→EN pivot — gemma3: EN→ID, Gemini guide)")
        eng_c = input("Choice [1]: ").strip()
        if eng_c == "2":
            engine_mode = "ollama"
        elif eng_c == "3":
            engine_mode = "gemini_only"
        elif eng_c == "4":
            engine_mode = "gemini_gemma3"
        elif eng_c == "5":
            engine_mode = "gemini_translategemma"
        elif eng_c == "6":
            engine_mode = "nllb_gemini"
        elif eng_c == "7":
            engine_mode = "nllb_translategemma"
        elif eng_c == "8":
            engine_mode = "nllb_gemma3"
        else:
            engine_mode = "gemini_fallback"
    print()

    # Load translation guide if available
    guide = pm.load_translation_guide(project_id)
    guide_text = guide.get("guide_text", "")
    if guide_text:
        print(f"  [*] Translation guide found — will be applied.\n")

    # Load & inject chapter context (rolling summary + arc + mood)
    ch_ctx = pm.load_chapter_context(project_id)
    summaries = ch_ctx.get("chapter_summaries", [])
    if summaries or ch_ctx.get("current_arc") or ch_ctx.get("recent_characters_active"):
        ctx_lines = ["\n=== STORY CONTEXT (for continuity) ==="]
        if ch_ctx.get("current_arc"):
            ctx_lines.append(f"Current arc: {ch_ctx['current_arc']}")
        if ch_ctx.get("mood"):
            ctx_lines.append(f"Story mood: {ch_ctx['mood']}")
        if ch_ctx.get("recent_characters_active"):
            ctx_lines.append(f"Active characters: {', '.join(ch_ctx['recent_characters_active'])}")
        if summaries:
            ctx_lines.append("Recent chapter summaries (last 3):")
            for s in summaries[-3:]:
                ctx_lines.append(f"  - {s.get('chapter','?')}: {s.get('summary','')}")
        ctx_lines.append("=== END STORY CONTEXT ===\n")
        story_context_block = "\n".join(ctx_lines)
        guide_text = story_context_block + guide_text
        print(f"  [*] Story context loaded ({len(summaries)} summaries, arc: {ch_ctx.get('current_arc','')[:50]}...)\n")

    # Step 1: Gemini analyzes new chapter → update reference
    if engine_mode == "ollama":
        print("[1/3] Entity analysis skipped (Ollama-only mode)...")
        ref = pm.load_manual_reference(project_id)
        print(f"     Using existing ref: {len(ref.get('characters',{}))} characters, "
              f"{len(ref.get('locations',{}))} locations, {len(ref.get('terms',{}))} terms\n")
    else:
        ctx = f"Novel title: {meta.get('title','')}\n"
        if guide_text:
            ctx += f"Translation guide:\n{guide_text[:500]}\n"
        ref = pm.load_manual_reference(project_id)
        before_counts = {k: len(ref.get(k, {})) for k in ("characters", "locations", "terms", "modern_terms")}
        entities = tr.analyze_chapter_with_context(raw_text, ctx, existing_reference=ref)
        ref = tr.merge_reference(ref, entities)
        ref = tr.dedup_reference(ref)
        pm.save_manual_reference(project_id, ref)

        new_chars  = len(ref.get("characters", {})) - before_counts["characters"]
        new_locs   = len(ref.get("locations", {}))  - before_counts["locations"]
        new_terms  = len(ref.get("terms", {}))      - before_counts["terms"]
        new_mterms = len(ref.get("modern_terms", {})) - before_counts["modern_terms"]
        print(f"     +{new_chars} characters, +{new_locs} locations, +{new_terms} terms, +{new_mterms} modern terms")
        print(f"     Total ref: {len(ref.get('characters',{}))} characters, "
              f"{len(ref.get('locations',{}))} locations, {len(ref.get('terms',{}))} terms, "
              f"{len(ref.get('modern_terms',{}))} modern terms\n")

    # Step 2: Translate per chunk
    _src_lang = meta.get("source_lang", "Chinese")
    content_rating = meta.get("content_rating", "general")

    is_explicit = content_rating == "explicit"
    if is_explicit:
        models = tr.get_available_models_explicit(_src_lang)
        print(f"  [18+] Explicit content — using professional translator role prompt.")
    else:
        models = tr.get_available_models(_src_lang)

    chunks_est = max(1, len(raw_text) // 2000)
    engine_label = {"gemini_fallback": "Gemini + Ollama fallback",
                    "gemini_only": "Gemini only",
                    "ollama": "Ollama local",
                    "gemini_gemma3": "Gemini + gemma3",
                    "gemini_translategemma": "Gemini + translategemma",
                    "nllb_gemini": "NLLB pivot + Gemini refine",
                    "nllb_translategemma": "NLLB pivot + translategemma refine",
                    "nllb_gemma3": "NLLB pivot + gemma3 refine"}.get(engine_mode, engine_mode)
    print(f"[2/3] Translating... (~{chunks_est} chunks) | Engine: {engine_label}\n")

    def _progress(n, total, engine):
        done = n - 1 if engine.startswith("▶") else n
        bar = "#" * done + (">" if engine.startswith("▶") else "") + "." * (total - done - (1 if engine.startswith("▶") else 0))
        bar = bar[:total]
        print(f"\r  [{bar}] {n}/{total} — {engine}      ", end="", flush=True)

    if engine_mode == "ollama":
        translated, stats = tr.translate_with_ollama_only(
            raw_text, ref, target,
            ollama_models=models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
            is_explicit=is_explicit,
            temp_dir=_temp_dir,
        )
    elif engine_mode == "gemini_only":
        # Gemini utama, Ollama semua model sebagai backup — tidak ada kalimat yang gagal terjemah
        translated, stats = tr.translate_with_gemini_primary(
            raw_text, ref, target,
            ollama_models=models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
            is_explicit=is_explicit,
            temp_dir=_temp_dir,
        )
    elif engine_mode == "gemini_gemma3":
        # Gemini hanya analisis — gemma3 yang terjemahkan semua chunk
        gemma3_models = [m for m in models if "gemma3" in m or "gemma:3" in m or m.startswith("gemma3")]
        translated, stats = tr.translate_with_ollama_only(
            raw_text, ref, target,
            ollama_models=gemma3_models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
            source_lang=_src_lang,
            is_explicit=is_explicit,
            temp_dir=_temp_dir,
        )
    elif engine_mode == "gemini_translategemma":
        # Gemini hanya analisis — translategemma yang terjemahkan semua chunk
        tgemma_models = [m for m in models if "translategemma" in m]
        translated, stats = tr.translate_with_ollama_only(
            raw_text, ref, target,
            ollama_models=tgemma_models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
            source_lang=_src_lang,
            is_explicit=is_explicit,
            temp_dir=_temp_dir,
        )
    elif engine_mode in ("nllb_gemini", "nllb_translategemma", "nllb_gemma3"):
        refine = {"nllb_gemini": "gemini", "nllb_translategemma": "translategemma", "nllb_gemma3": "gemma3"}[engine_mode]
        translated, stats = tr.translate_with_nllb_pivot(
            raw_text, ref, target,
            ollama_models=models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
            source_lang=_src_lang,
            is_explicit=is_explicit,
            temp_dir=_temp_dir,
            refine_engine=refine,
        )
    else:
        # gemini_fallback: Gemini hanya untuk analisis/guide — Ollama menerjemahkan semua chunk
        translated, stats = tr.translate_with_ollama_only(
            raw_text, ref, target,
            ollama_models=models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
            source_lang=_src_lang,
            is_explicit=is_explicit,
            temp_dir=_temp_dir,
        )
    print()  # newline setelah progress bar

    if not translated:
        print(f"\n[-] {filename}: Translation failed entirely.")
        if not batch_mode:
            input("Press Enter...")
        return False

    g = stats.get("gemini", 0)
    o = stats.get("ollama", 0)
    f = stats.get("failed", 0)
    c = stats.get("censored", 0)
    print(f"     Gemini: {g} chunks | Ollama: {o} chunks | Failed: {f} chunks")

    # If censored content detected and not yet in explicit mode → offer upgrade + retry
    if c > 0 and not is_explicit and not batch_mode:
        print(f"\n  [!] {c} chunk(s) were refused/censored by local models.")
        print(f"      This chapter may contain explicit content not detected during research.")
        ans = input("  Upgrade content rating to 'explicit' and re-translate? (y/n): ").strip().lower()
        if ans == "y":
            meta["content_rating"] = "explicit"
            pm.save_manual_metadata(project_id, meta)
            print("  [OK] Content rating updated to 'explicit'. Re-translating with professional translator prompt...\n")
            explicit_models = tr.get_available_models_explicit(_src_lang)
            if engine_mode == "ollama":
                translated, stats = tr.translate_with_ollama_only(
                    raw_text, ref, target, ollama_models=explicit_models,
                    chunk_size=2000, progress_cb=_progress, guide_text=guide_text, is_explicit=True, temp_dir=_temp_dir,
                )
            elif engine_mode == "gemini_gemma3":
                _em = [m for m in explicit_models if "gemma3" in m or m.startswith("gemma3")]
                translated, stats = tr.translate_with_ollama_only(
                    raw_text, ref, target, ollama_models=_em,
                    chunk_size=2000, progress_cb=_progress, guide_text=guide_text,
                    source_lang=_src_lang, is_explicit=True, temp_dir=_temp_dir,
                )
            elif engine_mode == "gemini_translategemma":
                _em = [m for m in explicit_models if "translategemma" in m]
                translated, stats = tr.translate_with_ollama_only(
                    raw_text, ref, target, ollama_models=_em,
                    chunk_size=2000, progress_cb=_progress, guide_text=guide_text,
                    source_lang=_src_lang, is_explicit=True, temp_dir=_temp_dir,
                )
            elif engine_mode == "gemini_only":
                translated, stats = tr.translate_with_gemini_primary(
                    raw_text, ref, target, ollama_models=explicit_models,
                    chunk_size=2000, progress_cb=_progress, guide_text=guide_text, is_explicit=True, temp_dir=_temp_dir,
                )
            else:
                # gemini_fallback: Ollama menerjemahkan, Gemini hanya guide
                translated, stats = tr.translate_with_ollama_only(
                    raw_text, ref, target, ollama_models=explicit_models,
                    chunk_size=2000, progress_cb=_progress, guide_text=guide_text,
                    source_lang=_src_lang, is_explicit=True, temp_dir=_temp_dir,
                )
            print()
            if not translated:
                print(f"\n[-] Re-translation failed.")
                if not batch_mode:
                    input("Press Enter...")
                return False

    # Step 3: Save
    print(f"\n[3/3] Saving...")
    save_path = pm.save_manual_chapter_translated(project_id, filename, translated)
    print(f"     Saved: {save_path}")

    # Update name index (for continuity check)
    _update_name_index(project_id, filename, translated, ref.get("character_profiles", []))

    # Step 4: Generate rolling summary & update chapter_context.json
    novel_title = meta.get("title", project_id)
    ch_ctx = pm.load_chapter_context(project_id)
    print(f"\n[*] Generating chapter summary for context memory...")
    summary_data = tr.generate_chapter_summary(
        translated_text=translated,
        chapter_name=filename,
        novel_title=novel_title,
        target_lang=target,
        existing_context=ch_ctx,
    )
    if summary_data:
        ch_ctx["last_translated"] = filename
        ch_ctx["current_arc"]     = summary_data.get("current_arc", ch_ctx.get("current_arc", ""))
        ch_ctx["mood"]            = summary_data.get("mood", ch_ctx.get("mood", ""))
        ch_ctx["recent_characters_active"] = summary_data.get("recent_characters_active", [])
        summaries = ch_ctx.get("chapter_summaries", [])
        summaries.append({"chapter": filename, "summary": summary_data.get("summary", "")})
        ch_ctx["chapter_summaries"] = summaries
        pm.save_chapter_context(project_id, ch_ctx)
        print(f"     Summary: {summary_data.get('summary','')[:100]}...")
        print(f"     Arc    : {ch_ctx['current_arc'][:80]}...")
    else:
        print("     [!] Summary skipped (Gemini unavailable or Ollama-only mode).")

    if batch_mode:
        print(f"\n[OK] {filename} done. Continuing batch...\n")
        print("-" * 56)
        return True

    # Preview (single mode only)
    print("\n" + "=" * 56)
    print(f"  PREVIEW — {filename}")
    print("=" * 56)
    lines = translated.splitlines()
    print("\n".join(lines[:15]))
    if len(lines) > 15:
        print(f"\n... ({len(lines)} lines — open file for full content)")

    print(f"\n[L] View Log  [Enter] Back")
    if input("Choice: ").strip().lower() == 'l':
        clear_screen()
        print(tail_log(40))
        input("\nPress Enter...")
    return True


def batch_translate_chapters(project_id, chapter_list):
    """
    Terjemahkan beberapa chapter secara berurutan.
    Semua pipeline tetap aktif: entity analysis, reference update, chapter context, rolling summary.
    chapter_list: list of filename strings
    """
    clear_screen()
    print("=" * 56)
    print("  BATCH TRANSLATION")
    print("=" * 56)
    print(f"  Chapters to translate: {len(chapter_list)}")
    for i, f in enumerate(chapter_list, 1):
        print(f"  {i}. {f}")
    print()

    # Pilih engine sekali untuk semua chapter
    import engines.nllb as _nllb
    nllb_info = _nllb.get_model_info() if _nllb.is_available() else "NOT INSTALLED"
    print("Translation engine (applies to ALL chapters):")
    print("  1. Gemini + Ollama           (Gemini: guide/analysis only — Ollama: all translation, hemat)")
    print("  2. Ollama only               (local, offline, no Gemini at all)")
    print("  3. Gemini primary + Ollama backup  (Gemini tiap chunk, Ollama backup jika Gemini gagal)")
    print("  4. Gemini + gemma3           (Gemini: guide/analysis only — gemma3: semua terjemahan)")
    print("  5. Gemini + translategemma   (Gemini: guide/analysis only — translategemma: semua terjemahan)")
    print(f"  --- [EXPERIMENT] NLLB: {nllb_info} ---")
    print("  6. NLLB + Gemini             (NLLB: CN→EN pivot — Gemini: EN→ID refine, Ollama fallback)")
    print("  7. NLLB + translategemma     (NLLB: CN→EN pivot — translategemma: EN→ID, Gemini guide)")
    print("  8. NLLB + gemma3             (NLLB: CN→EN pivot — gemma3: EN→ID, Gemini guide)")
    eng_c = input("Choice [1]: ").strip()
    if eng_c == "2":
        engine_mode = "ollama"
    elif eng_c == "3":
        engine_mode = "gemini_only"
    elif eng_c == "4":
        engine_mode = "gemini_gemma3"
    elif eng_c == "5":
        engine_mode = "gemini_translategemma"
    elif eng_c == "6":
        engine_mode = "nllb_gemini"
    elif eng_c == "7":
        engine_mode = "nllb_translategemma"
    elif eng_c == "8":
        engine_mode = "nllb_gemma3"
    else:
        engine_mode = "gemini_fallback"

    print(f"\n[*] Starting batch: {len(chapter_list)} chapters | engine={engine_mode}")
    print("=" * 56)

    ok, skipped, failed = 0, 0, 0
    for i, filename in enumerate(chapter_list, 1):
        print(f"\n[Batch {i}/{len(chapter_list)}] {filename}")
        result = manual_translate_chapter(
            project_id, filename,
            engine_mode=engine_mode,
            batch_mode=True,
        )
        if result is True:
            ok += 1
        elif result is False:
            failed += 1
        else:
            skipped += 1

    # Summary
    print("\n" + "=" * 56)
    print("  BATCH COMPLETE")
    print("=" * 56)
    print(f"  Done    : {ok}")
    print(f"  Failed  : {failed}")
    print(f"  Skipped : {skipped}")
    print("=" * 56)
    input("\nPress Enter to go back...")



def retranslate_chapter(project_id):
    """Re-translate satu chapter yang sudah ditranslate — overwrite dengan reference terbaru."""
    clear_screen()
    translated = pm.list_translated_chapters(project_id)
    if not translated:
        print("[-] No translated chapters found.")
        input("Press Enter...")
        return

    print("=" * 56)
    print("  RE-TRANSLATE CHAPTER")
    print("=" * 56)
    print("  Select a chapter to re-translate (overwrites existing):\n")
    for i, fname in enumerate(translated, 1):
        print(f"  {i:3}. {fname}")
    print()
    choice = input(f"Chapter number [1-{len(translated)}] or [B] Back: ").strip().lower()
    if choice == 'b' or not choice:
        return
    if not choice.isdigit() or not (1 <= int(choice) <= len(translated)):
        print("[-] Invalid selection.")
        input("Press Enter...")
        return

    filename = translated[int(choice) - 1]
    raw_text = pm.load_raw_chapter(project_id, filename)
    if not raw_text:
        print(f"[-] Raw file '{filename}' not found or empty — cannot re-translate.")
        input("Press Enter...")
        return

    print(f"\n  Chapter : {filename}")
    print(f"  Raw size: {len(raw_text)} chars")
    confirm = input("\n  Overwrite existing translation? [y/N]: ").strip().lower()
    if confirm != 'y':
        return

    manual_translate_chapter(project_id, filename)


def _update_name_index(project_id, filename, translated_text, profiles):
    """Update character_appearances.json: catat canonical names yang muncul di chapter."""
    import re, json
    index_path = os.path.join(pm.MANUAL_DIR, project_id, "character_appearances.json")
    try:
        index = json.load(open(index_path, encoding='utf-8')) if os.path.exists(index_path) else {}
    except Exception:
        index = {}
    found = []
    for p in profiles:
        rname = p.get("romanized_name", "").strip()
        if not rname:
            continue
        if re.search(r'\b' + re.escape(rname) + r'\b', translated_text, re.IGNORECASE):
            found.append(rname)
    index[filename] = found
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def continuity_check(project_id):
    """
    Scan semua translated chapter, flag nama karakter yang tidak konsisten.
    Menggunakan character_appearances.json sebagai index — hanya cek chapter
    di mana karakter diketahui muncul, dengan filter huruf awal yang sama.
    """
    import difflib, re, json

    clear_screen()
    print("=" * 56)
    print("  CONTINUITY CHECK")
    print("=" * 56)

    ref = pm.load_manual_reference(project_id)
    profiles = ref.get("character_profiles", [])

    if not profiles:
        print("\n[-] No character profiles found in reference.json.")
        print("    Run [S] Research first to generate character profiles.")
        input("Press Enter...")
        return

    # Build set of canonical names and known aliases (all lowercase → canonical)
    canonical_map = {}   # lower → display name
    for p in profiles:
        rname = p.get("romanized_name", "").strip()
        if not rname:
            continue
        canonical_map[rname.lower()] = rname
        for alias in p.get("aliases", []):
            if isinstance(alias, dict):
                r = alias.get("romanized", "").strip()
            else:
                r = str(alias).strip()
            if r:
                canonical_map[r.lower()] = rname  # alias also accepted

    if not canonical_map:
        print("\n[-] Character profiles have no romanized names.")
        input("Press Enter...")
        return

    canonical_names = list(canonical_map.keys())

    translated = pm.list_translated_chapters(project_id)
    if not translated:
        print("\n[-] No translated chapters found.")
        input("Press Enter...")
        return

    # Load name index (chapter → list of canonical names that appear)
    index_path = os.path.join(pm.MANUAL_DIR, project_id, "character_appearances.json")
    try:
        name_index = json.load(open(index_path, encoding='utf-8')) if os.path.exists(index_path) else {}
    except Exception:
        name_index = {}

    # Rebuild index for chapters that aren't indexed yet
    for filename in translated:
        if filename not in name_index:
            text = pm.load_translated_chapter(project_id, filename)
            _update_name_index(project_id, filename, text, profiles)
            found = [p.get("romanized_name","") for p in profiles
                     if p.get("romanized_name") and
                     re.search(r'\b' + re.escape(p["romanized_name"]) + r'\b', text, re.IGNORECASE)]
            name_index[filename] = found

    print(f"\n  Checking {len(translated)} chapters against {len([p for p in profiles if p.get('romanized_name')])} character names...\n")

    # Stopwords: kata Indonesia umum yang bentuknya mirip nama tapi bukan nama
    STOPWORDS_ID = {
        "Dia", "Dan", "Ini", "Itu", "Ada", "Jika", "Tapi", "Atau", "Lain",
        "Dari", "Pada", "Kami", "Kamu", "Aku", "Dia", "Mereka", "Kita",
        "Namun", "Saat", "Akan", "Yang", "Untuk", "Tidak", "Dengan", "Sudah",
        "Bisa", "Juga", "Sama", "Saja", "Atas", "Bawah", "Tanpa", "Lebih",
        "Masih", "Hanya", "Semua", "Sangat", "Setelah", "Sebelum", "Karena",
        "Tetapi", "Ketika", "Hingga", "Kepada", "Dalam", "Antara", "Bahwa",
        "Saya", "Anda", "Beliau", "Tuan", "Nyonya", "Nona", "Kakak", "Adik",
        "Ayah", "Ibu", "Paman", "Bibi", "Nenek", "Kakek",
        # Kata umum yang sering false-positive dengan nama karakter
        "Mana", "Anak", "Aliran", "Angin", "Asing", "Alam", "Awal",
        "Borgol", "Bukan", "Berkas", "Badan", "Bagian",
        "Udara", "Usia", "Ujung",
    }

    # Regex: capitalized words (likely proper nouns), min 3 chars
    word_re = re.compile(r'\b([A-Z][a-zA-Z]{2,})\b')

    # by_canonical: {canonical_name -> {variant -> [filenames]}}
    by_canonical = {}

    for filename in translated:
        text = pm.load_translated_chapter(project_id, filename)
        words = set(word_re.findall(text))

        # Ambil hanya karakter yang diketahui muncul di chapter ini (dari index)
        chars_in_chapter = name_index.get(filename, list(canonical_map.values()))
        active_canonicals = {c.lower(): canonical_map[c.lower()]
                             for c in [n.lower() for n in chars_in_chapter]
                             if c.lower() in canonical_map}

        for word in words:
            if word in STOPWORDS_ID:
                continue

            wl = word.lower()
            if wl in canonical_map:
                continue   # exact match — fine

            for cname_lower, canonical_display in active_canonicals.items():
                # Filter 1: huruf awal harus sama (case-insensitive)
                if wl[0] != cname_lower[0]:
                    continue
                # Filter 2: panjang tidak boleh beda lebih dari 2
                if abs(len(wl) - len(cname_lower)) > 2:
                    continue
                # Filter 3: similarity ratio ≥ 0.75
                ratio = difflib.SequenceMatcher(None, wl, cname_lower).ratio()
                if ratio >= 0.75 and ratio < 1.0:
                    if canonical_display not in by_canonical:
                        by_canonical[canonical_display] = {}
                    if word not in by_canonical[canonical_display]:
                        by_canonical[canonical_display][word] = []
                    if filename not in by_canonical[canonical_display][word]:
                        by_canonical[canonical_display][word].append(filename)
                    break

    if not by_canonical:
        print("  [OK] No inconsistencies detected!\n")
        input("Press Enter...")
        return

    # Display grouped by canonical character
    def _show_results():
        clear_screen()
        print("=" * 56)
        print("  CONTINUITY CHECK RESULTS")
        print("=" * 56)
        char_list = sorted(by_canonical.keys())
        for idx, cname in enumerate(char_list, 1):
            variants = by_canonical[cname]
            total_chapters = set(ch for chs in variants.values() for ch in chs)
            print(f"\n  [{idx}] {cname}  ({len(total_chapters)} chapter(s) affected)")
            for variant, chapters in sorted(variants.items(), key=lambda x: -len(x[1])):
                print(f"       '{variant}' → found in: {', '.join(chapters)}")
        print()
        print("-" * 56)
        print("  [1-N] Fix character  [W] Write report  [Enter] Back")
        return char_list

    def _do_fix(cname):
        """Replace semua variant → canonical di semua chapter yang terdampak."""
        variants = by_canonical[cname]
        affected = sorted(set(ch for chs in variants.values() for ch in chs))

        clear_screen()
        print(f"  Fix: '{cname}'")
        print("  Variants to replace: " + ", ".join("'" + v + "'" for v in variants))
        print(f"  Chapters affected  : {len(affected)}")
        print()
        for v, chs in variants.items():
            for ch in chs:
                text = pm.load_translated_chapter(project_id, ch)
                count = len(re.findall(rf'\b{re.escape(v)}\b', text))
                print(f"    '{v}' → '{cname}' in {ch}  ({count} occurrence(s))")
        print()
        confirm = input(f"  Replace ALL occurrences of these variants with '{cname}'? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("  Cancelled.")
            input("Press Enter...")
            return

        trans_dir = os.path.join(pm.MANUAL_DIR, project_id, "chapters", "translated")
        total_replaced = 0
        for filename in affected:
            fpath = os.path.join(trans_dir, filename)
            text = pm.load_translated_chapter(project_id, filename)
            new_text = text
            for variant in variants:
                new_text, n = re.subn(rf'\b{re.escape(variant)}\b', cname, new_text)
                total_replaced += n
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(new_text)
            print(f"    [OK] {filename}")

        # Remove fixed character from by_canonical so it disappears from results
        del by_canonical[cname]

        print(f"\n  [OK] {total_replaced} replacement(s) across {len(affected)} chapter(s).")
        input("Press Enter...")

    # Main interaction loop
    while True:
        char_list = _show_results()
        if not by_canonical:
            print("  [OK] All issues resolved!")
            input("Press Enter...")
            return
        cmd = input("Choice: ").strip().lower()
        if not cmd:
            return
        if cmd == 'w':
            report_path = os.path.join(pm.MANUAL_DIR, project_id, "continuity_report.txt")
            lines = [f"Continuity Check Report — {project_id}\n{'='*56}\n"]
            for cname in sorted(by_canonical.keys()):
                lines.append(f"[{cname}]")
                for variant, chapters in by_canonical[cname].items():
                    lines.append(f"  '{variant}' found in: {', '.join(chapters)}")
                lines.append("")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            print(f"\n  [OK] Report saved: {report_path}")
            input("Press Enter...")
        elif cmd.isdigit() and 1 <= int(cmd) <= len(char_list):
            _do_fix(char_list[int(cmd) - 1])
        else:
            return


def _save_reference_snapshot(project_id):
    """Simpan snapshot reference.json saat ini sebagai baseline untuk sync berikutnya."""
    import json
    ref_path  = os.path.join(pm.MANUAL_DIR, project_id, "reference.json")
    snap_path = os.path.join(pm.MANUAL_DIR, project_id, "reference_snapshot.json")
    if os.path.exists(ref_path):
        import shutil
        shutil.copy2(ref_path, snap_path)


def sync_reference(project_id):
    """
    Bandingkan reference.json dengan reference_snapshot.json.
    Setiap nilai yang berubah → replace di semua translated chapters.
    Setelah selesai, update snapshot.
    """
    import json, re

    clear_screen()
    print("=" * 56)
    print("  SYNC REFERENCE → TRANSLATED CHAPTERS")
    print("=" * 56)

    ref_path  = os.path.join(pm.MANUAL_DIR, project_id, "reference.json")
    snap_path = os.path.join(pm.MANUAL_DIR, project_id, "reference_snapshot.json")

    if not os.path.exists(snap_path):
        print("\n[-] Snapshot tidak ditemukan. Membuat snapshot sekarang...")
        _save_reference_snapshot(project_id)
        print("  [OK] Snapshot dibuat. Edit reference.json lalu jalankan Sync lagi.")
        input("Press Enter...")
        return

    ref  = json.load(open(ref_path,  encoding='utf-8'))
    snap = json.load(open(snap_path, encoding='utf-8'))

    # ── Build replacement map: old_value → new_value ──────────────────────────
    replace_map = {}  # {old_str: new_str}

    def _add(old, new):
        old, new = str(old).strip(), str(new).strip()
        if old and new and old != new:
            replace_map[old] = new

    # 1. Flat dicts: characters, locations, terms, modern_terms
    for key in ("characters", "locations", "terms", "modern_terms"):
        old_dict = snap.get(key, {})
        new_dict = ref.get(key, {})
        # Changed values
        for k in old_dict:
            if k in new_dict and old_dict[k] != new_dict[k]:
                _add(old_dict[k], new_dict[k])
        # Also check if key itself renamed (old key not in new → find by similar value)
        # (skip for now — too ambiguous)

    # 2. character_profiles: romanized_name + aliases
    old_profiles = {p.get("romanized_name",""): p for p in snap.get("character_profiles", []) if p.get("romanized_name")}
    new_profiles = {p.get("romanized_name",""): p for p in ref.get("character_profiles", [])  if p.get("romanized_name")}

    for old_name, old_p in old_profiles.items():
        # Name itself changed
        if old_name not in new_profiles:
            # Find by matching original_name or first alias
            for new_name, new_p in new_profiles.items():
                if new_p.get("original_name") == old_p.get("original_name"):
                    _add(old_name, new_name)
                    old_name = new_name  # track for alias comparison
                    break
        # Aliases changed
        new_p = new_profiles.get(old_name, {})
        old_aliases = old_p.get("aliases", [])
        new_aliases = new_p.get("aliases", [])
        for i, old_a in enumerate(old_aliases):
            old_r = old_a.get("romanized","").strip() if isinstance(old_a, dict) else str(old_a).strip()
            if i < len(new_aliases):
                new_a = new_aliases[i]
                new_r = new_a.get("romanized","").strip() if isinstance(new_a, dict) else str(new_a).strip()
                _add(old_r, new_r)

    if not replace_map:
        print("\n  [OK] Tidak ada perubahan terdeteksi antara reference dan snapshot.")
        print("  (Edit reference.json terlebih dahulu, lalu jalankan Sync)")
        input("Press Enter...")
        return

    def _make_pattern(s):
        escaped = re.escape(s)
        return r'(?<!\w)' + escaped + r'(?!\w)'

    translated = pm.list_translated_chapters(project_id)
    if not translated:
        print("\n[-] Tidak ada translated chapter.")
        input("Press Enter...")
        return

    # ── Scan occurrences ──────────────────────────────────────────────────────
    print("  Mencari occurrence di translated chapters...\n")
    preview = {}  # {filename: {old: [line_numbers]}}
    for fname in translated:
        text = pm.load_translated_chapter(project_id, fname)
        lines = text.splitlines()
        for old in replace_map:
            pat = _make_pattern(old)
            matched_lines = [i+1 for i, l in enumerate(lines) if re.search(pat, l, re.IGNORECASE)]
            if matched_lines:
                preview.setdefault(fname, {})[old] = matched_lines

    # ── Tampilkan laporan lengkap ─────────────────────────────────────────────
    print("=" * 56)
    print("  LAPORAN PERUBAHAN")
    print("=" * 56)
    print(f"\n  Perubahan di reference ({len(replace_map)} item):")
    for old, new in replace_map.items():
        total_occ = sum(len(v.get(old,[])) for v in preview.values())
        found_str = f"{total_occ} occurrence di {sum(1 for v in preview.values() if old in v)} chapter(s)" if total_occ else "tidak ditemukan di chapters"
        print(f"    '{old}'  →  '{new}'  [{found_str}]")

    if preview:
        print(f"\n  Detail lokasi:")
        for fname in sorted(preview):
            for old, linenos in preview[fname].items():
                lines_str = ", ".join(str(n) for n in linenos[:10])
                if len(linenos) > 10:
                    lines_str += f"... (+{len(linenos)-10})"
                print(f"    {fname} baris {lines_str}  →  '{old}'")
    else:
        print("\n  [INFO] Tidak ada occurrence ditemukan di translated chapters.")

    print()
    confirm = input("  Lanjutkan sync? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("  Dibatalkan. Snapshot tidak diupdate.")
        input("Press Enter...")
        return

    if not preview:
        # Tidak ada yang perlu direplace, tapi user konfirmasi → update snapshot
        _save_reference_snapshot(project_id)
        print("  Snapshot diupdate (tidak ada chapter yang berubah).")
        input("Press Enter...")
        return

    # ── Apply replacements ────────────────────────────────────────────────────
    import datetime
    trans_dir = os.path.join(pm.MANUAL_DIR, project_id, "chapters", "translated")
    log_lines = [
        f"SYNC REFERENCE LOG",
        f"Project  : {project_id}",
        f"Waktu    : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"=" * 56,
        f"Perubahan reference:",
    ]
    for old, new in replace_map.items():
        log_lines.append(f"  '{old}'  →  '{new}'")
    log_lines.append(f"\nHasil replace:")

    total_replaced = 0
    for fname in sorted(preview):
        text = pm.load_translated_chapter(project_id, fname)
        new_text = text
        file_total = 0
        for old, new in replace_map.items():
            new_text, n = re.subn(_make_pattern(old), new, new_text, flags=re.IGNORECASE)
            total_replaced += n
            file_total += n
        fpath = os.path.join(trans_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(new_text)
        print(f"  [OK] {fname}  ({file_total} replacement)")
        log_lines.append(f"  {fname}: {file_total} replacement(s)")

    # Tulis log file
    log_path = os.path.join(pm.MANUAL_DIR, project_id, "sync_log.txt")
    log_exists = os.path.exists(log_path)
    with open(log_path, "a", encoding="utf-8") as f:
        if log_exists:
            f.write("\n\n")
        f.write("\n".join(log_lines))
        f.write(f"\n\nTotal: {total_replaced} replacement(s) di {len(preview)} chapter(s).")

    # Update snapshot
    _save_reference_snapshot(project_id)

    print(f"\n  [OK] {total_replaced} replacement(s) di {len(preview)} chapter(s).")
    print(f"  Log disimpan: sync_log.txt")
    print("  Snapshot diupdate.")
    input("Press Enter...")


def generate_alt_titles(project_id):
    """Gemini generate judul alternatif untuk platform seperti Fizzo."""
    clear_screen()
    meta     = pm.load_manual_metadata(project_id)
    title    = meta.get("title", "")
    eng_name = meta.get("english_name", "")
    tgt_lang = meta.get("target_lang", "Indonesian")
    synopsis = meta.get("synopsis", "")
    guide    = pm.load_translation_guide(project_id)
    ref      = pm.load_manual_reference(project_id)

    print("=" * 56)
    print("  GENERATE ALTERNATIVE TITLES")
    print("=" * 56)
    print(f"  Novel : {title}")
    print(f"  Target: {tgt_lang}\n")
    print("[*] Requesting Gemini to generate alternative titles...\n")

    # Kumpulkan konteks
    chars_sample = ", ".join(list(ref.get("characters", {}).values())[:6])
    terms_sample = ", ".join(list(ref.get("terms", {}).values())[:6])
    report_snippet = guide.get("guide_text", "")[:400]

    prompt = (
        f"You are a creative {tgt_lang} novel title specialist for web novel platforms.\n\n"
        f"Original title: {title}\n"
        f"English name: {eng_name}\n"
        f"Target language: {tgt_lang}\n"
        f"Synopsis: {synopsis or '(tidak tersedia)'}\n"
        f"Main characters: {chars_sample or '(tidak tersedia)'}\n"
        f"Key terms/world: {terms_sample or '(tidak tersedia)'}\n"
        f"Story tone/style: {report_snippet or '(tidak tersedia)'}\n\n"
        f"Generate 10 alternative titles in {tgt_lang} for uploading to web novel platforms (like Fizzo).\n"
        f"Rules:\n"
        f"- Catchy, clickbait-friendly but not misleading\n"
        f"- Mix styles: descriptive, dramatic, funny, intriguing\n"
        f"- Max 10 words per title\n"
        f"- Do NOT use the original Chinese/Japanese title words\n"
        f"- Format: numbered list with brief explanation why each works\n\n"
        f"Also suggest 3 tagline options (1 sentence each) for the novel description."
    )

    result = tr._run_gemini(prompt, timeout=90)
    if not result:
        print("[-] Gemini did not respond.")
        input("Press Enter...")
        return

    clear_screen()
    print("=" * 56)
    print("  ALTERNATIVE TITLES")
    print("=" * 56)
    print(result)

    # Save
    raw_dir    = pm.get_raw_chapters_path(project_id)
    report_dir = os.path.join(os.path.dirname(raw_dir), "research")
    os.makedirs(report_dir, exist_ok=True)
    out_file = os.path.join(report_dir, "alternative_titles.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"ALTERNATIVE TITLES — {title}\n{'='*56}\n\n{result}")
    print(f"\n[*] Saved: {out_file}")
    input("\nPress Enter...")


def generate_image_prompt(project_id):
    """Gemini generate prompt untuk membuat cover image (Midjourney/DALL-E/SD/Gemini Image/Grok)."""
    clear_screen()
    meta     = pm.load_manual_metadata(project_id)
    title    = meta.get("title", "")
    src_lang = meta.get("source_lang", "Chinese")
    synopsis = meta.get("synopsis", "")
    guide    = pm.load_translation_guide(project_id)
    ref      = pm.load_manual_reference(project_id)

    print("=" * 56)
    print("  GENERATE IMAGE PROMPT (Cover Novel)")
    print("=" * 56)
    print(f"  Novel : {title}\n")

    print("Target platform:")
    print("  1. Midjourney")
    print("  2. DALL-E / ChatGPT Image")
    print("  3. Stable Diffusion")
    print("  4. Gemini Image (Imagen 3)")
    print("  5. Grok Aurora")
    print("  6. General (all platforms)")
    plat_c = input("Choice [1]: ").strip()
    platform = {
        "2": "DALL-E",
        "3": "Stable Diffusion",
        "4": "Gemini Image",
        "5": "Grok Aurora",
        "6": "General",
    }.get(plat_c, "Midjourney")

    print(f"\n[*] Requesting Gemini to generate image prompt for {platform}...\n")

    chars_detail = "\n".join(f"  {k}: {v}" for k, v in list(ref.get("characters", {}).items())[:5])
    locs_detail  = ", ".join(list(ref.get("locations", {}).values())[:4])
    guide_tone   = guide.get("guide_text", "")[:300]

    # Platform-specific prompt guidance
    platform_hints = {
        "Midjourney": (
            "Format: concise English prompt with style modifiers separated by commas. "
            "End with technical params like --ar 2:3 --style raw --v 6. "
            "Use Midjourney-specific keywords (e.g. --niji 6 for anime style)."
        ),
        "DALL-E": (
            "Format: natural descriptive English paragraph (2-4 sentences). "
            "DALL-E 3 works best with rich scene descriptions rather than tag lists. "
            "Include art style, lighting, composition, and mood in flowing prose."
        ),
        "Stable Diffusion": (
            "Format: comma-separated English tags. Include: subject, art style, quality tags "
            "(masterpiece, best quality, 8k), lighting, color palette. "
            "Also provide a separate NEGATIVE PROMPT list of things to avoid."
        ),
        "Gemini Image": (
            "Format: rich, natural-language English scene description. "
            "Gemini Imagen 3 excels with detailed narrative prompts — describe the scene as if "
            "writing a vivid paragraph for a film director. "
            "Focus on: subject details, environment, lighting, mood, and art style. "
            "No technical tags or parameters needed — just clear, detailed, vivid description."
        ),
        "Grok Aurora": (
            "Format: detailed English prompt, can be longer than Midjourney. "
            "Grok Aurora (xAI) handles natural language well but also responds to style keywords. "
            "Include character details, setting, art style, and mood. "
            "Mix descriptive sentences with style tags for best results. No special parameters needed."
        ),
        "General": (
            "Provide prompts for ALL major platforms: Midjourney, DALL-E, Stable Diffusion, "
            "Gemini Image, and Grok Aurora. Label each section clearly with the platform name."
        ),
    }
    hint = platform_hints.get(platform, "")

    prompt = (
        f"You are an expert AI image prompt engineer for novel cover art.\n\n"
        f"Novel: {title} ({src_lang} web novel)\n"
        f"Synopsis: {synopsis or '(tidak tersedia)'}\n"
        f"Main characters:\n{chars_detail or '  (tidak tersedia)'}\n"
        f"Key locations: {locs_detail or '(tidak tersedia)'}\n"
        f"Story tone: {guide_tone or '(tidak tersedia)'}\n\n"
        f"Generate cover art prompts optimized for **{platform}**.\n"
        f"Platform guidance: {hint}\n\n"
        f"Provide:\n"
        f"1. **MAIN PROMPT** — Full detailed prompt (English) for a stunning novel cover:\n"
        f"   - Main character visual description (appearance, clothing, pose)\n"
        f"   - Background/setting atmosphere\n"
        f"   - Art style (anime/manhwa/realistic/painterly — match the novel genre)\n"
        f"   - Lighting, color palette, mood\n"
        f"   - Technical format appropriate for {platform}\n\n"
        f"2. **NEGATIVE PROMPT** (things to avoid — skip if platform doesn't use negative prompts)\n\n"
        f"3. **ALTERNATIVE CONCEPT** — A second composition idea (different pose/scene)\n\n"
        f"4. **STYLE TAGS** — 5-8 concise style keywords for quick iteration\n\n"
        f"Write prompts in English (standard for image AI). Explain design choices briefly in Indonesian."
    )

    result = tr._run_gemini(prompt, timeout=120)
    if not result:
        print("[-] Gemini did not respond.")
        input("Press Enter...")
        return

    clear_screen()
    print("=" * 56)
    print(f"  IMAGE PROMPT — {platform}")
    print("=" * 56)
    print(result)

    # Save
    raw_dir    = pm.get_raw_chapters_path(project_id)
    report_dir = os.path.join(os.path.dirname(raw_dir), "research")
    os.makedirs(report_dir, exist_ok=True)
    out_file = os.path.join(report_dir, f"image_prompt_{platform.lower().replace(' ','_')}.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"IMAGE PROMPT — {title} | Platform: {platform}\n{'='*56}\n\n{result}")
    print(f"\n[*] Saved: {out_file}")
    input("\nPress Enter...")


def manage_projects():
    clear_screen()
    print("--- Active Projects ---")
    projects = pm.list_projects()
    if not projects:
        print("No projects found.")
    else:
        for i, p in enumerate(projects):
            meta = pm.load_metadata(p)
            title = meta.get("title", p)
            ch_count = meta.get("chapter_count", "?")
            print(f"{i+1}. {title} ({ch_count} chapters) [{p}]")
    input("\nPress Enter to return...")

if __name__ == "__main__":
    main_menu()
