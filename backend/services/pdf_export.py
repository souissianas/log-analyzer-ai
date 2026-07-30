import io
import re
from datetime import datetime
from fpdf import FPDF
from anyascii import anyascii


# ── Character sanitization & Text Normalization ───────────────────────────────

def safe_str(s: str) -> str:
    """
    Sanitizes strings to prevent UnicodeEncodeError in FPDF (Latin-1).
    Converts smart quotes, em-dashes, emojis and unrepresentable characters.
    Also normalizes whitespace (replaces multiple spaces/tabs with a single space).
    """
    if not isinstance(s, str):
        return str(s or "")

    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2014": "-", "\u2013": "-", "\u0153": "oe", "\u0152": "OE",
        "\u00e6": "ae", "\u00c6": "AE", "\u2026": "...", "\u2022": "*",
        "\U0001f6a8": "[ALERT]", "\U0001f4c1": "[FILE]",
        "\U0001f4a5": "[CRITICAL]", "\U0001f3f7\ufe0f": "[TAG]",
        "\u26a0\ufe0f": "[WARN]", "\u2705": "[OK]", "\u274c": "[ERROR]",
    }
    for orig, repl in replacements.items():
        s = s.replace(orig, repl)

    result = []
    for char in s:
        try:
            char.encode("latin-1")
            result.append(char)
        except UnicodeEncodeError:
            result.append(anyascii(char))

    cleaned = "".join(result)
    # Normalize multiple inline spaces
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
    return cleaned


# ── Color Palette ─────────────────────────────────────────────────────────────

COLORS = {
    "primary":      (37,  99,  235),   # Blue-600  #2563eb
    "primary_dark": (30,  58,  138),   # Blue-900  #1e3a8a
    "dark":         (15,  23,  42),    # Slate-900 #0f172a
    "surface":      (248, 250, 252),   # Slate-50  #f8fafc
    "surface_card": (241, 245, 249),   # Slate-100 #f1f5f9
    "white":        (255, 255, 255),
    "muted":        (100, 116, 139),   # Slate-500 #64748b
    "success":      (4,   120, 87),    # Emerald-700 #047857
    "success_bg":   (236, 253, 245),   # Emerald-50
    "warning":      (180, 83,  9),     # Amber-700  #b45309
    "warning_bg":   (255, 251, 235),   # Amber-50
    "error":        (220, 38,  38),    # Red-600   #dc2626
    "error_bg":     (254, 242, 242),   # Red-50
    "critical":     (124, 58,  237),   # Violet-600 #7c3aed
    "critical_bg":  (245, 243, 255),   # Violet-50
    "border":       (226, 232, 240),   # Slate-200 #e2e8f0
    "accent_bg":    (239, 246, 255),   # Blue-50   #eff6ff
    "info":         (37,  99,  235),   # Blue-600 (EXCEPTION/INFO)
    "info_bg":      (239, 246, 255),   # Blue-50
}

LEVEL_SCHEMES = {
    "CRITICAL":  {"fg": COLORS["critical"], "bg": COLORS["critical_bg"], "badge_bg": COLORS["critical"]},
    "FATAL":     {"fg": COLORS["critical"], "bg": COLORS["critical_bg"], "badge_bg": COLORS["critical"]},
    "ERROR":     {"fg": COLORS["error"],    "bg": COLORS["error_bg"],    "badge_bg": COLORS["error"]},
    "FAIL":      {"fg": COLORS["error"],    "bg": COLORS["error_bg"],    "badge_bg": COLORS["error"]},
    "WARNING":   {"fg": COLORS["warning"],  "bg": COLORS["warning_bg"],  "badge_bg": COLORS["warning"]},
    "WARN":      {"fg": COLORS["warning"],  "bg": COLORS["warning_bg"],  "badge_bg": COLORS["warning"]},
    "EXCEPTION": {"fg": COLORS["info"],     "bg": COLORS["info_bg"],     "badge_bg": COLORS["info"]},
    "INFO":      {"fg": COLORS["muted"],    "bg": COLORS["surface"],     "badge_bg": COLORS["muted"]},
}


