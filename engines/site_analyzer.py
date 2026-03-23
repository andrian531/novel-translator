"""
site_analyzer.py — Analyze new novel sites using Playwright + Gemini.
Generates JSON config compatible with GenericScraper.
"""
import json
import os
import re
import subprocess
from collections import Counter
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from engines.logger import logger


# ------------------------------------------------------------------
# Playwright fetch (headless browser)
# ------------------------------------------------------------------

def _fetch_with_playwright(url, wait_seconds=3, cookies=None):
    """Open URL with headless Chrome, return (html, final_url)."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [!] Playwright not installed. Run: playwright install chromium")
        return None, url

    print(f"  [browser] Opening {url} ...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            if cookies:
                context.add_cookies(cookies)
            page = context.new_page()
            try:
                response = page.goto(url, timeout=30000, wait_until="domcontentloaded")
                status = response.status if response else 0
                final_url = page.url
                if wait_seconds > 0:
                    page.wait_for_timeout(wait_seconds * 1000)
                logger.info(f"[site_analyzer] {url} -> status {status}, final: {final_url}")
                if status != 200:
                    print(f"  [!] HTTP status {status}")
                    return None, final_url
                return page.content(), final_url
            except Exception as e:
                logger.error(f"[site_analyzer] Playwright goto error: {e}")
                return None, url
            finally:
                browser.close()
    except Exception as e:
        logger.error(f"[site_analyzer] Playwright launch error: {e}")
        return None, url


def _attempt_login(login_url, username, password):
    """
    Attempt login via Playwright. Returns (cookies, success).
    Looks for input[type=password] on the login page, fills username + password, submits.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [], False

    print(f"  [browser] Opening login page: {login_url} ...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()
            try:
                page.goto(login_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                url_before = page.url

                # Find password field
                pw_input = page.query_selector("input[type=password]")
                if not pw_input:
                    print("  [!] No password field found on login page.")
                    browser.close()
                    return [], False

                # Find username field: input[type=text/email] or input[name*=user/name/email/login/account]
                user_input = None
                for sel in [
                    "input[type=email]",
                    "input[type=text][name*=user]", "input[type=text][name*=name]",
                    "input[type=text][name*=email]", "input[type=text][name*=login]",
                    "input[type=text][name*=account]", "input[type=text]",
                ]:
                    user_input = page.query_selector(sel)
                    if user_input:
                        break

                if user_input:
                    user_input.fill(username)
                pw_input.fill(password)

                # Submit: find submit button near password field
                submit = page.query_selector("input[type=submit], button[type=submit], button:has-text('login'), button:has-text('Login'), button:has-text('登录'), button:has-text('ログイン')")
                if submit:
                    submit.click()
                else:
                    pw_input.press("Enter")

                page.wait_for_timeout(3000)
                url_after = page.url

                cookies = context.cookies()
                browser.close()

                if url_after != url_before:
                    print(f"  [OK] Login successful (redirected to {url_after})")
                    return cookies, True
                else:
                    print(f"  [!] Login failed — still on login page. Continuing without login.")
                    return [], False
            except Exception as e:
                logger.error(f"[site_analyzer] Login error: {e}")
                browser.close()
                return [], False
    except Exception as e:
        logger.error(f"[site_analyzer] Login launch error: {e}")
        return [], False


def _save_credentials(domain, username, password, login_url):
    """Save credentials to config/credentials.json (gitignored)."""
    import json
    cred_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "credentials.json")
    try:
        creds = json.load(open(cred_path, encoding="utf-8")) if os.path.exists(cred_path) else {}
    except Exception:
        creds = {}
    creds[domain] = {"username": username, "password": password, "login_url": login_url}
    with open(cred_path, "w", encoding="utf-8") as f:
        json.dump(creds, f, ensure_ascii=False, indent=2)


def _load_credentials(domain):
    """Load credentials for a domain from config/credentials.json."""
    import json
    cred_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "credentials.json")
    if not os.path.exists(cred_path):
        return None
    try:
        creds = json.load(open(cred_path, encoding="utf-8"))
        return creds.get(domain)
    except Exception:
        return None


# ------------------------------------------------------------------
# Structure extraction
# ------------------------------------------------------------------

