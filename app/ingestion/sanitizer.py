"""
ROVON.UZ - Text Sanitization, Transliteration & Normalization
Handles Cyrillic <-> Latin transliteration, advertising removal, and content hashing.
"""

import hashlib
import re
from typing import Tuple


# Exact Uzbek Cyrillic to NEW Uzbek Latin mapping table (Ö, Ğ, Ş, Ç)
CYR_TO_LAT = {
    'А': 'A', 'а': 'a',
    'Б': 'B', 'б': 'b',
    'В': 'V', 'в': 'v',
    'Г': 'G', 'г': 'g',
    'Д': 'D', 'д': 'd',
    'Е': 'E', 'е': 'e',
    'Ё': 'Yo', 'ё': 'yo',
    'Ж': 'J', 'ж': 'j',
    'З': 'Z', 'з': 'z',
    'И': 'I', 'и': 'i',
    'Й': 'Y', 'й': 'y',
    'К': 'K', 'к': 'k',
    'Л': 'L', 'л': 'l',
    'М': 'M', 'м': 'm',
    'Н': 'N', 'н': 'n',
    'О': 'O', 'о': 'o',
    'П': 'P', 'п': 'p',
    'Р': 'R', 'р': 'r',
    'С': 'S', 'с': 's',
    'Т': 'T', 'т': 't',
    'У': 'U', 'у': 'u',
    'Ф': 'F', 'ф': 'f',
    'Х': 'X', 'х': 'x',
    'Ц': 'Ts', 'ц': 'ts',
    'Ч': 'Ç', 'ч': 'ç',  # Yangi alifbo: Ç ç
    'Ш': 'Ş', 'ш': 'ş',  # Yangi alifbo: Ş ş
    'Щ': 'Ş', 'щ': 'ş',  # Yangi alifbo: Ş ş
    'Ъ': "'", 'ъ': "'",
    'Ь': '', 'ь': '',
    'Ы': 'I', 'ы': 'i',
    'Э': 'E', 'э': 'e',
    'Ю': 'Yu', 'ю': 'yu',
    'Я': 'Ya', 'я': 'ya',
    'Ў': 'Ö', 'ў': 'ö',  # Yangi alifbo: Ö ö
    'Қ': 'Q', 'қ': 'q',
    'Ғ': 'Ğ', 'ғ': 'ğ',  # Yangi alifbo: Ğ ğ
    'Ҳ': 'H', 'ҳ': 'h',
}

# Regex patterns for ad clutter and social channel calls
AD_PATTERNS = [
    r"(?i)bizning\s+kanal(?:imiz)?ga\s+obuna\s+bo'?ling[:\s]*@\w+",
    r"(?i)telegram\s+kanalimiz(?:ga)?[:\s]*https?://t\.me/\S+",
    r"(?i)obuna\s+bo'?ling[:\s]*https?://\S+",
    r"(?i)batafsil\s+bu\s+yerda[:\s]*https?://\S+",
    r"(?i)reklama\s+va\s+hamkorlik[:\s]*@\w+",
    r"(?i)foto\s*manbasi?[:\s]*\S+",
    r"(?i)manba[:\s]*@\w+",
    r"(?i)@\w+_bot",
    r"t\.me/\w+",
]

COMPILED_AD_REGEX = [re.compile(p) for p in AD_PATTERNS]


