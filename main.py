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
        print("      NOVEL TRANSLATOR - CLI v0.2")
        print("========================================")
        print("1. Discover Novels (Browse Sites)")
        print("2. Initialize Project from URL")
        print("3. Manual Translate (Paste Teks)")
        print("4. Manage Existing Projects")
        print("5. Exit")
        print("----------------------------------------")

        choice = input("Select an option: ").strip()

        if choice == '1':
            browse_sites(manager)
        elif choice == '2':
            init_project_from_url(manager)
        elif choice == '3':
            manual_translate_menu()
        elif choice == '4':
            manage_projects()
        elif choice == '5':
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
        print("  MANUAL TRANSLATE")
        print("=" * 52)
        print("1. Project Baru")
        print("2. Project yang Ada")
        print("3. Kembali")
        print("-" * 52)
        c = input("Pilihan: ").strip()
        if c == '1':
            manual_project_new()
        elif c == '2':
            manual_project_select()
        elif c == '3':
            break


def manual_project_new():
    """Wizard buat project manual baru."""
    clear_screen()
    print("--- Project Baru ---\n")

    title = input("Judul novel (asli): ").strip()
    if not title:
        print("[-] Judul wajib diisi.")
        input("Press Enter...")
        return

    print("Bahasa sumber: 1.Chinese  2.Japanese  3.Korean  4.Lain")
    sc = input("Pilihan [1]: ").strip()
    source_lang = {"2": "Japanese", "3": "Korean"}.get(sc, "Chinese")
    if sc == "4":
        source_lang = input("Bahasa sumber: ").strip() or "Chinese"

    print("Bahasa tujuan: 1.Indonesian  2.English  3.Lain")
    tc = input("Pilihan [1]: ").strip()
    target_lang = {"2": "English"}.get(tc, "Indonesian")
    if tc == "3":
        target_lang = input("Bahasa tujuan: ").strip() or "Indonesian"

    synopsis = input("Sinopsis singkat (Enter untuk skip): ").strip()
    source_url = input("URL sumber novel (Enter untuk skip): ").strip()
    total_chapters_str = input("Jumlah total chapter (Enter untuk skip): ").strip()
    total_chapters = int(total_chapters_str) if total_chapters_str.isdigit() and int(total_chapters_str) > 0 else 0

    # Gemini suggest nama folder English
    print("\n[*] Gemini membaca judul & sinopsis untuk menyarankan nama folder...\n")
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
        print("Pilih nama folder (Gemini merekomendasikan):\n")
        for i, s in enumerate(suggestions, 1):
            print(f"  {i}. {s}")
        print(f"  {len(suggestions)+1}. Ketik sendiri")
        print()
        pick = input(f"Pilihan [1]: ").strip()
        if pick.isdigit() and 1 <= int(pick) <= len(suggestions):
            eng_name = suggestions[int(pick)-1]
        elif pick == str(len(suggestions)+1) or not pick.isdigit():
            eng_name = input("Nama folder: ").strip()
        else:
            eng_name = suggestions[0]
    else:
        print("Nama folder project (huruf Latin/Inggris, tanpa spasi).")
        eng_name = input("Nama folder: ").strip()

    if not eng_name:
        eng_name = _re.sub(r'[^\w]', '_', title[:20]).strip('_') or "novel"
    eng_name = _re.sub(r'[^\w\-]', '_', eng_name).strip('_')

    print("\n[*] Membuat folder project...")
    project_id, path = pm.create_manual_project(
        title, source_lang, target_lang,
        synopsis=synopsis, english_name=eng_name, source_url=source_url
    )

    # Jika ada sinopsis, Gemini bisa analisis dulu untuk reference awal
    if synopsis:
        print("[*] Gemini menganalisis sinopsis untuk reference awal...")
        ctx = f"Novel title: {title}\nSynopsis: {synopsis}\n"
        entities = tr.analyze_chapter_with_context(synopsis, ctx)
        ref = pm.load_manual_reference(project_id)
        ref = tr.merge_reference(ref, entities)
        ref = tr.dedup_reference(ref)
        pm.save_manual_reference(project_id, ref)
        chars = len(ref.get("characters", {}))
        locs  = len(ref.get("locations", {}))
        terms = len(ref.get("terms", {}))
        print(f"     Reference awal: {chars} tokoh, {locs} lokasi, {terms} istilah")

    raw_path = pm.get_raw_chapters_path(project_id)
    print(f"\n[OK] Project dibuat!")

    if total_chapters > 0:
        created, _ = pm.scaffold_raw_chapters(project_id, total_chapters)
        pm.update_manual_metadata(project_id, {"total_chapters": total_chapters})
        print(f"[OK] {created} file chapter kosong dibuat (chapter_001 … chapter_{str(total_chapters).zfill(max(3,len(str(total_chapters))))}.txt)")

    # Terjemahkan title + synopsis ke target_lang dan simpan di metadata
    if title or synopsis:
        _translate_metadata(project_id)

    if total_chapters == 0:
        print(f"\n  Copy file chapter (.txt) ke folder:")
        print(f"  {raw_path}")
        print(f"\n  Setiap file = 1 chapter. Nama bebas, misal:")
        print(f"    chapter_001.txt, ch01.txt, bab_1.txt, dst.")
    else:
        print(f"\n  File chapter kosong sudah siap di:")
        print(f"  {raw_path}")
        print(f"  Isi konten chapter ke masing-masing file.")
    input("\nPress Enter untuk masuk ke menu project...")
    manual_project_menu(project_id)