def _level_scheme(level: str) -> dict:
    return LEVEL_SCHEMES.get(
        (level or "").upper(),
        {"fg": COLORS["info"], "bg": COLORS["info_bg"], "badge_bg": COLORS["info"]}
    )


# ── Page Metrics ──────────────────────────────────────────────────────────────

PAGE_W    = 210
MARGIN    = 14
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Helpers ───────────────────────────────────────────────────────────────────

def _set_fill(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_fill_color(*rgb)


def _set_text(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_text_color(*rgb)


def _set_draw(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_draw_color(*rgb)


def _solid_badge(pdf: FPDF, text: str, bg: tuple, x: float, y: float,
                 w: float = 28, h: float = 6.5) -> None:
    """Solid colored badge with white text (like the level badges in screenshots)."""
    _set_fill(pdf, bg)
    _set_draw(pdf, bg)
    pdf.set_line_width(0.1)
    pdf.rect(x, y, w, h, "F")
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 8)
    pdf.set_xy(x, y + 0.5)
    pdf.cell(w, h - 1, text.upper(), border=0, ln=0, align="C")


def _outline_badge(pdf: FPDF, text: str, border_color: tuple, text_color: tuple,
                   x: float, y: float, w: float = 36, h: float = 6.5) -> None:
    """Outlined badge with colored border and text (for category)."""
    _set_fill(pdf, COLORS["white"])
    _set_draw(pdf, border_color)
    pdf.set_line_width(0.4)
    pdf.rect(x, y, w, h, "FD")
    _set_text(pdf, text_color)
    pdf.set_font("Arial", size=7.5)
    pdf.set_xy(x, y + 0.5)
    pdf.cell(w, h - 1, safe_str(text), border=0, ln=0, align="C")


# ── PDF Document Class with Footer ───────────────────────────────────────────

class ProfessionalPDF(FPDF):
    def footer(self):
        self.set_y(-13)
        self.set_line_width(0.2)
        _set_draw(self, COLORS["border"])
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(2)
        self.set_font("Arial", "I", 8)
        _set_text(self, COLORS["muted"])
        self.cell(0, 5, f"Log Analyzer AI   -   Page {self.page_no()}", align="C")


# ── Header Block ──────────────────────────────────────────────────────────────

def _write_header_block(pdf: FPDF, item: dict, data: dict) -> None:
    """Large branded blue header matching the screenshot design."""
    BANNER_H = 52

    # Full-width blue banner
    _set_fill(pdf, COLORS["primary"])
    pdf.rect(0, 0, PAGE_W, BANNER_H, "F")

    # ── Row 1: App title + badge ──────────────────────────────────
    pdf.set_xy(MARGIN, 10)
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 18)
    pdf.cell(120, 9, "Log Analyzer AI", ln=False)

    # "RAPPORT D'ANALYSE" right-aligned badge text
    pdf.set_xy(PAGE_W - MARGIN - 55, 10)
    pdf.set_font("Arial", "B", 10)
    _set_text(pdf, (210, 230, 255))
    pdf.cell(55, 9, "RAPPORT D'ANALYSE", align="R", ln=False)

    # ── Row 2: Filename ───────────────────────────────────────────
    filename = safe_str(data.get("filename", "fichier.log"))
    pdf.set_xy(MARGIN, 22)
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, f"Fichier analyse : {filename}", ln=True)

    # ── Row 3: Metadata ───────────────────────────────────────────
    created_raw = str(item.get("created_at", ""))
    created_fmt = created_raw[:19].replace("T", " ") if "T" in created_raw else created_raw
    log_id = str(item.get("id", "-"))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    pdf.set_xy(MARGIN, 32)
    pdf.set_font("Arial", size=8.5)
    _set_text(pdf, (195, 220, 255))
    meta_line = safe_str(
        f"ID Rapport : #{log_id}   |   Analyse du : {created_fmt}   |   Genere le : {now_str}"
    )
    pdf.cell(0, 6, meta_line, ln=True)

    # Small separator line inside banner
    _set_draw(pdf, (80, 130, 210))
    pdf.set_line_width(0.3)
    pdf.line(MARGIN, 41, PAGE_W - MARGIN, 41)

    pdf.set_y(BANNER_H + 6)


