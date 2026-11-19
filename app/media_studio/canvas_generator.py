"""
ROVON.UZ - Programmatic Pro Graphic Media Studio
Generates pixel-perfect, branded social news cards in the signature ROVON.UZ Pro Design:
- Dimensions: 1080 x 1350 (Standard 4:5 High-Definition Portrait Poster)
- Header: ROVON.UZ signature logo + red pill + slogan + digital globe grid
- Upper half: Cinematic news photo with smooth navy gradient transition
- Middle: Slanted red category pill + double slashes + bold italic uppercase headline
- Lower half: White details card with context-aware red icon badge and lead summary
- Footer: Calendar icon + date in Uzbek Latin + @rovonuz + dynamic red chevron ribbon
"""

import os
import re
from datetime import datetime
from typing import Optional, List, Tuple
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.ingestion.sanitizer import convert_to_new_uzbek_alphabet

UZBEK_MONTHS = {
    1: "YANVAR", 2: "FEVRAL", 3: "MART", 4: "APREL", 5: "MAY", 6: "IYUN",
    7: "IYUL", 8: "AVGUST", 9: "SENTABR", 10: "OKTABR", 11: "NOYABR", 12: "DEKABR"
}


class CanvasGenerator:
    """Generates 1080x1350 (4:5) signature ROVON.UZ Pro editorial news cards."""

    def __init__(self):
        self.width = 1080
        self.height = 1350

        # Colors matching the Pro signature design
        self.NAVY = (4, 20, 42)
        self.RED = (230, 30, 43)
        self.WHITE = (255, 255, 255)
        self.DARK_TEXT = (9, 26, 50)
        self.MUTED_NAVY = (14, 38, 72)
        self.MUTED_TEXT = (110, 130, 155)

    def _get_font(self, font_type: str, size: int) -> ImageFont.ImageFont:
        """Loads requested font with fallbacks."""
        base_dir = os.path.dirname(__file__)
        templates_fonts = os.path.join(base_dir, "templates", "fonts")

        candidates = []
        if font_type == "bold_italic":
            candidates = [
                os.path.join(templates_fonts, "segoeuiz.ttf"),
                os.path.join(templates_fonts, "arialbi.ttf"),
                os.path.join(templates_fonts, "Inter-Bold.ttf"),
                "C:/Windows/Fonts/segoeuiz.ttf",
                "C:/Windows/Fonts/arialbi.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
                settings.FONT_PATH_BOLD,
            ]
        elif font_type == "bold":
            candidates = [
                os.path.join(templates_fonts, "segoeuib.ttf"),
                os.path.join(templates_fonts, "arialbd.ttf"),
                os.path.join(templates_fonts, "Inter-Bold.ttf"),
                "C:/Windows/Fonts/segoeuib.ttf",
                "C:/Windows/Fonts/arialbd.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                settings.FONT_PATH_BOLD,
            ]
        else:
            candidates = [
                os.path.join(templates_fonts, "segoeui.ttf"),
                os.path.join(templates_fonts, "arial.ttf"),
                os.path.join(templates_fonts, "Inter-Regular.ttf"),
                "C:/Windows/Fonts/segoeui.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                settings.FONT_PATH_REGULAR,
            ]

        for p in candidates:
            if p and os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except Exception:
                    continue
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()

    def generate_news_card(
        self,
        headline: str,
        summary_text: Optional[str] = None,
        badge_text: str = "DUNYO",
        badge_color: str = "#E61E2B",
        base_image_path: Optional[str] = None,
        output_path: str = "news_card.jpg",
        date_str: Optional[str] = None,
    ) -> str:
        """
        Renders the signature ROVON.UZ Pro graphic news card.
        """
        from app.ingestion.sanitizer import is_russian_text, translate_to_uzbek
        if is_russian_text(headline):
            headline = translate_to_uzbek(headline)
        if summary_text and is_russian_text(summary_text):
            summary_text = translate_to_uzbek(summary_text)

        headline = convert_to_new_uzbek_alphabet(headline.strip() or "MUHIM RASMIY AXBOROT")
        if summary_text:
            summary_text = convert_to_new_uzbek_alphabet(summary_text.strip())
        else:
            summary_text = headline

        # Create base canvas in deep navy
        img = Image.new("RGB", (self.width, self.height), self.NAVY)
        draw = ImageDraw.Draw(img)

        # Fonts
        f_logo = self._get_font("bold_italic", 44)
        f_logo_badge = self._get_font("bold_italic", 34)
        f_slogan = self._get_font("bold", 16)
        f_category = self._get_font("bold", 26)
        f_headline = self._get_font("bold_italic", 50)
        f_body = self._get_font("bold", 34)
        f_footer = self._get_font("bold", 24)

        # ======================================================================
        # 1. HEADER (Y: 0 to 110)
        # ======================================================================
        # Top-right red angled wedge
        draw.polygon([(self.width - 110, 0), (self.width, 0), (self.width, 110), (self.width - 40, 110)], fill=self.RED)

        # Subtle digital globe dot pattern on top right
        for rx in range(680, 960, 24):
            for ry in range(25, 95, 14):
                if (rx + ry) % 3 != 0:
                    draw.ellipse((rx, ry, rx + 4, ry + 4), fill=(30, 65, 115))

        # ROVON text
        draw.text((60, 30), "ROVON", font=f_logo, fill=self.WHITE)

        # .UZ red badge
        uz_bbox = draw.textbbox((0, 0), ".UZ", font=f_logo_badge)
        uz_w = uz_bbox[2] - uz_bbox[0]
        draw.rounded_rectangle((225, 34, 225 + uz_w + 24, 82), radius=10, fill=self.RED)
        draw.text((237, 36), ".UZ", font=f_logo_badge, fill=self.WHITE)

        # Divider & Slogan
        draw.line([(345, 32), (345, 84)], fill=self.RED, width=4)
        draw.text((365, 34), "VOQEALAR RAVON,", font=f_slogan, fill=self.WHITE)
        draw.text((365, 58), "AXBOROT ANIQ.", font=f_slogan, fill=self.WHITE)
        draw.line([(0, 110), (self.width, 110)], fill=self.MUTED_NAVY, width=2)

        # ======================================================================
        # 2. PHOTO AREA (Y: 110 to 640, Height: 530px)
        # ======================================================================
        photo_h = 530
        if base_image_path and os.path.exists(base_image_path):
            try:
                base_p = Image.open(base_image_path).convert("RGB")
                pw, ph = base_p.size
                target_aspect = self.width / photo_h
                if pw / ph > target_aspect:
                    new_w = int(ph * target_aspect)
                    off = (pw - new_w) // 2
                    base_p = base_p.crop((off, 0, off + new_w, ph))
                else:
                    new_h = int(pw / target_aspect)
                    off = (ph - new_h) // 2
                    base_p = base_p.crop((0, off, pw, off + new_h))
                base_p = base_p.resize((self.width, photo_h), Image.Resampling.LANCZOS)
                img.paste(base_p, (0, 110))
            except Exception as e:
                print(f"[Canvas Warning] Could not load photo: {e}", flush=True)
                self._draw_gradient_fallback(draw, 110, photo_h)
        else:
            self._draw_gradient_fallback(draw, 110, photo_h)

        # Bottom photo gradient fade into navy
        fade_h = 160
        overlay = Image.new("RGBA", (self.width, fade_h), (0, 0, 0, 0))
        d_ov = ImageDraw.Draw(overlay)
        for y in range(fade_h):
            alpha = int(255 * (y / float(fade_h)))
            d_ov.line([(0, y), (self.width, y)], fill=(self.NAVY[0], self.NAVY[1], self.NAVY[2], alpha))
        img.paste(overlay, (0, 640 - fade_h), overlay)

        # Re-obtain draw after alpha paste
        draw = ImageDraw.Draw(img)

        # ======================================================================
        # 3. HEADLINE BANNER (Y: 640 to 920)
        # ======================================================================
        # Slanted category parallelogram
        cat_clean = badge_text.upper().strip() or "YANGILIK"
        cat_bbox = draw.textbbox((0, 0), cat_clean, font=f_category)
        cat_w = cat_bbox[2] - cat_bbox[0] + 50
        poly = [(60, 640), (60 + cat_w, 640), (45 + cat_w, 690), (45, 690)]
        draw.polygon(poly, fill=self.RED)
        draw.text((65, 648), cat_clean, font=f_category, fill=self.WHITE)

        # Double slashes //
        slash_x = 60 + cat_w + 14
        draw.line([(slash_x, 688), (slash_x + 14, 642)], fill=self.WHITE, width=4)
        draw.line([(slash_x + 12, 688), (slash_x + 26, 642)], fill=self.RED, width=4)

        # Wrap and draw uppercase bold italic headline
        hl_clean = headline.upper().strip()
        wrapped_hl = self._wrap_text(hl_clean, f_headline, max_width=920, draw=draw)[:3]

        # Dynamic left slanted vertical red accent bar matching headline height
        line_height = 62
        hl_lines_count = max(1, len(wrapped_hl))
        bar_top = 712
        bar_bottom = bar_top + (hl_lines_count * line_height) - 10
        slant = 14
        draw.polygon([
            (65, bar_top),
            (78, bar_top),
            (78 - slant, bar_bottom),
            (65 - slant, bar_bottom)
        ], fill=self.RED)

        hl_y = 712
        for line in wrapped_hl:
            draw.text((95, hl_y), line, font=f_headline, fill=self.WHITE)
            hl_y += line_height

        # ======================================================================
        # 4. WHITE DETAILS CARD (Y: 920 to 1230)
        # ======================================================================
        draw.rectangle([(0, 920), (self.width, 1230)], fill=self.WHITE)

        # Red Icon Box (60, 955, 175, 1070)
        draw.rounded_rectangle((60, 955, 175, 1070), radius=22, fill=self.RED)

        # Context-aware vector icon
        icon_type = self._detect_icon_type(f"{headline} {summary_text} {badge_text}")
        self._draw_vector_icon(draw, icon_type, (60, 955, 175, 1070), self.WHITE)

        # Extract 1-2 clean summary sentences
        clean_sum = self._prepare_summary_text(summary_text, headline)
        wrapped_sum = self._wrap_text(clean_sum, f_body, max_width=790, draw=draw)[:4]

        # Vertical red divider line matching text content height
        sum_line_height = 42
        total_sum_h = max(115, len(wrapped_sum) * sum_line_height + 10)
        draw.line([(205, 955), (205, 955 + total_sum_h)], fill=self.RED, width=3)

        sy = 955
        for sl in wrapped_sum:
            draw.text((230, sy), sl, font=f_body, fill=self.DARK_TEXT)
            sy += sum_line_height

        # ======================================================================
        # 5. FOOTER (Y: 1230 to 1350)
        # ======================================================================
        draw.rectangle([(0, 1230), (self.width, 1350)], fill=self.NAVY)
        draw.line([(0, 1230), (self.width, 1230)], fill=self.MUTED_NAVY, width=2)

        # Current Uzbek Date
        if not date_str:
            now = datetime.now()
            date_str = f"{now.day}-{UZBEK_MONTHS.get(now.month, 'OY')}, {now.year}"

        # Calendar vector icon
        draw.rounded_rectangle((60, 1262, 95, 1298), radius=6, outline=self.WHITE, width=2)
        draw.line([(60, 1272), (95, 1272)], fill=self.WHITE, width=2)
        draw.ellipse((68, 1258, 72, 1264), fill=self.WHITE)
        draw.ellipse((83, 1258, 87, 1264), fill=self.WHITE)
        draw.text((110, 1266), date_str.upper(), font=f_footer, fill=self.WHITE)

        # Vertical separator & @rovonuz
        draw.line([(400, 1264), (400, 1296)], fill=self.MUTED_TEXT, width=2)
        draw.text((425, 1266), "@ROVONUZ", font=f_footer, fill=self.WHITE)

        # Bottom-right red dynamic chevron ribbon
        draw.polygon([(self.width - 420, 1350), (self.width - 340, 1230), (self.width, 1230), (self.width, 1350)], fill=self.RED)
        draw.polygon([(self.width - 220, 1230), (self.width - 150, 1350), (self.width, 1350), (self.width, 1230)], fill=self.NAVY)

        # Save image
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        img.save(output_path, "JPEG", quality=95)
        return output_path

    def _draw_gradient_fallback(self, draw: ImageDraw.ImageDraw, start_y: int, height: int):
        """Draws a deep navy dusk gradient when no photo is provided."""
        for y in range(start_y, start_y + height):
            factor = (y - start_y) / float(height)
            r = int(12 + factor * 20)
            g = int(24 + factor * 35)
            b = int(50 + factor * 60)
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))

    def _detect_icon_type(self, text: str) -> str:
        """Determines best icon glyph based on article subject."""
        t = text.lower()
        if any(w in t for w in ["samolyot", "avia", "parvoz", "avariya", "yöl", "mashina", "avto", "poyezd"]):
            return "airplane"
        elif any(w in t for w in ["qonun", "adliya", "sud", "qaror", "huquq", "modda", "kodeks", "prezident", "farmon", "imtihon"]):
            return "justice"
        elif any(w in t for w in ["fvv", "ogohlantirish", "yong'in", "xavf", "favqulodda", "shoshilinch", "falokat"]):
            return "shield"
        return "megaphone"

    def _draw_vector_icon(self, draw: ImageDraw.ImageDraw, icon_type: str, box: Tuple[int, int, int, int], color: Tuple[int, int, int]):
        """Draws crisp vector glyphs inside the red icon box."""
        x0, y0, x1, y1 = box
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2

        if icon_type == "airplane":
            draw.polygon([(cx, cy - 35), (cx + 28, cy + 25), (cx, cy + 15), (cx - 28, cy + 25)], fill=color)
            draw.polygon([(cx - 38, cy - 2), (cx + 38, cy - 2), (cx, cy + 8)], fill=color)
        elif icon_type == "justice":
            draw.line([(cx, cy - 28), (cx, cy + 28)], fill=color, width=4)
            draw.line([(cx - 28, cy - 14), (cx + 28, cy - 14)], fill=color, width=4)
            draw.polygon([(cx - 36, cy + 10), (cx - 20, cy + 10), (cx - 28, cy + 18)], fill=color)
            draw.line([(cx - 28, cy - 14), (cx - 36, cy + 10)], fill=color, width=2)
            draw.line([(cx - 28, cy - 14), (cx - 20, cy + 10)], fill=color, width=2)
            draw.polygon([(cx + 20, cy + 10), (cx + 36, cy + 10), (cx + 28, cy + 18)], fill=color)
            draw.line([(cx + 28, cy - 14), (cx + 20, cy + 10)], fill=color, width=2)
            draw.line([(cx + 28, cy - 14), (cx + 36, cy + 10)], fill=color, width=2)
            draw.line([(cx - 20, cy + 28), (cx + 20, cy + 28)], fill=color, width=5)
        elif icon_type == "shield":
            draw.polygon([(cx - 28, cy - 24), (cx + 28, cy - 24), (cx + 28, cy + 4), (cx, cy + 30), (cx - 28, cy + 4)], fill=color)
            draw.polygon([(cx - 20, cy - 18), (cx + 20, cy - 18), (cx + 20, cy + 2), (cx, cy + 22), (cx - 20, cy + 2)], fill=self.RED)
            draw.rectangle([(cx - 3, cy - 10), (cx + 3, cy + 4)], fill=color)
            draw.ellipse((cx - 3, cy + 8, cx + 3, cy + 14), fill=color)
        else:
            # Megaphone / News speaker
            draw.polygon([(cx - 24, cy - 12), (cx + 8, cy - 24), (cx + 8, cy + 24), (cx - 24, cy + 12)], fill=color)
            draw.ellipse((cx + 4, cy - 24, cx + 14, cy + 24), fill=color)
            draw.rectangle((cx - 30, cy - 12, cx - 24, cy + 12), fill=color)
            draw.polygon([(cx - 16, cy + 12), (cx - 10, cy + 12), (cx - 14, cy + 28), (cx - 20, cy + 26)], fill=color)

    def _prepare_summary_text(self, summary_text: str, headline: str) -> str:
        """Cleans and extracts 1-2 complete sentences for the white details card, always ending with a period."""
        clean = re.sub(r'[*_#@🔗]', '', summary_text or "").strip()
        # Remove headline from beginning of summary if duplicated
        clean = re.sub(r'^\s*' + re.escape(headline) + r'[:\s.-]*', '', clean, flags=re.IGNORECASE).strip()
        # Remove any leftover partial word or lowercase crumbs at the beginning
        clean = re.sub(r'^[a-zʼʻöğşç\s,.-]+(?=[A-ZÖĞŞÇ])', '', clean).strip()

        # Split into clean sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean) if len(s.strip()) > 10]
        valid_sentences = []
        for s in sentences:
            s_clean = s.rstrip(" ,;:-")
            if s_clean and s_clean[-1] not in ".!?":
                s_clean += "."
            if len(s_clean) > 15:
                valid_sentences.append(s_clean)

        if not valid_sentences:
            c = clean.rstrip(" ,;:-")
            return c + ("." if c and c[-1] not in ".!?" else "")

        # Take up to 2 full sentences that fit comfortably in card (max ~220 chars total)
        selected = []
        total_len = 0
        for s in valid_sentences:
            if total_len + len(s) <= 220 or len(selected) == 0:
                selected.append(s)
                total_len += len(s)
            else:
                break

        res = " ".join(selected).strip().rstrip(" ,;:-")
        if res and res[-1] not in ".!?":
            res += "."
        return res

    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
        """Wraps text into lines based on pixel width."""
        words = text.split()
        lines = []
        cur = []
        for word in words:
            cur.append(word)
            bbox = draw.textbbox((0, 0), " ".join(cur), font=font)
            if (bbox[2] - bbox[0]) > max_width:
                cur.pop()
                if cur:
                    lines.append(" ".join(cur))
                cur = [word]
        if cur:
            lines.append(" ".join(cur))
        return lines


# Global instance for seamless importing
canvas_generator = CanvasGenerator()
