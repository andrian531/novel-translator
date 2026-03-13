import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from playwright.sync_api import sync_playwright
from engines.logger import logger


class Bq730Scraper(BaseScraper):
    def __init__(self, base_url="https://www.bq730.cc"):
        super().__init__(base_url)
        self.headers.update({
            "Referer": self.base_url
        })

    # ------------------------------------------------------------------
    # Ranking list
    # ------------------------------------------------------------------

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
        if rank_id == "top":
            url = f"{self.base_url}/top/"
        else:
            url = f"{self.base_url}/{rank_id}/{page}.html" if page > 1 else f"{self.base_url}/{rank_id}/"

        logger.info(f"[bq730] Fetching: {url}")
        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            logger.info(f"[bq730] Status: {response.status_code}")

            if response.status_code != 200:
                logger.warning(f"[bq730] Non-200 response: {response.status_code}")
                return []

            response.encoding = response.apparent_encoding or "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            if rank_id == "top":
                # Halaman /top/ punya beberapa seksi genre, tiap seksi 50 li
                # Format: <li><a href="/book/XXX/">Judul</a>/Author</li>
                novels = []
                rank_sections = soup.select(".rank > div")
                logger.info(f"[bq730] Top page: {len(rank_sections)} seksi ditemukan")
                for section in rank_sections:
                    section_title_tag = section.select_one(".title") or section.find(["h2", "h3", "h4"])
                    section_name = section_title_tag.text.strip() if section_title_tag else "Top"
                    lis = section.select("li")
                    for li in lis:
                        a = li.select_one("a")
                        if not a:
                            continue
                        href = a.get("href", "")
                        # Author ada setelah teks anchor, dipisah "/"
                        raw = li.get_text()
                        parts = raw.split("/", 1)
                        author = parts[1].strip() if len(parts) > 1 else "Unknown"
                        novels.append({
                            "id": href.strip("/"),
                            "title": a.text.strip(),
                            "author": author,
                            "synopsis": f"[{section_name}]",
                            "url": f"{self.base_url}{href}" if not href.startswith("http") else href,
                        })
                logger.info(f"[bq730] Total top: {len(novels)} novel")
                return novels

            items = soup.select(".item")
            logger.info(f"[bq730] Ditemukan {len(items)} item")

            novels = []
            for item in items:
                title_tag = item.select_one("dt a")
                author_tag = item.select_one("dt span")
                synopsis_tag = item.select_one("dd")

                if title_tag:
                    href = title_tag['href']
                    novels.append({
                        "id": href.strip("/"),
                        "title": title_tag.text.strip(),
                        "author": author_tag.text.strip() if author_tag else "Unknown",
                        "synopsis": synopsis_tag.text.strip() if synopsis_tag else "No description available.",
                        "url": href if href.startswith("http") else f"{self.base_url}{href}"
                    })

            logger.info(f"[bq730] Parsed {len(novels)} novel dari {url}")
            return novels
        except Exception as e:
            logger.error(f"[bq730] Scrape error: {e}")
            return []

    # ------------------------------------------------------------------
    # Novel details + chapter list
    # ------------------------------------------------------------------

    def get_novel_details(self, novel_url):
        """
        Fetch halaman novel bq730, ekstrak judul, author, daftar chapter.
        """
        logger.info(f"[bq730] Fetching novel details: {novel_url}")
        try:
            response = requests.get(novel_url, headers=self.headers, timeout=15)
            logger.info(f"[bq730] Novel page status: {response.status_code}")
            if response.status_code != 200:
                return {}

            response.encoding = response.apparent_encoding or "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")

            # Judul
            title_tag = soup.select_one("h1") or soup.select_one(".bookname")
            title = title_tag.text.strip() if title_tag else ""

            # Author
            author = ""
            for tag in soup.select(".bookinfo p, .author, .info p"):
                t = tag.text
                if "作者" in t or "Author" in t.lower():
                    author = t.replace("作者", "").replace("：", "").replace(":", "").strip()
                    break

            # Chapter list
            chapter_tags = (
                soup.select("#list dl dd a") or
                soup.select(".listmain dl dd a") or
                soup.select(".chapter-list li a") or
                soup.select("ul.list-chapter li a") or
                soup.select("dl dd a")
            )

            logger.info(f"[bq730] Ditemukan {len(chapter_tags)} chapter tag")

            chapters = []
            for tag in chapter_tags:
                href = tag.get("href", "")
                if not href or href == "#":
                    continue
                full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                chapters.append({
                    "title": tag.text.strip(),
                    "url": full_url,
                })

            logger.info(f"[bq730] Total {len(chapters)} chapter untuk '{title}'")
            return {
                "title": title,
                "author": author,
                "url": novel_url,
                "chapter_count": len(chapters),
                "chapters": chapters,
            }
        except Exception as e:
            logger.error(f"[bq730] get_novel_details error: {e}")
            return {}

    # ------------------------------------------------------------------
    # Fetch chapter content (Playwright — bypass verify redirect)
    # ------------------------------------------------------------------

    def fetch_chapter(self, chapter_url):
        """
        Fetch konten satu chapter bq730 menggunakan Playwright.
        requests tidak bisa karena site redirect ke /user/verify.html.
        """
        logger.info(f"[bq730] Fetching chapter (Playwright): {chapter_url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            try:
                response = page.goto(chapter_url, timeout=30000, wait_until="domcontentloaded")
                status = response.status if response else 0
                final_url = page.url
                logger.info(f"[bq730] Chapter status: {status} | final URL: {final_url}")

                if "verify" in final_url or status != 200:
                    logger.warning(f"[bq730] Diarahkan ke verify page atau status {status}. Site mungkin butuh login.")
                    return ""

                # Tunggu konten muncul
                for selector in ["#chaptercontent", ".content", "#BookText", ".chapter-content"]:
                    try:
                        page.wait_for_selector(selector, timeout=4000)
                        break
                    except Exception:
                        continue

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                content_tag = (
                    soup.select_one("#chaptercontent") or
                    soup.select_one(".content") or
                    soup.select_one("#BookText") or
                    soup.select_one(".chapter-content") or
                    soup.select_one("div.txtnav")
                )

                if not content_tag:
                    logger.warning(f"[bq730] Selector konten tidak ditemukan di {chapter_url}")
                    return ""

                for tag in content_tag.select("script, style, .ad, .adsbygoogle"):
                    tag.decompose()

                text = content_tag.get_text(separator="\n").strip()
                logger.info(f"[bq730] Chapter fetched: {len(text)} karakter")
                return text
            except Exception as e:
                logger.error(f"[bq730] fetch_chapter Playwright error: {e}")
                return ""
            finally:
                browser.close()
