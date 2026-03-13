import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
import os

class Shuba69Scraper(BaseScraper):
    def __init__(self, base_url="https://www.69shuba.com"):
        super().__init__(base_url)
        # Mirror list for fallback
        self.mirrors = ["https://www.69shuba.com", "https://69shuba.cx", "https://www.69shuba.pro", "https://www.69shuba.li"]
        self.session = requests.Session()
        # High-fidelity browser headers
        self.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def _warm_up(self, domain):
        """Hit the homepage once to get cookies."""
        try:
            self.session.get(domain, headers=self.headers, timeout=10)
        except:
            pass

    def get_supported_rankings(self):
        return {
            "Monthly Popular": "monthvisit",
            "Weekly Popular": "weekvisit",
            "All-time Popular": "allvisit",
            "Completed Novels": "full",
            "Recently Updated": "lastupdate",
            "New Novels": "postdate"
        }

    def get_ranking_list(self, rank_id, page=1):
        # Determine the ranking identifier
        rank_path = f"{rank_id}_0_0_{page}.htm"
        
        log_file = r"e:\ai-projects\novel-translator\scraper_debug.log"
        
        # Try mirrors until one works
        for base in self.mirrors:
            self._warm_up(base)
            url = f"{base}/novels/{rank_path}"
            
            try:
                # Add Referer for each mirror
                self.headers["Referer"] = base
                response = self.session.get(url, headers=self.headers, timeout=15, allow_redirects=True)
                
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[*] Trying mirror {base} - Status: {response.status_code}\n")
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, "html.parser", from_encoding='gbk')
                    # Updated selectors based on latest inspection
                    items = soup.select("div.newbox ul li") or soup.select("div.newbook ul li")
                    
                    if not items:
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(f"[!] No items found on {base}. Trying next...\n")
                        continue

                    novels = []
                    for item in items:
                        title_tag = item.select_one(".newnav h3 a") or item.select_one("h3 a")
                        if title_tag:
                            syn_tag = item.select_one(".newnav ol.ellipsis_2") or item.select_one("ol.ellipsis_2")
                            author_tag = item.select_one(".labelbox label:nth-child(1)")
                            
                            novels.append({
                                "id": title_tag['href'].split("/")[-1].replace(".htm", ""),
                                "title": title_tag.text.strip(),
                                "author": author_tag.text.strip() if author_tag else "Unknown",
                                "synopsis": syn_tag.text.strip() if syn_tag else "No description available.",
                                "url": title_tag['href'] if title_tag['href'].startswith("http") else f"{base}{title_tag['href']}"
                            })
                    return novels
            except Exception as e:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"[!] Mirror {base} failed: {str(e)}\n")
                continue
        
        return []