def manual_project_select():
    """Pilih project yang sudah ada."""
    while True:
        clear_screen()
        print("--- Project yang Ada ---\n")
        projects = pm.list_manual_projects()
        if not projects:
            print("Belum ada project manual.")
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

        print(f"\n{len(projects)+1}. Kembali")
        c = input("\nPilih project: ").strip()
        if not c.isdigit():
            continue
        idx = int(c) - 1
        if idx == len(projects):
            break
        if 0 <= idx < len(projects):
            manual_project_menu(projects[idx])


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
            print(f"\n  Belum ada file chapter di raw/.")
            print(f"  Copy file .txt ke:")
            print(f"  {raw_path}\n")
        else:
            print()
            print("  [✓] sudah diterjemahkan  [x] file kosong  [ ] belum diterjemahkan")
            print()
            for i, fname in enumerate(chapters, 1):
                if pm.is_chapter_translated(project_id, fname):
                    mark = "[✓]"
                elif pm.is_raw_chapter_empty(project_id, fname):
                    mark = "[x]"
                else:
                    mark = "[ ]"
                print(f"  {i:3}. {mark} {fname}")
            print()

        guide_exists  = bool(pm.load_translation_guide(project_id).get("guide_text"))
        guide_mark    = "[✓]" if guide_exists else "[ ]"
        has_trans_meta = bool(meta.get("title_translated") or meta.get("synopsis_translated"))
        trans_mark    = "[✓]" if has_trans_meta else "[ ]"
        total_ch = meta.get("total_chapters", 0)
        total_mark = f" ({total_ch} ch)" if total_ch else ""
        print(f"[R] Refresh  [V] Reference  [S] Riset {guide_mark}  [T] Terjemah Meta {trans_mark}")
        print(f"[U] Update Jumlah Chapter{total_mark}  [G] Judul Alt  [I] Image Prompt  [B] Kembali")
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
            prompt_cur = f" (sekarang {cur})" if cur else ""
            new_total_str = input(f"Jumlah total chapter{prompt_cur}: ").strip()
            if new_total_str.isdigit() and int(new_total_str) > 0:
                new_total = int(new_total_str)
                created, deleted = pm.scaffold_raw_chapters(project_id, new_total)
                pm.update_manual_metadata(project_id, {"total_chapters": new_total})
                msg = f"[OK] Total: {new_total} chapter."
                if created:
                    msg += f" +{created} file baru dibuat."
                if deleted:
                    msg += f" -{deleted} file kosong dihapus."
                print(msg)
            else:
                print("[-] Input tidak valid.")
            input("Press Enter...")
        elif cmd == 'g':
            generate_alt_titles(project_id)
        elif cmd == 'i':
            generate_image_prompt(project_id)
        elif cmd.isdigit() and chapters and 1 <= int(cmd) <= len(chapters):
            manual_translate_chapter(project_id, chapters[int(cmd)-1])


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
    print("  RISET PROJECT")
    print("=" * 56)
    print(f"  Novel : {title}")
    print(f"  Bahasa: {src_lang} → {tgt_lang}")
    print(f"  Chapter tersedia: {len(chapters)}")
    print()

    if not chapters and not synopsis:
        print("[-] Tidak ada chapter raw dan sinopsis kosong.")
        print("    Copy chapter ke raw/ atau isi sinopsis dulu.")
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
        print(f"[1/3] Memilih chapter untuk riset ({n_all} berisi konten dari {len(chapters)} total)...")
        print(f"      Dipilih {len(selected)}: {', '.join(selected)}")
    elif chapters:
        selected = []
        print("[1/3] Semua chapter masih kosong — riset dari sinopsis saja.")
    else:
        selected = []
        print("[1/3] Tidak ada chapter — riset dari sinopsis saja.")

    # ── TAHAP 2: Baca chapter terpilih + analisis komprehensif ───────────────
    print("\n[2/3] Memuat chapter dan mengirim ke Gemini untuk analisis mendalam...")
    print("      Harap tunggu — ini mungkin 1-2 menit.\n")

    content_parts = []
    if synopsis:
        content_parts.append(f"[SINOPSIS]\n{synopsis}")

    MAX_PER_CHAPTER = 4000
    for fname in selected:
        text = pm.load_raw_chapter(project_id, fname)
        if text:
            content_parts.append(f"[{fname}]\n{text[:MAX_PER_CHAPTER]}")

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
        f"Write in {tgt_lang}. This guide will be injected into every translation prompt.\n"
        f"## GAYA BAHASA TARGET\n"
        f"(Formal/informal, santai/serius, gaya light novel/sastra — sesuai tone asli)\n\n"
        f"## KONVENSI PENAMAAN\n"
        f"(Cara render nama: pinyin penuh / disingkat / gabung dengan gelar, dll)\n\n"
        f"## FRASA KUNCI & PADANANNYA\n"
        f"(Ungkapan khas novel ini + terjemahan yang konsisten dan natural)\n\n"
        f"## INSTRUKSI KHUSUS UNTUK PENERJEMAH\n"
        f"(Hal yang HARUS dijaga: konsistensi istilah, idiom, nuansa humor, dll)\n"
        f"WAJIB SERTAKAN: apakah novel ini menggunakan istilah internet/modern (live stream, host, dll)? "
        f"Jika ya, tuliskan instruksi: 'Kata serapan Inggris yang sudah umum di Indonesia (host, live stream, "
        f"streaming, online, boss, level, dll) JANGAN diterjemahkan ke padanan formal yang kaku.'\n\n"

        f"### SECTION 3: REFERENCE JSON ###\n"
        f"Output ONLY valid JSON:\n"
        f"```json\n"
        f'{{"characters":{{"OriginalName":"Romanized"}},'
        f'"locations":{{"OriginalName":"translated value"}},'
        f'"terms":{{"OriginalTerm":"Romanized (Meaning)"}},'
        f'"modern_terms":{{"OriginalTerm":"English loanword"}}}}\n'
        f"```\n"
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
        print("[-] Gemini tidak merespons. Cek koneksi atau coba lagi.")
        input("Press Enter...")
        return

    print("[3/3] Memproses dan menyimpan hasil...\n")

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
            new_entities = parsed
        except json.JSONDecodeError:
            pass

    # Riset ulang → REPLACE reference (Gemini sudah deduplicate)
    # Jika parse gagal, fallback ke merge agar tidak kehilangan data lama
    if new_entities:
        pm.save_manual_reference(project_id, new_entities)
        ref = new_entities
        print("     [✓] Reference diperbarui (deduplicated oleh Gemini)")
    else:
        ref = pm.load_manual_reference(project_id)
        print("     [!] Parse JSON gagal — reference lama dipertahankan")

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
    print("  HASIL RISET PROJECT")
    print("=" * 56)
    print(report_text[:2000])
    if len(report_text) > 2000:
        print(f"\n... (buka file untuk laporan lengkap)")

    if guide_text:
        print(f"\n{'─'*56}")
        print("  PANDUAN TERJEMAHAN (akan dipakai di semua translate):")
        print("─" * 56)
        print(guide_text[:800])
        if len(guide_text) > 800:
            print("  ...")

    print(f"\n{'='*56}")
    print(f"  Reference : {chars} tokoh | {locs} lokasi | {terms} istilah")
    print(f"  Guide     : translation_guide.json tersimpan")
    print(f"  Laporan   : {report_file}")
    print(f"{'='*56}")
    input("\nPress Enter untuk kembali...")


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
        print("[-] Tidak ada JSON dalam output Gemini.")
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
            print(f"     Judul   : {updates.get('title_translated', '-')}")
            syn_prev = updates.get("synopsis_translated", "")
            print(f"     Sinopsis: {syn_prev[:120]}{'...' if len(syn_prev) > 120 else ''}")
            print("[OK] Metadata terjemahan disimpan.")
        else:
            print("[-] Tidak ada terjemahan yang ditemukan dalam output.")
    except json.JSONDecodeError:
        print("[-] Gagal parse JSON dari Gemini.")
    input("Press Enter...")