def _extract_structure(html, url):
    """
    Extract a compact page structure summary from HTML.
    Returns a dict summary (not full HTML — too large for Gemini).
    """
    soup = BeautifulSoup(html, "html.parser")
    parsed = urlparse(url)
    base_domain = parsed.netloc

    # Encoding from meta tag
    encoding = "utf-8"
    meta_charset = soup.find("meta", charset=True)
    if meta_charset:
        encoding = meta_charset.get("charset", "utf-8").lower()
    else:
        meta_ct = soup.find("meta", {"http-equiv": re.compile("content-type", re.I)})
        if meta_ct and meta_ct.get("content"):
            m = re.search(r"charset=([^\s;]+)", meta_ct["content"], re.I)
            if m:
                encoding = m.group(1).lower()

    # Page title
    page_title = soup.title.get_text(strip=True) if soup.title else ""

    # Heading elements (h1, h2, h3) — candidate title selectors
    headings = []
    for tag in soup.find_all(["h1", "h2", "h3"])[:10]:
        classes = " ".join(tag.get("class", []))
        id_ = tag.get("id", "")
        text = tag.get_text(strip=True)[:60]
        if text:
            headings.append({
                "tag": tag.name,
                "class": classes,
                "id": id_,
                "text": text,
                "selector": f"{tag.name}{'.' + classes.replace(' ', '.') if classes else ''}{'#' + id_ if id_ else ''}"
            })

    # Elements with long text (> 80 chars) — candidate synopsis/content
    long_text_elements = []
    for tag in soup.find_all(["div", "p", "section"])[:200]:
        text = tag.get_text(strip=True)
        if 80 < len(text) < 800:
            classes = " ".join(tag.get("class", []))
            id_ = tag.get("id", "")
            sel = f"{tag.name}{'.' + classes.split()[0] if classes else ''}{'#' + id_ if id_ else ''}"
            long_text_elements.append({
                "selector": sel,
                "length": len(text),
                "preview": text[:80]
            })
    seen = set()
    deduped = []
    for el in long_text_elements:
        if el["selector"] not in seen:
            seen.add(el["selector"])
            deduped.append(el)
    long_text_elements = deduped[:15]

    # All links — find path patterns
    all_links = []
    for a in soup.find_all("a", href=True)[:500]:
        href = a["href"]
        if href.startswith("javascript") or href == "#":
            continue
        full = urljoin(url, href)
        link_parsed = urlparse(full)
        if link_parsed.netloc == base_domain or link_parsed.netloc == "":
            all_links.append(link_parsed.path)

    path_prefixes = []
    for link in all_links:
        parts = [p for p in link.split("/") if p]
        if parts:
            path_prefixes.append("/" + parts[0] + "/")
    path_counter = Counter(path_prefixes)
    top_path_patterns = [{"pattern": p, "count": c} for p, c in path_counter.most_common(10)]

    sample_links = list(dict.fromkeys(all_links))[:20]

    # Links to other domains (potential mirrors)
    external_links = set()
    for a in soup.find_all("a", href=True)[:300]:
        href = a["href"]
        if href.startswith("http"):
            ext_parsed = urlparse(href)
            if ext_parsed.netloc and ext_parsed.netloc != base_domain:
                external_links.add(ext_parsed.netloc)
    external_links = list(external_links)[:10]

    # List item elements (novel listing candidates)
    # Include raw HTML of first item so Gemini can see exact span/class structure
    list_candidates = []
    for container in soup.find_all(["ul", "ol", "div"])[:100]:
        items = container.find_all("li", recursive=False) or container.find_all("div", class_=True, recursive=False)
        if len(items) >= 5:
            classes = " ".join(container.get("class", []))
            id_ = container.get("id", "")
            first_item = items[0]
            first_item_links = first_item.find_all("a")[:2] if first_item else []
            item_example = first_item.get_text(strip=True)[:80] if first_item else ""
            # Include raw HTML of first item (trimmed) so Gemini sees span classes
            item_html = str(first_item)[:500] if first_item else ""
            sel = f"{container.name}{'.' + classes.split()[0] if classes else ''}{'#' + id_ if id_ else ''}"
            list_candidates.append({
                "container_selector": sel,
                "item_count": len(items),
                "item_example": item_example,
                "item_html_sample": item_html,
                "item_links": [a.get("href", "") for a in first_item_links]
            })
    list_candidates = list_candidates[:8]

    return {
        "url": url,
        "page_title": page_title,
        "encoding": encoding,
        "headings": headings,
        "long_text_elements": long_text_elements,
        "top_path_patterns": top_path_patterns,
        "sample_links": sample_links,
        "external_domains": external_links,
        "list_candidates": list_candidates,
    }


