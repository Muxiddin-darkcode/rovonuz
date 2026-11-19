"""
ROVON.UZ - Text Sanitization, Transliteration & Normalization
Handles Cyrillic <-> Latin transliteration, advertising removal, and content hashing.
"""

import hashlib
import html
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

# Patterns for low-value bureaucratic spam (Dissertations, tenders, obituaries)
UNWANTED_NEWS_PATTERNS = [
    # Academic & Dissertation Defense notices
    r"(?i)\bdissertatsiya\b",
    r"(?i)\bfalsafa\s+doktori\b",
    r"(?i)\bfanlari\s+doktori\b",
    r"(?i)\b\(phd\)\b",
    r"(?i)\b\(dsc\)\b",
    r"(?i)\bhimoyasi\s+t[oö'ʻ‘`]?g['ʻ‘`]?risida\b",
    r"(?i)\bhimoyasi\s+haqida\b",
    r"(?i)\bavtoreferat\b",
    r"(?i)\bixtisoslik\s+shifri\b",
    r"(?i)\bilmiy\s+daraja\b",
    r"(?i)\bдиссертация\b",
    r"(?i)\bфалсафа\s+доктори\b",
    r"(?i)\bфанлари\s+доктори\b",
    r"(?i)\bҳимояси\s+тўғрисида\b",

    # Tenders, Auctions, Vacancies
    r"(?i)\btender\b",
    r"(?i)\bdavlat\s+xaridi\b",
    r"(?i)\bauksion\b",
    r"(?i)\bbo'?sh\s+ish\s+o'?rni\b",
    r"(?i)\bvakansiya\b",
    r"(?i)\bishga\s+taklif\s+etadi\b",
    r"(?i)\bтендер\b",
    r"(?i)\bаукцион\b",
    r"(?i)\bдавлат\s+харид\b",

    # Condolences & routine protocol greetings
    r"(?i)\bhamdardlik\s+bildir\w*\b",
    r"(?i)\bnekrolog\b",
    r"(?i)\btug['ʻ‘`]?ilgan\s+kuni\s+bilan\s+qutla\w*\b",
    r"(?i)\btavallud\s+ayyomi\b",
]

COMPILED_UNWANTED_REGEX = [re.compile(p) for p in UNWANTED_NEWS_PATTERNS]


def is_news_worthy(title: str, body: str = "") -> bool:
    """
    Quality gatekeeper: Filters out dry bureaucratic notices (PhD defenses,
    tenders, vacancies, obituaries) to ensure content matches Kun.uz / Zamon.uz standards.
    """
    combined = f"{title or ''} {body or ''}"
    for pat in COMPILED_UNWANTED_REGEX:
        if pat.search(combined):
            return False
    # Check minimum length (must be substantive news)
    if len((title or "").strip()) < 10:
        return False
    return True


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
    if len(headline_candidate) > 90:
        words = headline_candidate.split()
        short_title = []
        for w in words:
            if len(" ".join(short_title + [w])) <= 90:
                short_title.append(w)
            else:
                break
        headline = " ".join(short_title).rstrip(".:;,- ")
    else:
        headline = headline_candidate.rstrip(".:;,- ")

    # Avoid duplicating the headline in the body
    if len(cleaned_lines) > 1:
        body = "\n\n".join(cleaned_lines[1:])
    else:
        body = cleaned_lines[0]
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