def is_russian_text(text: str) -> bool:
    """Detects if text is in Russian language (Cyrillic or transliterated)."""
    if not text:
        return False

    # 1. Definite Uzbek Cyrillic markers
    if re.search(r'[ўқғҳЎҚҒҲ]', text):
        return False

    # 2. Definite Russian letter markers
    if re.search(r'[ыщЫЩ]', text):
        return True

    # 3. High-frequency Russian function words (Cyrillic)
    ru_words = {
        'в', 'на', 'и', 'с', 'для', 'по', 'о', 'об', 'из', 'от', 'к', 'до', 'не',
        'что', 'как', 'это', 'года', 'были', 'было', 'сообщает', 'время', 'также',
        'все', 'при', 'его', 'ее', 'их', 'или', 'если', 'уже', 'был', 'была',
        'проведет', 'встреч', 'центре', 'сообщили', 'году', 'после', 'более', 'детям',
        'людей', 'инвалидностью', 'возможностях', 'лекции', 'дискуссии', 'проект'
    }
    words_cyr = re.findall(r'\b[а-яёА-ЯЁ]+\b', text.lower())
    if words_cyr:
        ru_count = sum(1 for w in words_cyr if w in ru_words)
        if ru_count >= 2 or (len(words_cyr) <= 10 and ru_count >= 1):
            return True

    # 4. Transliterated Russian words (Latin)
    ru_latin_markers = {
        'dlya', 'lyudey', 'kofeynya', 'provedet', 'vstreç', 'vstrech', 'ravnыx',
        'ravnyx', 'sredы', 'sredy', 'proydut', 'lektsii', 'diskussii', 'vozmojnostyax',
        'zakrыli', 'oproşennыx', 'oproshennyx', 'sprыgnul', 'sprygnul', 'vыdelyaet'
    }
    words_lat = re.findall(r'\b[a-zA-ZçşöğÇŞÖĞыЫ]+\b', text.lower())
    if words_lat:
        marker_hits = sum(1 for w in words_lat if w in ru_latin_markers)
        if marker_hits >= 1 or 'ы' in text.lower():
            return True

    return False


def translate_to_uzbek(text: str) -> str:
    """Translates Russian/foreign text to clean natural Uzbek language."""
    if not text:
        return ""
    try:
        import html
        from deep_translator import MyMemoryTranslator

        # Split text into manageable sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        translated_chunks = []
        translator = MyMemoryTranslator(source='ru-RU', target='uz-UZ')

        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            try:
                res = translator.translate(s_clean[:450])
                res = html.unescape(res)
                translated_chunks.append(res)
            except Exception:
                translated_chunks.append(s_clean)

        uz_text = " ".join(translated_chunks)
        return uz_text
    except Exception as e:
        print(f"[Translation Warning] Could not translate text: {e}")
        return text


def transliterate_cyrillic_to_latin(text: str) -> str:
    """Translates Uzbek Cyrillic text to Uzbek Latin script, or translates Russian to Uzbek."""
    if not text:
        return ""

    # If text is Russian, translate it directly to natural Uzbek!
    if is_russian_text(text):
        return translate_to_uzbek(text)

    # Handle composite letters first (e.g. Ye at start of word)
    text = re.sub(r'(^|\s)Е', r'\1Ye', text)
    text = re.sub(r'(^|\s)е', r'\1ye', text)

    result = []
    for char in text:
        result.append(CYR_TO_LAT.get(char, char))
    return "".join(result)