def _detect_search_url(soup, base_domain, fetch_fn):
    """
    Detect how the site handles search:
    1. Find search form → extract action + input name
    2. Submit a test query (keyword: "斗破苍穹" or "dragon") via Playwright
    3. Return the resulting URL as the search_url pattern
    Returns a dict: {"search_url": "...", "method": "get/post", "param": "q", "result_url": "..."}
    """
    result = {"search_url": "", "method": "get", "param": "", "result_url": ""}

    # Find search form
    form = None
    for f in soup.find_all("form"):
        inputs = f.find_all("input", {"type": ["text", "search", None]})
        if inputs:
            form = f
            break

    if not form:
        # Try common search input patterns without a form
        for inp in soup.find_all("input"):
            name = inp.get("name", "") or inp.get("id", "") or inp.get("placeholder", "")
            if any(k in name.lower() for k in ("search", "q", "key", "query", "keyword", "s")):
                form = inp.parent
                break

    if form:
        action = form.get("action", "")
        method = (form.get("method", "get") or "get").lower()
        full_action = action if action.startswith("http") else base_domain + action
        # Find text input name
        param = ""
        for inp in form.find_all("input"):
            t = (inp.get("type") or "text").lower()
            if t in ("text", "search", ""):
                param = inp.get("name", "") or inp.get("id", "")
                if param:
                    break
        result["method"] = method
        result["param"] = param
        if param and method == "get":
            result["search_url"] = full_action + ("?" if "?" not in full_action else "&") + param + "="
        else:
            result["search_url"] = full_action

    # Try actual search via Playwright to confirm URL pattern
    test_keyword = "dragon"
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="zh-CN",
            )
            page = context.new_page()
            try:
                page.goto(base_domain, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)

                # Try to find and fill search input
                search_selectors = [
                    "input[type='search']",
                    "input[name*='search']", "input[name*='key']", "input[name*='query']",
                    "input[id*='search']", "input[placeholder*='搜']", "input[placeholder*='Search']",
                    "input[type='text']",
                ]
                filled = False
                for sel in search_selectors:
                    try:
                        el = page.locator(sel).first
                        if el.is_visible(timeout=1000):
                            el.fill(test_keyword)
                            filled = True
                            break
                    except Exception:
                        continue

                if filled:
                    # Press Enter or click search button
                    try:
                        page.keyboard.press("Enter")
                    except Exception:
                        try:
                            page.locator("button[type='submit'], input[type='submit'], .search-btn, .btn-search").first.click()
                        except Exception:
                            pass
                    page.wait_for_timeout(2500)
                    result_url = page.url
                    result["result_url"] = result_url
                    # Extract search_url pattern from result URL
                    if test_keyword in result_url:
                        result["search_url"] = result_url.replace(test_keyword, "")
            except Exception as e:
                logger.warning(f"[search_detect] Playwright error: {e}")
            finally:
                browser.close()
    except Exception as e:
        logger.warning(f"[search_detect] Could not run Playwright search test: {e}")

    return result


