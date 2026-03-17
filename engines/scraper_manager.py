import json
import os
import importlib
from urllib.parse import urlparse

class ScraperManager:
    def __init__(self):
        self.base_dir = os.path.join(os.path.dirname(__file__), "..")
        self.config_path = os.path.join(self.base_dir, "config", "site_map.json")
        self.site_map = self._load_site_map()
        self._site_configs = {}   # name -> config dict
        self._load_site_configs()

    def _load_site_map(self):
        if not os.path.exists(self.config_path):
            return {"sites": {}, "domains": {}, "site_configs": []}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_site_configs(self):
        """Load semua JSON config dari site_map["site_configs"]."""
        for rel_path in self.site_map.get("site_configs", []):
            full_path = os.path.normpath(os.path.join(self.base_dir, rel_path))
            if not os.path.exists(full_path):
                print(f"[!] Site config not found: {full_path}")
                continue
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self._site_configs[cfg["name"]] = cfg
            except Exception as e:
                print(f"[!] Failed to load site config {full_path}: {e}")

    def save_site_config(self, config: dict):
        """
        Simpan config situs baru ke config/sites/{name}.json dan
        update site_map.json.
        """
        sites_dir = os.path.join(self.base_dir, "config", "sites")
        os.makedirs(sites_dir, exist_ok=True)
        name = config["name"]
        filename = f"{name}.json"
        filepath = os.path.join(sites_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        # Update site_map.json
        rel = f"config/sites/{filename}"
        if rel not in self.site_map.get("site_configs", []):
            self.site_map.setdefault("site_configs", []).append(rel)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.site_map, f, ensure_ascii=False, indent=4)

        # Reload ke memory
        self._site_configs[name] = config
        return filepath

    def list_available_sites(self):
        """Return daftar nama situs yang tersedia."""
        return sorted(self._site_configs.keys())

    def get_scraper_by_name(self, site_name):
        """Return GenericScraper untuk nama situs."""
        cfg = self._site_configs.get(site_name)
        if cfg:
            from engines.scrapers.generic_scraper import GenericScraper
            return GenericScraper(cfg)
        return None

    def get_all_scrapers(self):
        """Return list (name, GenericScraper) untuk semua situs."""
        from engines.scrapers.generic_scraper import GenericScraper
        return [(name, GenericScraper(cfg)) for name, cfg in self._site_configs.items()]

    def get_scraper_by_domain(self, domain):
        """Return GenericScraper berdasarkan domain."""
        domain_clean = domain.replace("www.", "")
        for name, cfg in self._site_configs.items():
            for mirror in cfg.get("mirrors", [cfg.get("base_url", "")]):
                from urllib.parse import urlparse
                m_domain = urlparse(mirror).netloc.replace("www.", "")
                if m_domain == domain_clean:
                    from engines.scrapers.generic_scraper import GenericScraper
                    return GenericScraper(cfg)
        return None

    def get_scraper(self, url):
        """Auto-detect situs dari URL dan return scraper."""
        domain = urlparse(url).netloc.replace("www.", "")
        return self.get_scraper_by_domain(domain)

    def get_config_path(self, site_name):
        """Return path file JSON config untuk site_name, atau None jika tidak ditemukan."""
        site_map = self._load_site_map()
        for rel_path in site_map.get("site_configs", []):
            full_path = os.path.join(self.base_dir, rel_path)
            if os.path.exists(full_path):
                try:
                    with open(full_path, encoding="utf-8") as f:
                        cfg = json.load(f)
                    if cfg.get("name") == site_name:
                        return full_path
                except Exception:
                    continue
        return None