# ── KPI Summary Cards ─────────────────────────────────────────────────────────

def _write_kpi_summary(pdf: FPDF, data: dict) -> None:
    """Three metric boxes exactly matching screenshot style."""
    total    = data.get("total_errors_found", 0)
    analyzed = data.get("total_analyzed", len(data.get("analyzed", [])))
    skipped  = data.get("skipped", 0)

    labels = ["ERREURS DETECTEES", "ERREURS ANALYSEES PAR IA", "LIGNES IGNOREES"]
    values = [str(total), str(analyzed), str(skipped)]
    val_colors = [COLORS["error"], COLORS["primary"], COLORS["muted"]]

    box_w = (CONTENT_W - 6) / 3   # 2px gap between each
    box_h = 22
    y     = pdf.get_y()

    for i, (lbl, val, clr) in enumerate(zip(labels, values, val_colors)):
        x = MARGIN + i * (box_w + 3)

        # Card background + border
        _set_fill(pdf, COLORS["white"])
        _set_draw(pdf, COLORS["border"])
        pdf.set_line_width(0.4)
        pdf.rect(x, y, box_w, box_h, "FD")

        # Large numeric value
        pdf.set_xy(x, y + 2)
        _set_text(pdf, clr)
        pdf.set_font("Arial", "B", 17)
        pdf.cell(box_w, 10, val, align="C", ln=False)

        # Label underneath
        pdf.set_xy(x, y + 14)
        _set_text(pdf, COLORS["muted"])
        pdf.set_font("Arial", "B", 6.5)
        pdf.cell(box_w, 5, safe_str(lbl), align="C", ln=False)

    pdf.set_y(y + box_h + 8)


# ── Section Title ─────────────────────────────────────────────────────────────

def _write_section_title(pdf: FPDF, title: str) -> None:
    """Bold section title with blue underline, matching screenshot style."""
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", "B", 13)
    pdf.set_x(MARGIN)
    pdf.cell(0, 8, safe_str(title), ln=True)

    # Blue underline beneath the text
    _set_draw(pdf, COLORS["primary"])
    pdf.set_line_width(0.8)
    y = pdf.get_y()
    pdf.line(MARGIN, y, MARGIN + 70, y)
    pdf.ln(6)


# ── Single Error Card ─────────────────────────────────────────────────────────

