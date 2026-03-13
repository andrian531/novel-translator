import requests
from bs4 import BeautifulSoup
import subprocess
import json
import re
from engines.logger import logger


class BaseScraper:
    def __init__(self, base_url=""):
        self.base_url = base_url
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def get_supported_rankings(self):
        return {}

    def get_ranking_list(self, rank_id, page=1):
        return []

    # ------------------------------------------------------------------
    # translate_results: Gemini batch (1 call untuk semua novel di list)
    # ------------------------------------------------------------------

    def translate_results(self, novels, target_lang="Indonesian"):
        """
        Terjemahkan judul + sinopsis semua novel dalam satu batch Gemini.
        Lebih cepat dan lebih natural daripada Ollama satu-satu.
        """
        if not novels:
            return novels

        logger.info(f"[List-Translate] Batch {len(novels)} novel ke '{target_lang}' via Gemini")
        print(f"  [*] Menerjemahkan {len(novels)} novel ke {target_lang}...", end="\r")

        # Bangun batch input sebagai JSON
        batch = [
            {"i": i, "title": n["title"], "synopsis": n.get("synopsis", "")}
            for i, n in enumerate(novels)
        ]
        batch_json = json.dumps(batch, ensure_ascii=False)

        prompt = (
            f"Translate the following Chinese web novel titles and synopses into {target_lang}.\n\n"
            "Rules:\n"
            "- Character names: use Pinyin (e.g. 夏青 → Xia Qing), do NOT translate names as common words.\n"
            "- Genre tags like [快穿] = [Quick Transmigration], [重生] = [Reborn], [穿越] = [Transmigration].\n"
            "- Translate naturally and fluently, not word-by-word.\n"
            "- Keep the 'i' field exactly as-is (it is an index, do not change).\n"
            "- Return ONLY a valid JSON array — no markdown, no explanation.\n\n"
            f"Input:\n{batch_json}\n\n"
            f"Output format: same JSON array with translated 'title' and 'synopsis' fields."
        )

        result = self._run_gemini(prompt, timeout=120)

        if result:
            translated_list = self._parse_json_array(result)
            if translated_list and len(translated_list) == len(novels):
                for item in translated_list:
                    idx = item.get("i")
                    if idx is not None and 0 <= idx < len(novels):
                        if item.get("title"):
                            novels[idx]["title"] = item["title"]
                        if item.get("synopsis"):
                            novels[idx]["synopsis"] = item["synopsis"]
                logger.info(f"[List-Translate] Gemini batch selesai: {len(novels)} novel")
                print(f"  [OK] Terjemahan selesai ({len(novels)} novel)          ")
                return novels
            else:
                logger.warning(
                    f"[List-Translate] Parse JSON gagal atau jumlah tidak cocok "
                    f"(dapat {len(translated_list) if translated_list else 0}, harap {len(novels)}). "
                    "Menampilkan asli."
                )
        else:
            logger.warning("[List-Translate] Gemini tidak mengembalikan output. Menampilkan asli.")

        print(f"  [!] Terjemahan gagal — menampilkan judul asli.          ")
        return novels

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run_gemini(self, prompt, timeout=60):
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
            logger.warning(f"[Gemini] returncode={result.returncode} stderr={result.stderr[:300]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"[Gemini] Timeout setelah {timeout}s")
        except Exception as e:
            logger.error(f"[Gemini] Exception: {e}")
        return None

    def _parse_json_array(self, text):
        """Ekstrak JSON array dari output Gemini (kadang dibungkus ```json ```)."""
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.warning(f"[Gemini] JSON parse error: {e} | raw: {text[:300]}")
            return None

    def get_novel_details(self, novel_url):
        return {}

    def fetch_chapter(self, chapter_url):
        return ""
