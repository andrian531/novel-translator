"""
GenericScraper — universal scraper yang membaca konfigurasi dari JSON.
Menggantikan site-specific scrapers (shuba_69.py, bq730.py).
"""
import re
import requests
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper
from engines.logger import logger


# ------------------------------------------------------------------
# Listing field extraction helpers (chapter count, last update, status)
# ------------------------------------------------------------------

def _extract_chapter_count(item, css_sel, fallback_text=""):
    """Try CSS selector first, then regex on item text."""
    if css_sel:
        el = item.select_one(css_sel) if isinstance(css_sel, str) else None
        if not el and isinstance(css_sel, list):
            for s in css_sel:
                el = item.select_one(s)
                if el:
                    break
        if el:
            m = re.search(r"(\d[\d,]+)", el.get_text())
            if m:
                return m.group(1).replace(",", "")
    # Regex fallback: "共1234章" / "1234章" / "1,234 chapters"
    m = re.search(r"共\s*(\d[\d,]*)\s*章|(\d[\d,]*)\s*章|(\d[\d,]*)\s*chapters?", fallback_text, re.I)
    if m:
        return (m.group(1) or m.group(2) or m.group(3) or "").replace(",", "")
    return ""


def _extract_last_update(item, css_sel, fallback_text=""):
    """Try CSS selector first, then regex for date patterns."""
    if css_sel:
        el = item.select_one(css_sel) if isinstance(css_sel, str) else None
        if not el and isinstance(css_sel, list):
            for s in css_sel:
                el = item.select_one(s)
                if el:
                    break
        if el:
            return el.get_text(strip=True)
    # Regex fallback: YYYY-MM-DD / MM-DD / YYYY/MM/DD
    m = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}", fallback_text)
    if m:
        return m.group(0)
    return ""


def _extract_status(item, css_sel, fallback_text=""):
    """Try CSS selector first, then keyword detection."""
    if css_sel:
        el = item.select_one(css_sel) if isinstance(css_sel, str) else None
        if not el and isinstance(css_sel, list):
            for s in css_sel:
                el = item.select_one(s)
                if el:
                    break
        if el:
            return el.get_text(strip=True)
    # Keyword fallback
    completed_kw = r"完结|完本|完稿|Completed|Tamat|END|end"
    ongoing_kw = r"连载|连载中|Ongoing|On-going|进行中|更新中"
    if re.search(completed_kw, fallback_text, re.I):
        return "Completed"
    if re.search(ongoing_kw, fallback_text, re.I):
        return "Ongoing"
    return ""


