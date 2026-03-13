import os
import sys
from engines.scraper_manager import ScraperManager

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
        print("3. Manage Existing Projects")
        print("4. Exit")
        print("----------------------------------------")
        
        choice = input("Select an option: ").strip()
        
        if choice == '1':
            browse_sites(manager)
        elif choice == '2':
            init_project_from_url(manager)
        elif choice == '3':
            manage_projects()
        elif choice == '4':
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
            show_rank_results(scraper, rank_id, rank_label)

def show_rank_results(scraper, rank_id, rank_label):
    page = 1
    while True:
        clear_screen()
        print(f"--- {rank_label} (Page {page}) ---")
        print("Fetching results...")
        
        novels = scraper.get_ranking_list(rank_id, page)
        
        clear_screen()
        print(f"--- {rank_label} (Page {page}) ---")
        if not novels:
            print("[-] No results found or site blocked access (403).")
            print("[TIP] Check scraper_debug.log or try a different mirror/site.")
            input("\nPress Enter to go back...")
            break

        for i, n in enumerate(novels):
            print(f"{i+1}. {n['title']} | Author: {n['author']}")
            # Truncate synopsis for clean display
            syn = n['synopsis'][:150] + "..." if len(n['synopsis']) > 150 else n['synopsis']
            print(f"   > {syn}")
            print("-" * 40)

        print(f"\n[N] Next Page | [P] Previous Page | [T] Translate List | [1-{len(novels)}] Select Novel | [B] Back")
        cmd = input("Choice: ").strip().lower()
        
        if cmd == 'n': page += 1
        elif cmd == 'p': page = max(1, page - 1)
        elif cmd == 'b': break
        elif cmd == 't':
            target = input("Choose language (ID: Indonesian, EN: English) [EN]: ").strip().lower()
            lang = "Indonesian" if target == 'id' else "English"
            print(f"[*] Translating list to {lang} using AI. Please wait...")
            novels = scraper.translate_results(novels, target_lang=lang)
        elif cmd.isdigit() and 1 <= int(cmd) <= len(novels):
            selected = novels[int(cmd)-1]
            init_project_menu(selected)
            break

def init_project_menu(novel_data):
    clear_screen()
    print("--- Initialize Novel Project ---")
    print(f"Title: {novel_data['title']}")
    print(f"Author: {novel_data['author']}")
    print(f"URL: {novel_data['url']}")
    print("-" * 40)
    
    confirm = input("Initialize this novel? (y/n): ").strip().lower()
    if confirm == 'y':
        print(f"\n[*] Creating project for {novel_data['title']}...")
        # TODO: Implement project creation logic (folder structure, etc.)
        input("\n[Feature Pending] Project structure created. Press Enter...")

def init_project_from_url(manager):
    url = input("\nEnter novel URL: ").strip()
    if not url: return
    
    scraper = manager.get_scraper(url)
    if not scraper:
        print("[-] Unsupported URL or site.")
        input("Press Enter...")
        return
    
    print("[*] Fetching novel data...")
    # This would usually call scraper.get_novel_details(url)
    input("\n[Feature Pending] Novel structure creation. Press Enter...")

def manage_projects():
    projects_dir = "projects"
    if not os.path.exists(projects_dir):
        os.makedirs(projects_dir)
    
    projects = [d for d in os.listdir(projects_dir) if os.path.isdir(os.path.join(projects_dir, d))]
    
    clear_screen()
    print("--- Active Projects ---")
    if not projects:
        print("No projects found.")
    else:
        for i, p in enumerate(projects):
            print(f"{i+1}. {p}")
    
    input("\nPress Enter to return...")

if __name__ == "__main__":
    main_menu()