def _detect_chapter_sample(soup, url):
    """Find candidate chapter links from a novel detail page."""
    parsed = urlparse(url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"
    candidates = []

    chapter_patterns = [
        "#chapterlist", "#list", ".listmain", ".chapter-list",
        "ul.list-chapter", "dl dd", "#catalog"
    ]
    for sel in chapter_patterns:
        links = soup.select(f"{sel} a")[:3]
        if links:
            for a in links:
                href = a.get("href", "")
                if href and href != "#":
                    full = href if href.startswith("http") else base_domain + href
                    candidates.append({"selector_context": sel, "url": full, "text": a.get_text(strip=True)[:30]})
            break

    return candidates[:3]


def _detect_listing_page(soup, url):
    """
    Find a listing/category page URL from a novel detail page.
    Looks at breadcrumbs and nav links for category/ranking pages.
    Returns a URL string or None.
    """
    parsed = urlparse(url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    # Breadcrumb patterns — second-to-last link is usually the category
    breadcrumb_selectors = [
        ".crumb a", ".breadcrumb a", ".bread a", ".nav-path a",
        ".location a", "#breadcrumb a", "nav.breadcrumb a",
        "[class*='bread'] a", "[class*='crumb'] a",
    ]
    for sel in breadcrumb_selectors:
        links = soup.select(sel)
        # Breadcrumb: skip first (home) and last (current page) → pick middle ones
        candidates = [a for a in links if a.get("href") and a["href"] not in ("#", "/", "")]
        if len(candidates) >= 1:
            # Prefer second-to-last (category level)
            target = candidates[-1] if len(candidates) == 1 else candidates[-2]
            href = target.get("href", "")
            if href:
                full = href if href.startswith("http") else base_domain + href.rstrip("/") + "/"
                if full != url:
                    return full

    # Nav menu — look for links that look like genre/category pages (short paths)
    nav_selectors = [".nav a", "#nav a", ".menu a", "header a", ".navbar a", "nav a"]
    for sel in nav_selectors:
        for a in soup.select(sel):
            href = a.get("href", "")
            if not href or href in ("#", "/"):
                continue
            full = href if href.startswith("http") else base_domain + href
            parsed_link = urlparse(full)
            # Category pages typically have 1-2 path segments, no numbers
            path_parts = [p for p in parsed_link.path.split("/") if p]
            if (parsed_link.netloc == parsed.netloc and
                    1 <= len(path_parts) <= 2 and
                    not any(c.isdigit() for c in path_parts[-1])):
                return full

    return None


# ------------------------------------------------------------------
# Gemini analysis
# ------------------------------------------------------------------

def _run_gemini(prompt, timeout=90):
    try:
        result = subprocess.run(
            "gemini",
            input=prompt,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.warning(f"[site_analyzer] Gemini returncode={result.returncode} stderr={result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.warning(f"[site_analyzer] Gemini timeout after {timeout}s")
    except Exception as e:
        logger.error(f"[site_analyzer] Gemini error: {e}")
    return None


def _parse_json_from_text(text):
    """Extract JSON object from Gemini output."""
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    clean = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("```").strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError as e:
        logger.warning(f"[site_analyzer] JSON parse error: {e}")
    return None


def _ask_gemini_analyze(structure: dict, source_lang: str, page_type: str,
                        existing_config: dict = None):
    """Send multi-page structure summary to Gemini, request JSON scraper config.
    structure is a dict with keys: homepage, category_listing_page, novel_detail_page, chapter_page.
    If existing_config is provided, Gemini uses it as a baseline and only updates changed fields."""
    structure_json = json.dumps(structure, ensure_ascii=False, indent=2)

    if existing_config:
        existing_json = json.dumps(existing_config, ensure_ascii=False, indent=2)
        existing_section = (
            f"\nEXISTING CONFIG (use as baseline — keep fields that are still valid, "
            f"update only what has changed based on the new page structure):\n{existing_json}\n"
        )
        task_note = (
            "This is a RE-RESEARCH of an existing site. "
            "Start from the existing config above and only update selectors, rankings, mirrors, or "
            "encoding if the new page structure shows they have changed. "
            "Keep 'name', 'display_name', 'source_language', and 'locale' from the existing config "
            "unless clearly wrong."
        )
    else:
        existing_section = ""
        task_note = (
            "This is a NEW site. Generate a complete scraper config from scratch."
        )

    prompt = f"""You are a web scraping expert. Analyze the structure of a web novel site and return a JSON scraper config.

{task_note}

Source language of novels: {source_lang}
Exploration method: {page_type} — multiple pages were visited: homepage → category listing → novel detail → chapter.
Each key in the structure data below corresponds to a different page type.
Use ALL page structures together to generate the most accurate selectors.
Pay special attention to "item_html_sample" in list_candidates — it contains raw HTML of a listing item
showing exact span/class names for listing_chapter_count, listing_status, listing_author, etc.
{existing_section}
Extracted structures (from all visited pages):
{structure_json}

IMPORTANT NOTES:
- The page analyzed is a novel detail page or homepage — listing selectors (listing_*) may not be visible in the structure.
  Use your knowledge of this site's HTML structure or make reasonable CSS guesses based on common patterns (e.g., span.s2-s6 for bq730-style sites).
- For novel_status: provide a selector that targets ONLY the status element (e.g., a <p> or <span> containing 完结/连载).
  Do NOT use broad containers like #info or .bookinfo alone — the scraper will scan all child elements.
- If unsure about a listing selector, use an empty array [] rather than guessing incorrectly.

Return ONLY valid JSON — no markdown, no explanation:
{{
    "name": "site_slug_lowercase_no_spaces",
    "display_name": "Human Readable Site Name",
    "source_language": "{source_lang}",
    "base_url": "https://domain.com",
    "mirrors": ["https://domain.com"],
    "encoding": "utf-8 or gbk or euc-kr etc",
    "needs_playwright": true,
    "chapter_needs_playwright": true,
    "locale": "zh-CN or ko-KR or ja-JP etc",
    "selectors": {{
        "novel_listing": ["css selector for list items on ranking/category pages"],
        "listing_title": ["css selector for title link within each list item"],
        "listing_synopsis": ["css selector for synopsis within each list item"],
        "listing_author": ["css selector for author within each list item"],
        "listing_href_from": "listing_title",
        "listing_chapter_count": ["css selector for chapter count within each list item, e.g. span.s4"],
        "listing_last_update": ["css selector for last update date within each list item, e.g. span.s6"],
        "listing_status": ["css selector for completion status within each list item, e.g. span.s5"],
        "novel_title": ["css selector for novel title on detail page"],
        "novel_author_selectors": ["css selectors for info block paragraphs on detail page, e.g. #info p"],
        "novel_author_keyword": "作者 or 저자 or 作者",
        "novel_synopsis": ["css selector for synopsis on detail page"],
        "novel_status": ["css selector targeting ONLY the status paragraph/element on detail page (must contain 完结 or 连载 text — do NOT use a broad container)"],
        "chapter_list": ["css selectors for chapter links"],
        "chapter_content": ["css selectors for chapter text content"],
        "chapter_content_remove": ["script", "style", ".ad"]
    }},
    "rankings": {{
        "Category Name": {{
            "url": "/path/to/ranking/",
            "url_paged": "/path/to/ranking/{{page}}.html"
        }}
    }},
    "search_url": "https://domain.com/search?q="
}}"""

    return _run_gemini(prompt, timeout=90)


# ------------------------------------------------------------------
# Existing config detection
# ------------------------------------------------------------------

def _find_existing_config(manager, domain: str):
    """
    Check if a site with this domain is already registered in the manager.
    Returns (site_name, config_dict) or (None, None).
    """
    if not manager:
        return None, None
    domain_clean = domain.replace("www.", "")
    for name, cfg in manager._site_configs.items():
        for mirror in cfg.get("mirrors", [cfg.get("base_url", "")]):
            m_domain = urlparse(mirror).netloc.replace("www.", "")
            if m_domain == domain_clean:
                return name, cfg
    return None, None


def _merge_configs(existing: dict, new: dict) -> dict:
    """
    Merge new Gemini config over existing config.
    - Stable identity fields (name, display_name, source_language, locale) kept from existing
      unless new config has clearly different/non-default values.
    - Selectors, rankings, mirrors, encoding, search_url taken from new.
    - Extra fields in existing that new doesn't have are preserved.
    """
    merged = existing.copy()

    # Always update these from Gemini's fresh analysis
    for key in ("selectors", "rankings", "search_url", "encoding",
                 "needs_playwright", "chapter_needs_playwright"):
        if key in new:
            merged[key] = new[key]

    # Update mirrors: union of both, existing first
    existing_mirrors = set(existing.get("mirrors", []))
    new_mirrors = new.get("mirrors", [])
    for m in new_mirrors:
        if m not in existing_mirrors:
            merged.setdefault("mirrors", []).append(m)

    # Only update identity fields if new value is non-trivial
    for key in ("display_name", "base_url", "locale"):
        if new.get(key) and new[key] not in ("site_slug_lowercase_no_spaces", "https://domain.com"):
            merged[key] = new[key]

    return merged


# ------------------------------------------------------------------
# Main flow
# ------------------------------------------------------------------

def _find_novel_link(soup, base_domain):
    """Find a novel detail page link from a listing/category page."""
    # Look for links with path depth >= 2 (e.g. /book/12345/ or /novel/slug/)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = href if href.startswith("http") else base_domain + href
        parsed = urlparse(full)
        if parsed.netloc and parsed.netloc not in base_domain:
            continue
        parts = [p for p in parsed.path.split("/") if p]
        # Novel pages usually have 1-2 path segments, last segment contains digits or is alphanumeric
        if 1 <= len(parts) <= 2 and any(c.isdigit() for c in parts[-1]):
            return full
    return None


def _find_listing_candidates(soup, base_domain):
    """
    Scan ALL links on the page, find URLs that look like listing/category pages.
    Strategy: short paths (1 segment), no digits, appear multiple times → likely categories.
    Returns up to 5 candidates sorted by frequency (most linked = most likely category).
    """
    from collections import Counter
    path_counter = Counter()
    path_to_url = {}

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href or href.startswith("javascript") or href == "#":
            continue
        full = href if href.startswith("http") else base_domain + href
        parsed = urlparse(full)
        # Same domain only
        if parsed.netloc and parsed.netloc not in base_domain.split("//")[-1]:
            continue
        parts = [p for p in parsed.path.split("/") if p]
        # Category: 1 path segment, no pure numbers, not too long
        if (len(parts) == 1
                and not parts[0].isdigit()
                and len(parts[0]) <= 20
                and "." not in parts[0]):
            path_counter[parsed.path] += 1
            path_to_url[parsed.path] = full

    # Sort by frequency descending — most linked paths are likely category pages
    sorted_paths = [p for p, _ in path_counter.most_common(10)]
    return [path_to_url[p] for p in sorted_paths][:5]


def analyze_website(manager=None):
    """
    Interactive: start from homepage, auto-explore listing → novel detail → chapter.
    Builds comprehensive structure data for Gemini to generate accurate config.
    If site already exists, re-research using existing config as baseline.
    """
    print("\n" + "=" * 50)
    print("  ADD WEBSITE — Analyze Novel Site")
    print("=" * 50)
    print("  Enter the site HOMEPAGE URL.")
    print("  The analyzer will auto-explore menus, listing, novel detail, and chapter.")
    print("  Example: https://www.bq730.cc/")
    print()

    url = input("  Homepage URL: ").strip()
    if not url:
        print("  [!] No URL entered. Cancelled.")
        return

    if not url.startswith("http"):
        url = "https://" + url

    # Normalize to homepage
    parsed_input = urlparse(url)
    homepage_url = f"{parsed_input.scheme}://{parsed_input.netloc}/"
    input_domain = parsed_input.netloc

    # --- Check if site already exists ---
    existing_name, existing_config = _find_existing_config(manager, input_domain)

    is_update = False
    if existing_config:
        print(f"\n  [!] Site already registered: '{existing_name}'")
        print(f"      Display name : {existing_config.get('display_name', '-')}")
        print(f"      Base URL     : {existing_config.get('base_url', '-')}")
        sel_count = len(existing_config.get("selectors", {}))
        rank_count = len(existing_config.get("rankings", {}))
        print(f"      Selectors    : {sel_count} fields | Rankings: {rank_count}")
        print()
        print("  Options:")
        print("  1. Re-research and update (uses existing config as baseline)")
        print("  2. Cancel")
        choice = input("  > ").strip()
        if choice != "1":
            print("  [!] Cancelled.")
            input("\n  Press Enter to return...")
            return
        is_update = True
        source_lang = existing_config.get("source_language", "Chinese")
        print(f"  [*] Source language: {source_lang} (from existing config)")
    else:
        source_lang = input("  Source language of novels on this site (Chinese/Korean/Japanese/etc.): ").strip()
        if not source_lang:
            source_lang = "Chinese"

    base_domain = f"{parsed_input.scheme}://{parsed_input.netloc}"
    all_structures = {}

    # ── Login (optional) ──────────────────────────────────────────
    session_cookies = []
    saved_cred = _load_credentials(input_domain)
    if saved_cred:
        print(f"\n  [*] Saved credentials found for {input_domain} (user: {saved_cred['username']})")
        use_saved = input("  Use saved credentials? (Y/n): ").strip().lower()
        if use_saved != "n":
            cookies, ok = _attempt_login(saved_cred["login_url"], saved_cred["username"], saved_cred["password"])
            if ok:
                session_cookies = cookies
            # if failed, continue without — message already printed in _attempt_login
    else:
        login_url = input("\n  Login page URL (Enter to skip): ").strip()
        if login_url:
            if not login_url.startswith("http"):
                login_url = base_domain + login_url
            username = input("  Username / Email (Enter to skip): ").strip()
            if username:
                import getpass
                password = getpass.getpass("  Password: ")
                if password:
                    cookies, ok = _attempt_login(login_url, username, password)
                    if ok:
                        session_cookies = cookies
                        _save_credentials(input_domain, username, password, login_url)
                        print(f"  [OK] Credentials saved for future use.")

    # ── Step 1: Homepage ──────────────────────────────────────────
    print(f"\n  [1/4] Opening homepage...")
    html, final_url = _fetch_with_playwright(homepage_url, cookies=session_cookies)
    if not html:
        print("  [!] Failed to load homepage.")
        return
    soup = BeautifulSoup(html, "html.parser")
    home_structure = _extract_structure(html, final_url)
    all_structures["homepage"] = {
        "url": final_url,
        "headings": home_structure["headings"][:5],
        "list_candidates": home_structure["list_candidates"],
        "top_path_patterns": home_structure["top_path_patterns"],
        "sample_links": home_structure["sample_links"][:15],
        "external_domains": home_structure["external_domains"],
    }
    print(f"  [OK] Homepage — {len(home_structure['list_candidates'])} list area(s) found")

    # ── Step 1b: Search test ──────────────────────────────────────
    print(f"  [+] Testing search functionality...")
    search_info = _detect_search_url(soup, base_domain, _fetch_with_playwright)
    if search_info.get("result_url"):
        print(f"  [OK] Search URL pattern: {search_info.get('search_url', '-')}")
        print(f"       Result URL sample : {search_info.get('result_url', '-')}")
    elif search_info.get("search_url"):
        print(f"  [~] Search form found (not tested): {search_info['search_url']}")
    else:
        print(f"  [~] Search form not detected")
    all_structures["search_info"] = search_info

    # ── Step 2: Category/listing pages (user-provided) ───────────
    print(f"\n  [2/4] Listing/category pages")
    print(f"  Paste listing page URLs one by one (e.g. ranking, genre, category pages).")
    print(f"  Press Enter with no input when done.")
    listing_soup = None
    listing_idx = 0
    while True:
        listing_idx += 1
        raw_cat = input(f"  Listing URL #{listing_idx} (Enter to skip/done): ").strip()
        if not raw_cat:
            break
        cat_url = raw_cat if raw_cat.startswith("http") else base_domain + raw_cat
        print(f"  [+] Opening: {cat_url}")
        cat_html, cat_final = _fetch_with_playwright(cat_url, wait_seconds=2, cookies=session_cookies)
        if not cat_html:
            print(f"  [!] Failed to load. Try another URL.")
            listing_idx -= 1
            continue
        cat_soup_tmp = BeautifulSoup(cat_html, "html.parser")
        cat_structure = _extract_structure(cat_html, cat_final)
        key = "category_listing_page" if listing_idx == 1 else f"category_listing_page_{listing_idx}"
        all_structures[key] = {
            "url": cat_final,
            "list_candidates": cat_structure["list_candidates"],
            "headings": cat_structure["headings"][:3],
            "sample_links": cat_structure["sample_links"][:10],
        }
        item_counts = [c["item_count"] for c in cat_structure["list_candidates"]]
        print(f"  [OK] Listing page added — {len(cat_structure['list_candidates'])} list area(s), items: {item_counts}")
        if listing_soup is None:
            listing_soup = cat_soup_tmp
    if not listing_soup:
        print(f"  [~] No listing page provided — using homepage as fallback")

    # ── Step 3: Novel detail page (user-provided) ─────────────────
    print(f"\n  [3/4] Novel detail page")
    print(f"  Paste a URL of a specific novel's detail/info page.")
    manual = input("  Novel detail URL (Enter to skip): ").strip()
    novel_url = None
    if manual:
        novel_url = manual if manual.startswith("http") else base_domain + manual

    if novel_url:
        print(f"  [+] Opening novel: {novel_url}")
        nov_html, nov_final = _fetch_with_playwright(novel_url, wait_seconds=2, cookies=session_cookies)
        if nov_html:
            nov_soup = BeautifulSoup(nov_html, "html.parser")
            nov_structure = _extract_structure(nov_html, nov_final)
            all_structures["novel_detail_page"] = {
                "url": nov_final,
                "headings": nov_structure["headings"][:5],
                "long_text_elements": nov_structure["long_text_elements"],
                "list_candidates": nov_structure["list_candidates"],
            }
            print(f"  [OK] Novel detail page analyzed")

            # ── Step 4: Chapter page ──────────────────────────────
            print(f"\n  [4/4] Opening a chapter page...")
            ch_candidates = _detect_chapter_sample(nov_soup, nov_final)
            if not ch_candidates:
                print(f"  [~] Could not auto-detect a chapter link.")
                manual_ch = input("  Paste a chapter page URL manually (or Enter to skip): ").strip()
                if manual_ch:
                    ch_url = manual_ch if manual_ch.startswith("http") else base_domain + manual_ch
                    ch_candidates = [{"url": ch_url}]
            if ch_candidates:
                ch_url = ch_candidates[0]["url"]
                print(f"  [+] Opening chapter: {ch_url}")
                ch_html, ch_final = _fetch_with_playwright(ch_url, wait_seconds=2, cookies=session_cookies)
                if ch_html:
                    ch_structure = _extract_structure(ch_html, ch_final)
                    all_structures["chapter_page"] = {
                        "url": ch_final,
                        "headings": ch_structure["headings"][:3],
                        "long_text_elements": ch_structure["long_text_elements"][:6],
                    }
                    print(f"  [OK] Chapter page analyzed")

    # ── Gemini analysis ───────────────────────────────────────────
    print(f"\n  [Gemini] Sending all page structures for analysis...")
    if is_update:
        print(f"          Using existing config as baseline.")

    raw_result = _ask_gemini_analyze(
        all_structures, source_lang, "multi_page_exploration",
        existing_config=existing_config if is_update else None
    )
    if not raw_result:
        print("  [!] Gemini returned no result. Try again or edit config manually.")
        return

    new_config = _parse_json_from_text(raw_result)
    if not new_config:
        print("  [!] Gemini output is not valid JSON.")
        print("  --- Raw output ---")
        print(raw_result[:500])
        print("  ---")
        return

    # Ensure base_url is set correctly
    site_domain = base_domain
    if not new_config.get("base_url") or new_config["base_url"] == "https://domain.com":
        new_config["base_url"] = site_domain

    # Ensure original domain is in mirrors
    if "mirrors" not in new_config or not new_config["mirrors"]:
        new_config["mirrors"] = [site_domain]
    elif site_domain not in new_config["mirrors"]:
        new_config["mirrors"].insert(0, site_domain)

    # Merge with existing config if updating
    if is_update and existing_config:
        config = _merge_configs(existing_config, new_config)
        print("\n  -- Updated Config (merged with existing) --")
    else:
        config = new_config
        print("\n  -- Gemini Analysis Result --")

    print(json.dumps(config, ensure_ascii=False, indent=2))
    print()

    if is_update:
        confirm = input("  Save updated config? (y/n): ").strip().lower()
    else:
        confirm = input("  Save this config? (y/n): ").strip().lower()

    if confirm != "y":
        print("  [!] Cancelled. Config not saved.")
        input("\n  Press Enter to return...")
        return

    # Allow renaming (only for new sites)
    if not is_update:
        suggested_name = config.get("name", "")
        name_input = input(f"  Site name (Enter = '{suggested_name}'): ").strip()
        if name_input:
            config["name"] = name_input.lower().replace(" ", "_")
    else:
        config["name"] = existing_name  # preserve original name on update

    # Save
    if manager:
        saved_path = manager.save_site_config(config)
        if is_update:
            print(f"\n  [OK] Config updated: {saved_path}")
        else:
            print(f"\n  [OK] Config saved: {saved_path}")
        print(f"  Site '{config['name']}' is ready in Search Novel.")
    else:
        sites_dir = os.path.join(os.path.dirname(__file__), "..", "config", "sites")
        os.makedirs(sites_dir, exist_ok=True)
        out_path = os.path.join(sites_dir, f"{config['name']}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        print(f"\n  [OK] Config saved: {out_path}")
        print(f"  Restart the program for changes to take effect.")

    input("\n  Press Enter to return to menu...")
