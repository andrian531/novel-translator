import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

class Bq730Scraper(BaseScraper):
    def __init__(self, base_url="https://www.bq730.cc"):
        super().__init__(base_url)
        self.headers.update({
            "Referer": self.base_url
        })

    def get_supported_rankings(self):
        return {
            "Total Rankings": "top",
            "Completed Novels": "finish",
            "Fantasy (Xuanhuan)": "xuanhuan",
            "Xianxia": "xianxia",
            "Urban": "dushi",
            "Historical": "lishi",
            "Sci-Fi": "kehuan",
            "Game/Sports": "youxi"
        }

    def get_ranking_list(self, rank_id, page=1):
        # bq730 uses categories as rankings
        if rank_id == "top":
            url = f"{self.base_url}/top/"
        else:
            url = f"{self.base_url}/{rank_id}/{page}.html" if page > 1 else f"{self.base_url}/{rank_id}/"
            
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []

            # Use apparent_encoding or fallback to utf-8
            response.encoding = response.apparent_encoding or "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            
            # The /top/ page has a different structure
            if rank_id == "top":
                items = soup.select(".top-list .item") # Placeholder, usually top lists are different
                # For this specific site, let's focus on the category-style lists which have synopses
                return [] 

            items = soup.select(".item")
            novels = []
            for item in items:
                title_tag = item.select_one("dt a")
                author_tag = item.select_one("dt span")
                synopsis_tag = item.select_one("dd")
                
                if title_tag:
                    novels.append({
                        "id": title_tag['href'].strip("/"),
                        "title": title_tag.text.strip(),
                        "author": author_tag.text.strip() if author_tag else "Unknown",
                        "synopsis": synopsis_tag.text.strip() if synopsis_tag else "No description available.",
                        "url": title_tag['href'] if title_tag['href'].startswith("http") else f"{self.base_url}{title_tag['href']}"
                    })
            return novels
        except Exception as e:
            print(f"[-] bq730 Scrape Error: {e}")
            return []