def _show_reference(ref):
    clear_screen()
    print("--- Reference ---\n")
    for section, label in (
        ("characters", "TOKOH"),
        ("locations", "LOKASI"),
        ("terms", "ISTILAH"),
        ("modern_terms", "MODERN TERMS (tetap bahasa Inggris)"),
    ):
        items = ref.get(section, {})
        if not items:
            continue
        print(f"[{label}] ({len(items)} entri)")
        for k, v in items.items():
            print(f"  {k} → {v}")
        print()
    input("Press Enter...")


def manual_translate_chapter(project_id, filename):
    """Proses translate satu chapter: Gemini analisis → translate per chunk."""
    clear_screen()
    meta     = pm.load_manual_metadata(project_id)
    target   = meta.get("target_lang", "Indonesian")

    print(f"--- Translate: {filename} ---\n")

    raw_text = pm.load_raw_chapter(project_id, filename)
    if not raw_text:
        print("[-] File tidak ditemukan.")
        input("Press Enter...")
        return

    print(f"  Teks: {len(raw_text)} karakter")
    print(f"  Target: {target}\n")

    # Pilih engine
    print("Engine terjemahan:")
    print("  1. Gemini + Ollama fallback  (Gemini analisis, Ollama terjemah — hemat token)")
    print("  2. Ollama saja               (lokal, offline, bebas limit)")
    print("  3. Gemini saja               (Gemini untuk semua — boros token, risiko rate limit)")
    eng_c = input("Pilihan [1]: ").strip()
    if eng_c == "2":
        engine_mode = "ollama"
    elif eng_c == "3":
        engine_mode = "gemini_only"
    else:
        engine_mode = "gemini_fallback"
    print()

    # Muat translation guide jika ada
    guide = pm.load_translation_guide(project_id)
    guide_text = guide.get("guide_text", "")
    if guide_text:
        print(f"  [*] Translation guide ditemukan — akan digunakan.\n")

    # Step 1: Gemini analisis chapter baru → update reference
    if engine_mode == "ollama":
        print("[1/3] Analisis entitas dilewati (mode Ollama-only)...")
        ref = pm.load_manual_reference(project_id)
        print(f"     Pakai ref yang ada: {len(ref.get('characters',{}))} tokoh, "
              f"{len(ref.get('locations',{}))} lokasi, {len(ref.get('terms',{}))} istilah\n")
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
        print(f"     +{new_chars} tokoh, +{new_locs} lokasi, +{new_terms} istilah, +{new_mterms} modern terms")
        print(f"     Total ref: {len(ref.get('characters',{}))} tokoh, "
              f"{len(ref.get('locations',{}))} lokasi, {len(ref.get('terms',{}))} istilah, "
              f"{len(ref.get('modern_terms',{}))} modern terms\n")

    # Step 2: Translate per chunk
    models = tr.get_available_models()
    chunks_est = max(1, len(raw_text) // 2000)
    engine_label = {"gemini_fallback": "Gemini + Ollama fallback",
                    "gemini_only": "Gemini saja",
                    "ollama": "Ollama lokal"}.get(engine_mode, engine_mode)
    print(f"[2/3] Menerjemahkan... (~{chunks_est} chunk) | Engine: {engine_label}\n")

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
        )
    elif engine_mode == "gemini_only":
        translated, stats = tr.translate_with_gemini_primary(
            raw_text, ref, target,
            ollama_models=[],          # kosong = tidak ada fallback
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
        )
    else:
        translated, stats = tr.translate_with_gemini_primary(
            raw_text, ref, target,
            ollama_models=models,
            chunk_size=2000,
            progress_cb=_progress,
            guide_text=guide_text,
        )
    print()  # newline setelah progress bar

    if not translated:
        print("\n[-] Terjemahan gagal total. Cek scraper_logs/")
        input("Press Enter...")
        return

    g = stats.get("gemini", 0)
    o = stats.get("ollama", 0)
    f = stats.get("failed", 0)
    print(f"     Gemini: {g} chunk | Ollama: {o} chunk | Gagal: {f} chunk")

    # Step 3: Simpan
    print(f"\n[3/3] Menyimpan...")
    save_path = pm.save_manual_chapter_translated(project_id, filename, translated)
    print(f"     Disimpan: {save_path}")

    # Preview
    print("\n" + "=" * 56)
    print(f"  PREVIEW — {filename}")
    print("=" * 56)
    lines = translated.splitlines()
    print("\n".join(lines[:15]))
    if len(lines) > 15:
        print(f"\n... ({len(lines)} baris — buka file untuk lengkapnya)")

    print(f"\n[L] Lihat Log  [Enter] Kembali")
    if input("Choice: ").strip().lower() == 'l':
        clear_screen()
        print(tail_log(40))
        input("\nPress Enter...")


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
    print("  GENERATE JUDUL ALTERNATIF")
    print("=" * 56)
    print(f"  Novel : {title}")
    print(f"  Target: {tgt_lang}\n")
    print("[*] Meminta Gemini membuat judul alternatif...\n")

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
        print("[-] Gemini tidak merespons.")
        input("Press Enter...")
        return

    clear_screen()
    print("=" * 56)
    print("  JUDUL ALTERNATIF")
    print("=" * 56)
    print(result)

    # Simpan
    raw_dir    = pm.get_raw_chapters_path(project_id)
    report_dir = os.path.join(os.path.dirname(raw_dir), "research")
    os.makedirs(report_dir, exist_ok=True)
    out_file = os.path.join(report_dir, "alternative_titles.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"JUDUL ALTERNATIF — {title}\n{'='*56}\n\n{result}")
    print(f"\n[*] Disimpan: {out_file}")
    input("\nPress Enter...")


def generate_image_prompt(project_id):
    """Gemini generate prompt untuk membuat cover image (Midjourney/DALL-E/Stable Diffusion)."""
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
    print("  4. Umum (semua platform)")
    plat_c = input("Pilihan [1]: ").strip()
    platform = {"2": "DALL-E", "3": "Stable Diffusion", "4": "General"}.get(plat_c, "Midjourney")

    print(f"\n[*] Meminta Gemini membuat image prompt untuk {platform}...\n")

    chars_detail = "\n".join(f"  {k}: {v}" for k, v in list(ref.get("characters", {}).items())[:5])
    locs_detail  = ", ".join(list(ref.get("locations", {}).values())[:4])
    guide_tone   = guide.get("guide_text", "")[:300]

    prompt = (
        f"You are an expert AI image prompt engineer for novel cover art.\n\n"
        f"Novel: {title} ({src_lang} web novel)\n"
        f"Synopsis: {synopsis or '(tidak tersedia)'}\n"
        f"Main characters:\n{chars_detail or '  (tidak tersedia)'}\n"
        f"Key locations: {locs_detail or '(tidak tersedia)'}\n"
        f"Story tone: {guide_tone or '(tidak tersedia)'}\n\n"
        f"Generate cover art prompts optimized for {platform}.\n\n"
        f"Provide:\n"
        f"1. **MAIN PROMPT** — Full detailed prompt (English) for a stunning novel cover:\n"
        f"   - Main character visual description (appearance, clothing, pose)\n"
        f"   - Background/setting atmosphere\n"
        f"   - Art style (anime/manhwa/realistic/painterly — match the novel genre)\n"
        f"   - Lighting, color palette, mood\n"
        f"   - Quality/technical tags appropriate for {platform}\n\n"
        f"2. **NEGATIVE PROMPT** (things to avoid, especially for {platform})\n\n"
        f"3. **ALTERNATIVE CONCEPT** — A second composition idea (different pose/scene)\n\n"
        f"4. **STYLE TAGS** — 5-8 concise style keywords for quick use\n\n"
        f"Write prompts in English (standard for image AI). Explain choices in Indonesian."
    )

    result = tr._run_gemini(prompt, timeout=120)
    if not result:
        print("[-] Gemini tidak merespons.")
        input("Press Enter...")
        return

    clear_screen()
    print("=" * 56)
    print(f"  IMAGE PROMPT — {platform}")
    print("=" * 56)
    print(result)

    # Simpan
    raw_dir    = pm.get_raw_chapters_path(project_id)
    report_dir = os.path.join(os.path.dirname(raw_dir), "research")
    os.makedirs(report_dir, exist_ok=True)
    out_file = os.path.join(report_dir, f"image_prompt_{platform.lower().replace(' ','_')}.txt")
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(f"IMAGE PROMPT — {title} | Platform: {platform}\n{'='*56}\n\n{result}")
    print(f"\n[*] Disimpan: {out_file}")
    input("\nPress Enter...")


def manage_projects():
    clear_screen()
    print("--- Active Projects ---")
    projects = pm.list_projects()
    if not projects:
        print("Belum ada project.")
    else:
        for i, p in enumerate(projects):
            meta = pm.load_metadata(p)
            title = meta.get("title", p)
            ch_count = meta.get("chapter_count", "?")
            print(f"{i+1}. {title} ({ch_count} chapter) [{p}]")
    input("\nPress Enter to return...")

if __name__ == "__main__":
    main_menu()
