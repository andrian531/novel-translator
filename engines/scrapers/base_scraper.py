import requests
from bs4 import BeautifulSoup
import subprocess
import os
import json

class BaseScraper:
    def __init__(self, base_url):
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

    def translate_results(self, novels, target_lang="English"):
        """Translates titles and synopses using Gemini CLI."""
        if not novels:
            return novels

        # Prepare payload for AI to minimize calls
        payload = []
        for i, n in enumerate(novels):
            payload.append({
                "index": i,
                "title": n['title'],
                "synopsis": n['synopsis']
            })

        prompt = f"""Translate the following list of Chinese novel metadata into {target_lang}.
Maintain the same JSON structure. Output ONLY the JSON array.
If the title is a proper name, provide a transliteration and a descriptive title in parentheses.
Translate the synopsis accurately while maintaining its tone.

JSON to translate:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""
        
        temp_input = "temp_translate_in.txt"
        try:
            with open(temp_input, "w", encoding="utf-8") as f:
                f.write(prompt)
            
            # Use gemini CLI
            cmd = f'type "{temp_input}" | gemini'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode == 0:
                # Clean up output to extract JSON
                output = result.stdout.strip()
                if "```json" in output:
                    output = output.split("```json")[1].split("```")[0].strip()
                elif "```" in output:
                    output = output.split("```")[1].split("```")[0].strip()
                
                translated_data = json.loads(output)
                for item in translated_data:
                    idx = item.get("index")
                    if idx is not None and idx < len(novels):
                        novels[idx]['title'] = item.get("title", novels[idx]['title'])
                        novels[idx]['synopsis'] = item.get("synopsis", novels[idx]['synopsis'])
            
        except Exception as e:
            print(f"[-] AI Translation Error: {e}")
        finally:
            if os.path.exists(temp_input):
                os.remove(temp_input)
        
        return novels

    def get_novel_details(self, novel_url):
        return {}

    def fetch_chapter(self, chapter_url):
        return ""