def sanitize_text(text: str) -> str:
    """
    Cleans raw news text:
    - Removes channel promos, subscription calls, and tracking links
    - Normalizes quotes, apostrophes and dashes
    - Collapses redundant whitespace
    """
    if not text:
        return ""

    # Replace varied apostrophes with standard single quote
    text = text.replace("`", "'").replace("‘", "'").replace("’", "'").replace("ʻ", "'").replace("ʼ", "'")

    # Remove ad patterns
    for pattern in COMPILED_AD_REGEX:
        text = pattern.sub("", text)

    # Remove generic URLs
    text = re.sub(r'https?://[^\s]+', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def compute_content_hash(title: str, body: str) -> str:
    """Generates a SHA-256 fingerprint for idempotency and duplicate checking."""
    normalized_content = f"{title.strip().lower()}:{body.strip().lower()}"
    return hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()


def convert_to_new_uzbek_alphabet(text: str) -> str:
    """
    Transforms text to the NEW Uzbek Latin Alphabet (2026 standard):
    - Oʻ, O', O‘, O’ -> Ö
    - oʻ, o', o‘, o’ -> ö
    - Gʻ, G', G‘, G’ -> Ğ
    - gʻ, g', g‘, g’ -> ğ
    - Sh, SH -> Ş
    - sh -> ş
    - Ch, CH -> Ç
    - ch -> ç
    """
    if not text:
        return ""

    # 1. Letters with inverted commas / apostrophes
    text = re.sub(r"O[ʻ'‘ʼ`]", "Ö", text)
    text = re.sub(r"o[ʻ'‘ʼ`]", "ö", text)
    text = re.sub(r"G[ʻ'‘ʼ`]", "Ğ", text)
    text = re.sub(r"g[ʻ'‘ʼ`]", "ğ", text)

    # 2. Digraphs Sh and Ch (preserving case)
    text = re.sub(r"\bSH\b", "Ş", text)
    text = re.sub(r"SH(?=[A-ZÖĞŞÇ])", "Ş", text)
    text = re.sub(r"Sh", "Ş", text)
    text = re.sub(r"sh", "ş", text)

    text = re.sub(r"\bCH\b", "Ç", text)
    text = re.sub(r"CH(?=[A-ZÖĞŞÇ])", "Ç", text)
    text = re.sub(r"Ch", "Ç", text)
    text = re.sub(r"ch", "ç", text)

    # 3. Clean up any Cyrillic or Russian leftovers
    text = text.replace("ы", "i").replace("Ы", "I")
    text = text.replace("ь", "").replace("Ь", "")
    text = text.replace("ъ", "'").replace("Ъ", "'")
    text = text.replace("щ", "ş").replace("Щ", "Ş")

    return text


def extract_clean_headline_and_body(raw_text: str, fallback_title: str = "") -> Tuple[str, str]:
    """
    Intelligently cleans Telegram post text and extracts a proper headline:
    - Strips leading reaction emojis (e.g. 😎 😎 😎)
    - Strips channel hashtag headers (e.g. #Qonunchilikdagi_yangiliklar)
    - Strips bullet emoji icons (❗️, 🔰, 📌, ⚡️, ⚖️, etc.)
    - Finds the first coherent, informative sentence as the headline
    - Formats the remaining body into clean journalistic paragraphs
    """
    if not raw_text:
        return fallback_title or "Muhim xabar", ""

    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    cleaned_lines = []

    emoji_line_re = re.compile(r'^[\W_\d\s#\u2000-\u3300\U00010000-\U0010ffff]+$')
    hashtag_line_re = re.compile(r'^#\w+$')

    for line in lines:
        if emoji_line_re.match(line) or hashtag_line_re.match(line):
            continue
        line = re.sub(r'^[#@\w\s_]*[❗️⚡️🔴⚖️🔰📢📌🔹🔸🔺🔷🔶👉✅❌❓👇]+\s*', '', line).strip()
        line = re.sub(r'^#\w+\s*', '', line).strip()
        line = re.sub(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f900-\U0001f9ff]+', ' ', line)
        line = re.sub(r'\s+', ' ', line).strip()
        if len(line) >= 8:
            cleaned_lines.append(line)

    if not cleaned_lines:
        return fallback_title or "Muhim xabar", sanitize_text(raw_text)

    # Candidate for headline: first meaningful line
    headline_candidate = cleaned_lines[0]
    if len(headline_candidate) > 85:
        words = headline_candidate.split()
        short_title = []
        for w in words:
            if len(" ".join(short_title + [w])) <= 85:
                short_title.append(w)
            else:
                break
        headline = " ".join(short_title)
    else:
        headline = headline_candidate.rstrip(".:; ")

    body = "\n\n".join(cleaned_lines)
    return headline, body


def prepare_article_full(raw_text: str, title: str = "") -> Tuple[str, str, str]:
    """
    Returns (clean_title, clean_body, content_hash) in the NEW Uzbek Latin Alphabet (Ö, Ğ, Ş, Ç).
    Strips raw emojis, channel hashtags, and reaction bursts.
    Translates Russian or foreign text into natural Uzbek.
    """
    raw_headline, raw_body = extract_clean_headline_and_body(raw_text, title)

    if is_russian_text(raw_headline):
        raw_headline = translate_to_uzbek(raw_headline)
    if is_russian_text(raw_body):
        raw_body = translate_to_uzbek(raw_body)

    latin_headline = transliterate_cyrillic_to_latin(raw_headline)
    latin_body = transliterate_cyrillic_to_latin(raw_body)

    clean_headline = sanitize_text(latin_headline)
    clean_body = sanitize_text(latin_body)

    new_uzbek_headline = convert_to_new_uzbek_alphabet(clean_headline)
    new_uzbek_body = convert_to_new_uzbek_alphabet(clean_body)

    content_hash = compute_content_hash(new_uzbek_headline, new_uzbek_body)
    return new_uzbek_headline, new_uzbek_body, content_hash


def prepare_article_text(raw_text: str, title: str = "") -> Tuple[str, str]:
    """
    Backward-compatible 2-tuple helper: returns (clean_body, content_hash).
    """
    _, new_uzbek_body, content_hash = prepare_article_full(raw_text, title)
    return new_uzbek_body, content_hash