def _extract_status_from_page(soup, info_selectors):
    """Search info block for status keywords.
    Layer 1: configured selectors (most precise).
    Layer 2: fallback — scan common info containers for any element whose text
             contains a status label (状态/Status) paired with a value.
             This handles sites where exact selector is unknown/wrong but status
             is guaranteed to exist on the detail page.
    NEVER scans full page — sidebars contain '完结榜' which causes false positives.
    """
    completed_kw = r"完结|完本|完稿|Completed|Tamat|全本"
    ongoing_kw   = r"连载|连载中|Ongoing|进行中|更新中|Sedang|Berlangsung"
    status_label = r"状[态況]|Status"

    def _check(text):
        if re.search(completed_kw, text, re.I):
            return "Completed"
        if re.search(ongoing_kw, text, re.I):
            return "Ongoing"
        return ""

    # Layer 1: configured selectors
    for sel in (info_selectors or []):
        for tag in soup.select(sel):
            text = tag.get_text()
            if re.search(status_label, text, re.I) or re.search(completed_kw + "|" + ongoing_kw, text, re.I):
                result = _check(text)
                if result:
                    return result

    # Layer 2: try elements whose id/class name suggests "status"
    STATUS_ATTR_KW = re.compile(r"status|full|state|zuozhe|info|small", re.I)
    for tag in soup.find_all(True):
        tag_id    = tag.get("id", "")
        tag_class = " ".join(tag.get("class", []))
        if not re.search(STATUS_ATTR_KW, tag_id + " " + tag_class):
            continue
        text = tag.get_text(strip=True)
        if len(text) > 150:
            continue
        if re.search(status_label, text, re.I):
            result = _check(text)
            if result:
                return result

    # Layer 3: scan common info containers — find any small element with status label
    INFO_CONTAINERS = [
        "div.info", "div.small", "div.bookinfo", "#info", ".detail",
        "div.book-info", "div.meta", ".novel-info", ".book-detail",
        "div.bookdetail", "div.book_intro", ".intro-top",
    ]
    for container_sel in INFO_CONTAINERS:
        container = soup.select_one(container_sel)
        if not container:
            continue
        for tag in container.find_all(True):
            text = tag.get_text(strip=True)
            if len(text) > 100:
                continue
            if re.search(status_label, text, re.I):
                result = _check(text)
                if result:
                    return result

    # Layer 4: find any small element whose text IS the status value
    # e.g. <span>连载</span>, <span>完结</span>, <span>状态: 连载</span>
    # Skip elements inside nav/header/footer/sidebar/ranking areas
    SKIP_CONTAINERS = re.compile(
        r"nav|menu|header|footer|sidebar|rank|top|榜|recommend|hot|banner", re.I)
    completed_exact = re.compile(r"^(完结|完本|完稿|Completed|Tamat|全本)$", re.I)
    ongoing_exact   = re.compile(r"^(连载|连载中|Ongoing|进行中|更新中|Sedang|Berlangsung)$", re.I)
    labeled_pattern = re.compile(
        r"状[态況][：:]\s*(?P<val>\S+)|Status\s*[：:]\s*(?P<val2>\S+)", re.I)

    for tag in soup.find_all(["span", "em", "b", "strong", "p", "td", "li"]):
        in_bad_area = any(
            re.search(SKIP_CONTAINERS,
                      " ".join(p.get("class", [])) + " " + (p.get("id") or ""))
            for p in tag.parents if p.name
        )
        if in_bad_area:
            continue
        text = tag.get_text(strip=True)
        if not text or len(text) > 30:
            continue
        if completed_exact.match(text):
            return "Completed"
        if ongoing_exact.match(text):
            return "Ongoing"
        m = labeled_pattern.search(text)
        if m:
            val = m.group("val") or m.group("val2") or ""
            if re.search(completed_kw, val, re.I):
                return "Completed"
            if re.search(ongoing_kw, val, re.I):
                return "Ongoing"

    return ""


def _extract_last_update_from_page(soup, info_selectors):
    """Search info block paragraphs for a date pattern."""
    update_kw = r"更新|Updated?|Diperbarui|最[近新]"
    for sel in (info_selectors or []):
        for tag in soup.select(sel):
            text = tag.get_text()
            if re.search(update_kw, text, re.I):
                m = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?", text)
                if m:
                    return m.group(0)
    # Fallback: search full page
    page_text = soup.get_text(" ")
    m = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?", page_text)
    if m:
        return m.group(0)
    return ""