def _write_error_section(pdf: FPDF, ai: dict) -> None:
    """Renders one structured error block matching the screenshot design."""

    # Page break if near the bottom
    if pdf.get_y() > 242:
        pdf.add_page()

    level   = (ai.get("level") or "ERROR").upper()
    scheme  = _level_scheme(level)
    cat     = ai.get("category", "")
    index   = ai.get("index", "?")
    msg     = safe_str(ai.get("message", ""))
    analysis = ai.get("analysis") or {}

    y_start  = pdf.get_y()
    x0       = MARGIN
    CARD_H   = 9          # header strip height

    # ── 1. Full-width colored header strip ───────────────────────────────────
    _set_fill(pdf, scheme["bg"])
    _set_draw(pdf, scheme["fg"])
    pdf.set_line_width(0.4)
    pdf.rect(x0, y_start, CONTENT_W, CARD_H, "FD")

    # "Erreur #N"  — colored text
    pdf.set_xy(x0 + 4, y_start + 1.5)
    _set_text(pdf, scheme["fg"])
    pdf.set_font("Arial", "B", 10)
    pdf.cell(30, 6, safe_str(f"Erreur #{index}"), ln=False)

    # Level badge: solid colored with white text
    badge_x = x0 + 36
    _solid_badge(pdf, level, scheme["badge_bg"], x=badge_x, y=y_start + 1.5, w=26, h=6)

    # Category badge: outlined, right of level badge
    if cat and cat.lower() not in ("", "unknown"):
        cat_label = f"[{cat}]" if not cat.startswith("[") else cat
        _outline_badge(pdf, cat_label, scheme["fg"], scheme["fg"],
                       x=badge_x + 29, y=y_start + 1.5, w=38, h=6)

    # Line number & timestamp — right-aligned italic
    line_no = ai.get("line_number")
    ts      = ai.get("timestamp", "")
    parts   = []
    if line_no:
        parts.append(f"Ligne {line_no}")
    if ts:
        parts.append(str(ts)[:19])
    if parts:
        pdf.set_xy(PAGE_W - MARGIN - 65, y_start + 1.5)
        _set_text(pdf, scheme["fg"])
        pdf.set_font("Arial", "I", 8)
        pdf.cell(62, 6, safe_str("   |   ".join(parts)), align="R", ln=False)

    pdf.set_y(y_start + CARD_H + 3)

    # ── 2. Message ───────────────────────────────────────────────────────────
    pdf.set_x(x0 + 3)
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", "B", 9)
    pdf.cell(20, 5, "Message : ", ln=False)
    pdf.set_font("Arial", size=9)
    _set_text(pdf, (30, 41, 59))
    pdf.multi_cell(CONTENT_W - 24, 5, msg)
    pdf.ln(1)

    # ── 3. Explication ───────────────────────────────────────────────────────
    explanation = safe_str(analysis.get("explanation", ""))
    if explanation:
        pdf.set_x(x0 + 3)
        _set_text(pdf, COLORS["primary_dark"])
        pdf.set_font("Arial", "B", 9)
        pdf.cell(CONTENT_W - 5, 5, "Explication :", ln=True)

        pdf.set_x(x0 + 8)
        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        pdf.multi_cell(CONTENT_W - 12, 5, explanation)
        pdf.ln(1)

    # ── 4. Causes possibles ──────────────────────────────────────────────────
    causes = analysis.get("causes", [])
    if causes:
        pdf.set_x(x0 + 3)
        _set_text(pdf, COLORS["warning"])
        pdf.set_font("Arial", "B", 9)
        pdf.cell(CONTENT_W - 5, 5, "Causes possibles :", ln=True)

        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        for cause in causes:
            pdf.set_x(x0 + 10)
            pdf.multi_cell(CONTENT_W - 14, 4.5, safe_str(f"- {cause}"))
        pdf.ln(1)

    # ── 5. Solutions recommandees ────────────────────────────────────────────
    solutions = analysis.get("solutions", [])
    if solutions:
        pdf.set_x(x0 + 3)
        _set_text(pdf, COLORS["success"])
        pdf.set_font("Arial", "B", 9)
        pdf.cell(CONTENT_W - 5, 5, "Solutions recommandees :", ln=True)

        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        for sol in solutions:
            pdf.set_x(x0 + 10)
            pdf.multi_cell(CONTENT_W - 14, 4.5, safe_str(f"- {sol}"))
        pdf.ln(1)

    # ── Separator ────────────────────────────────────────────────────────────
    _set_draw(pdf, COLORS["border"])
    pdf.set_line_width(0.25)
    sep_y = pdf.get_y() + 2
    pdf.line(MARGIN, sep_y, PAGE_W - MARGIN, sep_y)
    pdf.ln(7)


# ── Public Export Function ────────────────────────────────────────────────────

def build_analysis_pdf(item: dict) -> io.BytesIO:
    data = item.get("data") or {}

    pdf = ProfessionalPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # 1. Header Banner
    _write_header_block(pdf, item, data)

    # 2. KPI Summary Cards
    _write_kpi_summary(pdf, data)

    # 3. Main Section Title
    _write_section_title(pdf, "Details des Erreurs Analysees")

    # 4. Error Cards
    analyzed_items = data.get("analyzed", [])
    for ai in analyzed_items:
        _write_error_section(pdf, ai)

    # Return BytesIO stream
    bio = io.BytesIO()
    bio.write(pdf.output(dest="S").encode("latin-1"))
    bio.seek(0)
    return bio
