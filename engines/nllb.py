"""
NLLB translation engine wrapper.
Translates source text via pivot language (e.g. CN → EN),
then AI model refines EN → target language with context.

Improvements v2:
- Name placeholder protection: canonical names replaced with tokens before NLLB
- Post-NLLB CJK scan: detect remaining Chinese chars, flag for Gemini
- Chunk size 800 for better context
"""

import os
import re

# NLLB language code map
LANG_CODES = {
    "chinese":             "zho_Hans",
    "chinese_traditional": "zho_Hant",
    "japanese":            "jpn_Jpan",
    "korean":              "kor_Hang",
    "english":             "eng_Latn",
    "indonesian":          "ind_Latn",
    "thai":                "tha_Thai",
    "vietnamese":          "vie_Latn",
}

# Best pivot language per source (what NLLB handles best)
PIVOT_LANG = {
    "chinese":    "english",
    "japanese":   "english",
    "korean":     "english",
    "thai":       "english",
    "vietnamese": "english",
    "english":    None,
}

_nllb_model     = None
_nllb_tokenizer = None
_nllb_model_name = None


def _get_model_name():
    """Return best available NLLB model from HF cache."""
    hf_hub = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    for name in ["nllb-200-3.3B", "nllb-200-distilled-1.3B", "nllb-200-distilled-600M"]:
        if os.path.isdir(os.path.join(hf_hub, f"models--facebook--{name}")):
            return f"facebook/{name}"
    return None


def _load_model():
    global _nllb_model, _nllb_tokenizer, _nllb_model_name
    if _nllb_model is not None:
        return True
    model_name = _get_model_name()
    if not model_name:
        return False
    try:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        import torch
        print(f"  [NLLB] Loading {model_name}...", flush=True)
        _nllb_tokenizer = AutoTokenizer.from_pretrained(model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device)
        _nllb_model_name = model_name
        print(f"  [NLLB] Loaded on {device.upper()}", flush=True)
        return True
    except Exception as e:
        print(f"  [NLLB] Load failed: {e}")
        return False


# ── Name placeholder helpers ──────────────────────────────────────────────────

def build_name_placeholders(profiles):
    """
    Build two dicts from character_profiles:
      name_to_token: {"Borg": "<<NAME_0>>", "Alina": "<<NAME_1>>", ...}
      token_to_name: reverse map
    Includes romanized_name + all romanized aliases.
    """
    name_to_token = {}
    token_to_name = {}
    idx = 0
    for p in profiles:
        rname = p.get("romanized_name", "").strip()
        if not rname:
            continue
        token = f"<<NAME_{idx}>>"
        name_to_token[rname] = token
        token_to_name[token] = rname
        idx += 1
        for alias in p.get("aliases", []):
            r = alias.get("romanized", "").strip() if isinstance(alias, dict) else str(alias).strip()
            if r and r not in name_to_token:
                token = f"<<NAME_{idx}>>"
                name_to_token[r] = token
                token_to_name[token] = r
                idx += 1
    return name_to_token, token_to_name


def inject_placeholders(text, name_to_token):
    """Replace canonical names in text with placeholder tokens."""
    # Sort by length desc to avoid partial replacements
    for name in sorted(name_to_token, key=len, reverse=True):
        token = name_to_token[name]
        text = re.sub(r'\b' + re.escape(name) + r'\b', token, text)
    return text


def restore_placeholders(text, token_to_name):
    """Restore placeholder tokens back to canonical names."""
    for token, name in token_to_name.items():
        text = text.replace(token, name)
    return text


# ── CJK detection ─────────────────────────────────────────────────────────────

def has_cjk(text):
    """Return True if text contains CJK characters."""
    return bool(re.search(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]', text))


def extract_cjk_snippets(text):
    """Return list of unique CJK words/phrases remaining in text."""
    return list(set(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]+', text)))


# ── Core translate ────────────────────────────────────────────────────────────

def translate_chunk(text, src_lang, tgt_lang):
    """Translate a single chunk using NLLB. Returns string or None."""
    if not _load_model():
        return None
    src_code = LANG_CODES.get(src_lang)
    tgt_code = LANG_CODES.get(tgt_lang)
    if not src_code or not tgt_code:
        return None
    try:
        import torch
        inputs = _nllb_tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=600,
        ).to(_nllb_model.device)
        forced_id = _nllb_tokenizer.lang_code_to_id[tgt_code]
        with torch.no_grad():
            output = _nllb_model.generate(
                **inputs,
                forced_bos_token_id=forced_id,
                max_new_tokens=600,
                num_beams=4,
                early_stopping=True,
            )
        return _nllb_tokenizer.decode(output[0], skip_special_tokens=True)
    except Exception as e:
        print(f"  [NLLB] Translate error: {e}")
        return None


def translate_text(text, src_lang, tgt_lang, chunk_size=800,
                   progress_cb=None, profiles=None):
    """
    Translate full text by splitting into chunks.
    - profiles: list of character profile dicts — used for name placeholder protection
    Returns (translated_text, stats_dict, cjk_remaining_list).
    """
    if not _load_model():
        return None, {"nllb": 0, "failed": 0}, []

    # Build name placeholders from profiles
    name_to_token, token_to_name = {}, {}
    if profiles:
        name_to_token, token_to_name = build_name_placeholders(profiles)

    # Inject placeholders into source text
    protected_text = inject_placeholders(text, name_to_token) if name_to_token else text

    # Split into paragraph-aware chunks of ~chunk_size chars
    paragraphs = protected_text.split("\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 1 > chunk_size and current:
            chunks.append(current.strip())
            current = para + "\n"
        else:
            current += para + "\n"
    if current.strip():
        chunks.append(current.strip())

    results = []
    ok, fail = 0, 0
    all_cjk = []

    for i, chunk in enumerate(chunks, 1):
        if progress_cb:
            progress_cb(i, len(chunks), "NLLB")
        result = translate_chunk(chunk, src_lang, tgt_lang)
        if result:
            # Restore name placeholders in NLLB output
            result = restore_placeholders(result, token_to_name)
            # Collect any remaining CJK (NLLB missed these)
            cjk = extract_cjk_snippets(result)
            if cjk:
                all_cjk.extend(cjk)
            results.append(result)
            ok += 1
        else:
            # On failure restore placeholders in original chunk too
            fallback = restore_placeholders(chunk, token_to_name)
            results.append(fallback)
            fail += 1

    translated = "\n\n".join(results)
    unique_cjk = list(set(all_cjk))
    return translated, {"nllb": ok, "failed": fail}, unique_cjk


# ── Utilities ─────────────────────────────────────────────────────────────────

def is_available():
    """Return True if NLLB packages and at least one model are available."""
    try:
        import transformers, torch, sentencepiece  # noqa
    except ImportError:
        return False
    return _get_model_name() is not None


def get_model_info():
    """Return model name string for display."""
    name = _get_model_name()
    return name.split("/")[-1] if name else "not installed"
