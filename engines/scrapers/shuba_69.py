from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from playwright.sync_api import sync_playwright
from engines.logger import logger


class Shuba69Scraper(BaseScraper):
    def __init__(self, base_url="https://www.69shuba.com"):
        super().__init__(base_url)
        self.mirrors = ["https://www.69shuba.com", "https://69shuba.cx"]

    # ------------------------------------------------------------------
    # Internal: Playwright fetch
    # ------------------------------------------------------------------

    def _fetch_html(self, url, wait_selector=None):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            page = context.new_page()
            try:
                response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                status = response.status if response else 0
                logger.info(f"[shuba69] Playwright fetched {url} - Status: {status}")
                if status == 200:
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=5000)
                        except Exception:
                            pass
                    return page.content()
                else:
                    logger.warning(f"[shuba69] Non-200 status {status} pada {url}")
            except Exception as e:
                logger.error(f"[shuba69] Playwright error pada {url}: {e}")
            finally:
                browser.close()
        return None

    def _try_mirrors(self, path, wait_selector=None):
        """Coba tiap mirror, kembalikan (html, base_url) pertama yang berhasil."""
        for base in self.mirrors:
            url = f"{base}{path}"
            html = self._fetch_html(url, wait_selector)
            if html:
                return html, base
        return None, None

    # ------------------------------------------------------------------
    # Ranking list
    # ------------------------------------------------------------------

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
        rank_path = f"/novels/{rank_id}_0_0_{page}.htm"
        html, base = self._try_mirrors(rank_path)
        if not html:
            logger.error(f"[shuba69] Semua mirror gagal untuk rank_id='{rank_id}' page={page}")
            return []

        soup = BeautifulSoup(html, "html.parser", from_encoding="gbk")
        items = soup.select("div.newbox ul li") or soup.select("div.newbook ul li")

        if not items:
            logger.warning(f"[shuba69] Tidak ada item ditemukan di {base} dengan selector newbox/newbook")
            return []

        novels = []
        for item in items:
            title_tag = item.select_one(".newnav h3 a") or item.select_one("h3 a")
            if title_tag:
                syn_tag = item.select_one(".newnav ol.ellipsis_2") or item.select_one("ol.ellipsis_2")
                author_tag = item.select_one(".labelbox label:nth-child(1)")
                href = title_tag["href"]
                novels.append({
                    "id": href.split("/")[-1].replace(".htm", ""),
                    "title": title_tag.text.strip(),
                    "author": author_tag.text.strip() if author_tag else "Unknown",
                    "synopsis": syn_tag.text.strip() if syn_tag else "No description available.",
                    "url": href if href.startswith("http") else f"{base}{href}"
                })

        logger.info(f"[shuba69] Parsed {len(novels)} novel dari {base}")
        return novels

    # ------------------------------------------------------------------
    # Novel details + chapter list
    # ------------------------------------------------------------------

    def get_novel_details(self, novel_url):
        """
        Fetch halaman novel, ekstrak:
        - title, author, synopsis
        - daftar chapter [{title, url}]
        - chapter_count
        """
        logger.info(f"[shuba69] Fetching novel details: {novel_url}")
        html = self._fetch_html(novel_url, wait_selector="ul#chapterlist, .listmain")
        if not html:
            logger.error(f"[shuba69] Gagal fetch novel page: {novel_url}")
            return {}

        soup = BeautifulSoup(html, "html.parser", from_encoding="gbk")

        # Judul
        title_tag = soup.select_one("h1") or soup.select_one(".bookname h1")
        title = title_tag.text.strip() if title_tag else ""

        # Author
        author = ""
        for tag in soup.select(".bookinfo p, .author"):
            if "作者" in tag.text or "author" in tag.text.lower():
                author = tag.text.replace("作者", "").replace("：", "").replace(":", "").strip()
                break

        # Chapter list — beberapa kemungkinan selector
        chapter_tags = (
            soup.select("ul#chapterlist li a") or
            soup.select(".listmain dl dd a") or
            soup.select("#list dl dd a") or
            soup.select(".chapter-list li a") or
            soup.select("ul.list-chapter li a")
        )

        logger.info(f"[shuba69] Ditemukan {len(chapter_tags)} chapter tag")

        # Tentukan base URL dari novel_url
        base = "/".join(novel_url.split("/")[:3])

        chapters = []
        for tag in chapter_tags:
            href = tag.get("href", "")
            if not href or href == "#":
                continue
            full_url = href if href.startswith("http") else f"{base}{href}"
            chapters.append({
                "title": tag.text.strip(),
                "url": full_url,
            })

        logger.info(f"[shuba69] Total {len(chapters)} chapter untuk '{title}'")
        return {
            "title": title,
            "author": author,
            "url": novel_url,
            "chapter_count": len(chapters),
            "chapters": chapters,
        }

    # ------------------------------------------------------------------
    # Fetch chapter content
    # ------------------------------------------------------------------

    def fetch_chapter(self, chapter_url):
        """
        Fetch konten satu chapter. Kembalikan teks mentah (China).
        """
        logger.info(f"[shuba69] Fetching chapter: {chapter_url}")
        html = self._fetch_html(chapter_url, wait_selector=".txtnav, #chaptercontent, .content")
        if not html:
            logger.error(f"[shuba69] Gagal fetch chapter: {chapter_url}")
            return ""

        soup = BeautifulSoup(html, "html.parser", from_encoding="gbk")

        # Coba beberapa selector umum untuk konten chapter
        content_tag = (
            soup.select_one(".txtnav") or
            soup.select_one("#chaptercontent") or
            soup.select_one(".content") or
            soup.select_one("#BookText") or
            soup.select_one(".chapter-content")
        )

        if not content_tag:
            logger.warning(f"[shuba69] Selector konten tidak ditemukan di {chapter_url}")
            return ""

        # Hapus tag script/style di dalam konten
        for tag in content_tag.select("script, style, .ad, .adsbygoogle"):
            tag.decompose()

        text = content_tag.get_text(separator="\n").strip()
        logger.info(f"[shuba69] Chapter fetched: {len(text)} karakter")
        return text
