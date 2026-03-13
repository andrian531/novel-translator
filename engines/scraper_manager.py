import json
import os
import importlib
from urllib.parse import urlparse

class ScraperManager:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "..", "config", "site_map.json")
        self.config = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            return {"sites": {}, "domains": {}}
        with open(self.config_path, "r") as f:
            return json.load(f)

    def list_available_sites(self):
        """Returns a list of friendly site identifiers."""
        return sorted(list(self.config.get("sites", {}).keys()))

    def get_scraper_by_name(self, site_name):
        """Returns a scraper instance for a friendly site name."""
        module_name = self.config.get("sites", {}).get(site_name)
        return self._load_scraper_module(module_name)

    def get_scraper_by_domain(self, domain):
        """Returns a scraper instance for a domain."""
        module_name = self.config.get("domains", {}).get(domain)
        return self._load_scraper_module(module_name)

    def _load_scraper_module(self, module_name):
        if not module_name:
            return None
        
        try:
            module = importlib.import_module(f"engines.scrapers.{module_name}")
            class_name = "".join([part.capitalize() for part in module_name.split("_")]) + "Scraper"
            scraper_class = getattr(module, class_name)
            return scraper_class()
        except Exception as e:
            print(f"[-] Error loading scraper module {module_name}: {e}")
            return None

    def get_scraper(self, url):
        """Detect site from URL and return the corresponding scraper instance."""
        domain = urlparse(url).netloc.replace("www.", "")
        return self.get_scraper_by_domain(domain)