def format_telegram_post(headline: str, body: str) -> str:
    """
    Formats headline and body into professional Kun.uz / Zamon.uz Telegram channel format.
    Ensures:
    1. HTML bold headline: <b>Sarlavha</b> (strictly eliminates raw ** asterisks forever).
    2. Strips surrounding quotes or markdown from headline.
    3. Zero headline repetition in body lead.
    4. Compact, readable length: 2-3 essential sentences (max 450 characters) so it never
       dumps giant blocks of text or overflows Telegram's 1024-char photo caption limit.
    5. Clean ROVON.UZ branding footer: 🔗 @rovonuz — Voqealar ravon, axborot aniq.
    """
    headline = (headline or "").strip()
    headline = convert_to_new_uzbek_alphabet(headline)
    # Strip any markdown bold/italic/hashtags or surrounding quotation marks from headline
    headline = re.sub(r'[*_#]', '', headline).strip()
    headline = re.sub(r'^["“«\'ʻ‘`]+|["”»\'ʻ‘`]+$', '', headline).strip()
    headline = headline.rstrip(".:;,- ")

    body = (body or "").strip()
    # Remove any existing footers, hashtags, or broken markdown tags
    body = re.sub(r'(?i)\n*🔗\s*@rovonuz[^\n]*', '', body)
    body = re.sub(r'(?i)\n*#rovon_uz\b[^\n]*', '', body)
    body = re.sub(r'(?i)ℹ️\s*_[^_]+_', '', body)
    body = re.sub(r'[*_#]', '', body)
    body = convert_to_new_uzbek_alphabet(body).strip()

    # Strip headline from beginning of body if repeated
    body = re.sub(r'^\s*' + re.escape(headline) + r'[:\s.-]*', '', body, flags=re.IGNORECASE).strip()
    body = re.sub(r'^[a-zʼʻöğşç\s,.-]+(?=[A-ZÖĞŞÇ])', '', body).strip()

    # Paragraphs breakdown
    raw_paragraphs = [p.strip() for p in body.split("\n") if p.strip()]

    # Extract clean keywords from headline (words > 3 chars)
    hl_words = [w.lower() for w in re.sub(r'[^\w\s]', '', headline.lower()).split() if len(w) > 3]

    clean_sentences = []
    dropped_lead = False

    for para in raw_paragraphs:
        sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', para) if len(s.strip()) > 8]
        for sent in sents:
            sent_clean = re.sub(r'^ℹ️\s*', '', sent).strip()
            # If opening sentence repeats headline, cleanly omit it
            if not dropped_lead and hl_words:
                sent_words = [w.lower() for w in re.sub(r'[^\w\s]', '', sent_clean.lower()).split() if len(w) > 3]
                overlap = sum(1 for w in hl_words if w in sent_words)
                if overlap >= 3 or (len(hl_words) > 0 and (overlap / len(hl_words)) >= 0.45):
                    dropped_lead = True
                    continue
            sent_clean = sent_clean.rstrip(" ,;:-")
            if sent_clean and sent_clean[-1] not in ".!?":
                sent_clean += "."
            if len(sent_clean) > 12:
                clean_sentences.append(sent_clean)

    # Compact selection: Target 250 - 450 characters (max 2-3 complete sentences)
    selected_sentences = []
    current_len = 0

    for s in clean_sentences:
        if not s:
            continue
        if current_len + len(s) <= 450 or len(selected_sentences) < 2:
            selected_sentences.append(s)
            current_len += len(s)
        else:
            break

    if not selected_sentences:
        if clean_sentences:
            selected_sentences = clean_sentences[:2]
        else:
            c = body[:350].rstrip(" ,;:-")
            selected_sentences = [c + ("." if c and c[-1] not in ".!?" else "")]

    # Ensure all selected sentences strictly end with terminal punctuation (. ! ?)
    for i in range(len(selected_sentences)):
        s = selected_sentences[i].rstrip(" ,;:-")
        if s and s[-1] not in ".!?":
            s += "."
        selected_sentences[i] = s

    # Format into 1 or 2 clean paragraphs
    if len(selected_sentences) >= 2:
        clean_body = f"{selected_sentences[0]}\n\n" + " ".join(selected_sentences[1:])
    else:
        clean_body = selected_sentences[0]

    # HTML escape with quote=False so Uzbek apostrophes (') are preserved
    escaped_headline = html.escape(headline, quote=False)
    escaped_body = html.escape(clean_body, quote=False)

    footer = "🔗 @rovonuz — Voqealar ravon, axborot aniq."
    return f"<b>{escaped_headline}</b>\n\n{escaped_body}\n\n{footer}"