class GenericScraper(BaseScraper):
    """
    Scraper universal yang dikonfigurasi via dict (dari config/sites/*.json).
    Mendukung Playwright (untuk situs JS-heavy) dan requests (untuk situs statis).
    """

    def __init__(self, config: dict):
        super().__init__(config["base_url"])
        self.config = config
        self.site_name = config.get("name", "unknown")
        self.mirrors = config.get("mirrors", [config["base_url"]])
        self.needs_playwright = config.get("needs_playwright", False)
        self.chapter_needs_playwright = config.get("chapter_needs_playwright", self.needs_playwright)
        self.sel = config.get("selectors", {})
        self.encoding = config.get("encoding", "utf-8")
        self.locale = config.get("locale", "zh-CN")

    # ------------------------------------------------------------------
    # Internal: fetch HTML
    # ------------------------------------------------------------------

    def _fetch_html_requests(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=20)
            if r.status_code != 200:
                logger.warning(f"[{self.site_name}] HTTP {r.status_code} pada {url}")
                return None
            enc = self.encoding if self.encoding != "auto" else (r.apparent_encoding or "utf-8")
            r.encoding = enc
            return r.text
        except Exception as e:
            logger.error(f"[{self.site_name}] requests error pada {url}: {e}")
            return None

    def _fetch_html_playwright(self, url, wait_selector=None):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error(f"[{self.site_name}] Playwright tidak terinstal. Jalankan: playwright install chromium")
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent=self.headers["User-Agent"],
                    locale=self.locale,
                )
                page = context.new_page()
                try:
                    response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    status = response.status if response else 0
                    logger.info(f"[{self.site_name}] Playwright {url} — status {status}")
                    if status != 200:
                        logger.warning(f"[{self.site_name}] Non-200 status {status}")
                        return None
                    if wait_selector:
                        try:
                            page.wait_for_selector(wait_selector, timeout=5000)
                        except Exception:
                            pass
                    return page.content()
                except Exception as e:
                    logger.error(f"[{self.site_name}] Playwright goto error: {e}")
                    return None
                finally:
                    browser.close()
        except Exception as e:
            logger.error(f"[{self.site_name}] Playwright launch error: {e}")
            return None

    def _fetch_html(self, url, use_playwright=None, wait_selector=None):
        """Fetch HTML menggunakan Playwright atau requests sesuai config."""
        pw = self.needs_playwright if use_playwright is None else use_playwright
        if pw:
            return self._fetch_html_playwright(url, wait_selector)
        return self._fetch_html_requests(url)

    def _fetch_with_mirrors(self, path, use_playwright=None, wait_selector=None):
        """Coba fetch path di tiap mirror, kembalikan (html, base_url) pertama sukses."""
        for base in self.mirrors:
            url = f"{base.rstrip('/')}{path}"
            html = self._fetch_html(url, use_playwright=use_playwright, wait_selector=wait_selector)
            if html:
                return html, base
        return None, None

    # ------------------------------------------------------------------
    # Selector helpers
    # ------------------------------------------------------------------

    def _select_first(self, soup, selectors):
        """Coba tiap selector, kembalikan list element pertama yang menghasilkan hasil."""
        if isinstance(selectors, str):
            selectors = [selectors]
        for sel in selectors:
            result = soup.select(sel)
            if result:
                return result
        return []

    def _select_one_first(self, soup, selectors):
        """Coba tiap selector, kembalikan element pertama yang ditemukan."""
        if isinstance(selectors, str):
            selectors = [selectors]
        for sel in selectors:
            result = soup.select_one(sel)
            if result:
                return result
        return None

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def get_supported_rankings(self):
        return {name: cfg for name, cfg in self.config.get("rankings", {}).items()}

    def _get_ranking_url(self, rank_name, page=1):
        """Bangun URL ranking berdasarkan config."""
        rank_cfg = self.config.get("rankings", {}).get(rank_name)
        if not rank_cfg:
            return None
        if page == 1 or not rank_cfg.get("url_paged"):
            path = rank_cfg.get("url", "")
        else:
            path = rank_cfg["url_paged"].replace("{page}", str(page))
        return self.config["base_url"].rstrip("/") + path

    def get_ranking_list(self, rank_name, page=1):
        """
        Fetch halaman ranking, kembalikan list dict:
        [{"title", "author", "synopsis", "url", "id", "site"}]
        """
        url = self._get_ranking_url(rank_name, page)
        if not url:
            logger.warning(f"[{self.site_name}] Ranking '{rank_name}' tidak ditemukan di config")
            return []

        logger.info(f"[{self.site_name}] Fetching ranking '{rank_name}' page {page}: {url}")
        html = self._fetch_html(url)
        if not html:
            # Coba mirror lain
            path = url.replace(self.config["base_url"].rstrip("/"), "")
            html, _ = self._fetch_with_mirrors(path)
        if not html:
            logger.error(f"[{self.site_name}] Gagal fetch ranking '{rank_name}'")
            return []

        enc = self.encoding if self.encoding != "auto" else "utf-8"
        soup = BeautifulSoup(html, "html.parser", from_encoding=enc if enc != "utf-8" else None)

        listing_sel = self.sel.get("novel_listing", [])
        items = self._select_first(soup, listing_sel)
        if not items:
            logger.warning(f"[{self.site_name}] Tidak ada item ditemukan dengan selector: {listing_sel}")
            return []

        novels = []
        for item in items:
            title_el = self._select_one_first(item, self.sel.get("listing_title", ["a"]))
            if not title_el:
                continue
            href = title_el.get("href", "")
            if not href or href == "#":
                continue
            full_url = href if href.startswith("http") else self.config["base_url"].rstrip("/") + href

            author_el = self._select_one_first(item, self.sel.get("listing_author", []))
            syn_el = self._select_one_first(item, self.sel.get("listing_synopsis", []))

            # Optional: chapter count, last update, status via config selectors or regex fallback
            item_text = item.get_text(" ", strip=True)
            chapter_count = _extract_chapter_count(
                item, self.sel.get("listing_chapter_count"), item_text)
            last_update = _extract_last_update(
                item, self.sel.get("listing_last_update"), item_text)
            status = _extract_status(
                item, self.sel.get("listing_status"), item_text)

            novel_id = href.rstrip("/").split("/")[-1]
            novels.append({
                "id": novel_id,
                "title": title_el.get_text(strip=True),
                "author": author_el.get_text(strip=True) if author_el else "Unknown",
                "synopsis": syn_el.get_text(strip=True) if syn_el else "",
                "url": full_url,
                "site": self.site_name,
                "chapter_count": chapter_count,
                "last_update": last_update,
                "status_raw": status,
            })

        logger.info(f"[{self.site_name}] Parsed {len(novels)} novel dari ranking '{rank_name}'")
        return novels

    # ------------------------------------------------------------------
    # Novel details + chapter list
    # ------------------------------------------------------------------

    def get_novel_details(self, novel_url):
        """
        Fetch halaman novel, ekstrak metadata dan daftar chapter.
        Return: {"title", "author", "synopsis", "url", "chapter_count", "chapters": [{"title", "url"}]}
        """
        logger.info(f"[{self.site_name}] Fetching novel details: {novel_url}")

        # Coba fetch dengan mirror jika URL dari base_url
        html = self._fetch_html(novel_url)
        if not html:
            # Coba cari path dan retry via mirror
            from urllib.parse import urlparse
            parsed = urlparse(novel_url)
            path = parsed.path
            if parsed.query:
                path += "?" + parsed.query
            html, _ = self._fetch_with_mirrors(path)
        if not html:
            logger.error(f"[{self.site_name}] Gagal fetch novel details: {novel_url}")
            return {}

        enc = self.encoding if self.encoding != "auto" else "utf-8"
        soup = BeautifulSoup(html, "html.parser", from_encoding=enc if enc != "utf-8" else None)

        # Judul
        title_el = self._select_one_first(soup, self.sel.get("novel_title", ["h1"]))
        title = title_el.get_text(strip=True) if title_el else ""

        # Author — cari elemen yang mengandung keyword author
        author = ""
        author_keyword = self.sel.get("novel_author_keyword", "作者")
        for sel in self.sel.get("novel_author_selectors", []):
            for tag in soup.select(sel):
                if author_keyword in tag.get_text():
                    author = (tag.get_text()
                              .replace(author_keyword, "")
                              .replace("：", "")
                              .replace(":", "")
                              .strip())
                    break
            if author:
                break

        # Sinopsis
        syn_el = self._select_one_first(soup, self.sel.get("novel_synopsis", []))
        synopsis = syn_el.get_text(strip=True) if syn_el else ""

        # Status — via config selector or keyword search in info block
        status = ""
        # Use novel_status selectors first (targeted), fallback to novel_author_selectors
        # Always use _extract_status_from_page (keyword scan) — never _select_one_first,
        # because the first matching element may be author/category, not status.
        status_selectors = self.sel.get("novel_status") or self.sel.get("novel_author_selectors", [])
        status = _extract_status_from_page(soup, status_selectors)

        # Last update — via config selector or regex search
        last_update = ""
        update_sel = self.sel.get("novel_last_update")
        if update_sel:
            el = self._select_one_first(soup, update_sel)
            if el:
                last_update = el.get_text(strip=True)
        if not last_update:
            last_update = _extract_last_update_from_page(soup, self.sel.get("novel_author_selectors", []))

        # Chapter list
        chapter_tags = self._select_first(soup, self.sel.get("chapter_list", ["dl dd a"]))
        logger.info(f"[{self.site_name}] Ditemukan {len(chapter_tags)} chapter tag")

        base = "/".join(novel_url.split("/")[:3])
        chapters = []
        for tag in chapter_tags:
            href = tag.get("href", "")
            if not href or href == "#":
                continue
            full_url = href if href.startswith("http") else f"{base}{href}"
            chapters.append({
                "title": tag.get_text(strip=True),
                "url": full_url,
            })

        logger.info(f"[{self.site_name}] Total {len(chapters)} chapter untuk '{title}'")
        return {
            "title": title,
            "author": author,
            "synopsis": synopsis,
            "url": novel_url,
            "chapter_count": len(chapters),
            "status": status,
            "last_update": last_update,
            "chapters": chapters,
        }

    # ------------------------------------------------------------------
    # Fetch chapter content
    # ------------------------------------------------------------------

    def fetch_chapter(self, chapter_url):
        """
        Fetch konten satu chapter. Kembalikan teks mentah.
        """
        logger.info(f"[{self.site_name}] Fetching chapter: {chapter_url}")

        verify_keyword = self.sel.get("chapter_verify_redirect")
        html = self._fetch_html(chapter_url, use_playwright=self.chapter_needs_playwright)
        if not html:
            logger.error(f"[{self.site_name}] Gagal fetch chapter: {chapter_url}")
            return ""

        soup = BeautifulSoup(html, "html.parser")

        # Cek redirect ke verify page
        if verify_keyword:
            from playwright.sync_api import sync_playwright
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    context = browser.new_context(user_agent=self.headers["User-Agent"])
                    page = context.new_page()
                    try:
                        response = page.goto(chapter_url, timeout=30000, wait_until="domcontentloaded")
                        status = response.status if response else 0
                        final_url = page.url
                        if verify_keyword in final_url or status != 200:
                            logger.warning(f"[{self.site_name}] Redirect ke verify atau status {status}")
                            return ""
                        for sel in self.sel.get("chapter_content", []):
                            try:
                                page.wait_for_selector(sel, timeout=4000)
                                break
                            except Exception:
                                continue
                        html = page.content()
                        soup = BeautifulSoup(html, "html.parser")
                    finally:
                        browser.close()
            except Exception as e:
                logger.error(f"[{self.site_name}] fetch_chapter Playwright error: {e}")
                return ""

        content_tag = self._select_one_first(soup, self.sel.get("chapter_content", []))
        if not content_tag:
            logger.warning(f"[{self.site_name}] Selector konten tidak ditemukan di {chapter_url}")
            return ""

        for remove_sel in self.sel.get("chapter_content_remove", ["script", "style"]):
            for tag in content_tag.select(remove_sel):
                tag.decompose()

        text = content_tag.get_text(separator="\n").strip()
        logger.info(f"[{self.site_name}] Chapter fetched: {len(text)} karakter")
        return text

    def fetch_chapter_full(self, chapter_url):
        """
        Fetch chapter content + title dari URL.
        Kembalikan dict {"title": str, "content": str}.
        Title diambil dari: selector chapter_title (jika ada di config),
        lalu h1, lalu <title> tag halaman.
        """
        logger.info(f"[{self.site_name}] Fetching chapter full: {chapter_url}")
        html = self._fetch_html(chapter_url, use_playwright=self.chapter_needs_playwright)
        if not html:
            return {"title": "", "content": ""}

        soup = BeautifulSoup(html, "html.parser")

        # Ambil title — catat confidence level
        # "high"  : dari configured selector atau h1
        # "low"   : dari <title> tag halaman (sering berisi nama situs)
        title = ""
        title_confidence = "low"
        title_selectors = self.sel.get("chapter_title", [])
        if isinstance(title_selectors, str):
            title_selectors = [title_selectors]
        for sel in title_selectors:
            tag = soup.select_one(sel)
            if tag:
                title = tag.get_text(strip=True)
                title_confidence = "high"
                break
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)
                title_confidence = "high"
        if not title:
            pg_title = soup.find("title")
            if pg_title:
                raw_title = pg_title.get_text(strip=True)
                for sep in [" - ", " | ", " – ", "_", "—"]:
                    if sep in raw_title:
                        title = raw_title.split(sep)[0].strip()
                        break
                else:
                    title = raw_title
                title_confidence = "low"

        # Ambil content
        content_tag = self._select_one_first(soup, self.sel.get("chapter_content", []))
        if not content_tag:
            logger.warning(f"[{self.site_name}] Selector konten tidak ditemukan di {chapter_url}")
            return {"title": title, "title_confidence": title_confidence, "content": ""}

        for remove_sel in self.sel.get("chapter_content_remove", ["script", "style"]):
            for tag in content_tag.select(remove_sel):
                tag.decompose()

        content = content_tag.get_text(separator="\n").strip()

        # Confidence konten: rendah jika terlalu pendek atau baris pertama terlihat seperti watermark/iklan
        _WATERMARK_KW = re.compile(
            r"请收藏|收藏本站|手机版|www\.|http|全文阅读|章节目录|下一章|上一章", re.I
        )
        paragraphs = [p.strip() for p in content.splitlines() if p.strip()]
        first_para = paragraphs[0] if paragraphs else ""
        content_confidence = "high"
        if len(content) < 300:
            content_confidence = "low"
        elif first_para and _WATERMARK_KW.search(first_para):
            content_confidence = "low"

        logger.info(
            f"[{self.site_name}] Chapter full: title='{title[:50]}' "
            f"title_conf={title_confidence} content={len(content)}ch content_conf={content_confidence}"
        )
        return {
            "title": title,
            "title_confidence": title_confidence,
            "content": content,
            "content_confidence": content_confidence,
            "first_para": first_para,
        }
