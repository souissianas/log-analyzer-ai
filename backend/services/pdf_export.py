import io
from datetime import datetime
from fpdf import FPDF
from anyascii import anyascii


# ── Character sanitization ────────────────────────────────────────────────────

def safe_str(s: str) -> str:
    """
    Sanitizes strings to prevent UnicodeEncodeError in FPDF (Latin-1).
    Converts smart quotes, em-dashes, emojis and unrepresentable characters.
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
    return "".join(result)


# ── Color palette ─────────────────────────────────────────────────────────────

COLORS = {
    "primary":   (37,  99,  235),   # Blue-600
    "dark":      (15,  23,  42),    # Slate-900
    "surface":   (241, 245, 249),   # Slate-100
    "white":     (255, 255, 255),
    "muted":     (100, 116, 139),   # Slate-500
    "success":   (16,  185, 129),   # Emerald-500
    "warning":   (245, 158,  11),   # Amber-500
    "error":     (239,  68,  68),   # Red-500
    "critical":  (124,  58, 237),   # Violet-600
    "border":    (226, 232, 240),   # Slate-200
    "accent_bg": (239, 246, 255),   # Blue-50
}

LEVEL_COLORS = {
    "CRITICAL": COLORS["critical"],
    "FATAL":    COLORS["critical"],
    "ERROR":    COLORS["error"],
    "FAIL":     COLORS["error"],
    "WARNING":  COLORS["warning"],
    "WARN":     COLORS["warning"],
}


def _level_color(level: str) -> tuple:
    return LEVEL_COLORS.get((level or "").upper(), COLORS["primary"])


# ── Layout helpers ────────────────────────────────────────────────────────────

PAGE_W    = 210
MARGIN    = 18
CONTENT_W = PAGE_W - 2 * MARGIN


def _set_fill(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_fill_color(*rgb)


def _set_text(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_text_color(*rgb)


def _set_draw(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_draw_color(*rgb)


def _rule(pdf: FPDF, y_offset: float = 2, color=None) -> None:
    """Draw a thin horizontal rule."""
    color = color or COLORS["border"]
    _set_draw(pdf, color)
    pdf.set_line_width(0.3)
    x = pdf.get_x()
    y = pdf.get_y() + y_offset
    pdf.line(MARGIN, y, PAGE_W - MARGIN, y)
    pdf.ln(y_offset + 2)


def _badge(pdf: FPDF, text: str, bg: tuple, fg: tuple = COLORS["white"],
           x: float = None, y: float = None, w: float = 28, h: float = 6,
           uppercase: bool = True) -> None:
    """Draw a filled rounded-rectangle badge with centred text."""
    x = x if x is not None else pdf.get_x()
    y = y if y is not None else pdf.get_y()
    pdf.set_xy(x, y)
    _set_fill(pdf, bg)
    _set_text(pdf, fg)
    pdf.set_font("Arial", "B", 7.5)
    txt_to_draw = text.upper() if uppercase else text
    pdf.cell(w, h, safe_str(txt_to_draw), border=0, ln=0, align="C", fill=True)


# ── Cover / header page block ─────────────────────────────────────────────────

def _write_cover(pdf: FPDF, item: dict, data: dict) -> None:
    """Full-width branded cover block at the top of the first page."""
    # Blue header band
    _set_fill(pdf, COLORS["primary"])
    pdf.rect(0, 0, PAGE_W, 46, "F")

    # App name (top-left)
    pdf.set_xy(MARGIN, 8)
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, "Log Analyzer AI", ln=False)

    # Report label (top-right)
    pdf.set_xy(PAGE_W - MARGIN - 38, 8)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(38, 8, "Rapport d'Analyse", align="R", ln=False)

    # Subtitle – filename
    filename = safe_str(data.get("filename", "fichier"))
    pdf.set_xy(MARGIN, 20)
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, f"Analyse : {filename}", ln=True)

    # Meta row
    created = safe_str(str(item.get("created_at", "")[:19]).replace("T", " "))
    log_id  = safe_str(str(item.get("id", "-")))
    pdf.set_xy(MARGIN, 30)
    pdf.set_font("Arial", size=8.5)
    _set_text(pdf, (200, 220, 255))
    pdf.cell(0, 6, f"ID : {log_id}     |     Date : {created}     |     Generated : {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)

    pdf.set_y(52)


# ── Summary stats strip ───────────────────────────────────────────────────────

def _write_stats(pdf: FPDF, data: dict) -> None:
    """Three KPI boxes: Detected / Analyzed / Skipped."""
    total    = data.get("total_errors_found", 0)
    analyzed = data.get("total_analyzed", len(data.get("analyzed", [])))
    skipped  = data.get("skipped", 0)

    labels  = ["Erreurs detectees", "Erreurs analysees", "Ignorees"]
    values  = [str(total), str(analyzed), str(skipped)]
    colors  = [COLORS["error"], COLORS["primary"], COLORS["muted"]]
    box_w   = CONTENT_W / 3
    y       = pdf.get_y()

    for i, (lbl, val, clr) in enumerate(zip(labels, values, colors)):
        x = MARGIN + i * box_w
        # Box background
        _set_fill(pdf, COLORS["surface"])
        _set_draw(pdf, COLORS["border"])
        pdf.set_line_width(0.4)
        pdf.rect(x, y, box_w - 3, 22, "FD")
        # Big number
        pdf.set_xy(x, y + 2)
        _set_text(pdf, clr)
        pdf.set_font("Arial", "B", 18)
        pdf.cell(box_w - 3, 10, val, align="C", ln=False)
        # Label
        pdf.set_xy(x, y + 13)
        _set_text(pdf, COLORS["muted"])
        pdf.set_font("Arial", size=7.5)
        pdf.cell(box_w - 3, 5, safe_str(lbl).upper(), align="C", ln=False)

    pdf.ln(28)
    _rule(pdf, y_offset=0)


# ── Single error card ─────────────────────────────────────────────────────────

def _write_error_card(pdf: FPDF, ai: dict) -> None:
    """Draw one analysed-error card with a coloured left accent bar."""
    level  = (ai.get("level") or "").upper()
    clr    = _level_color(level)
    cat    = ai.get("category", "")
    index  = ai.get("index", "?")
    msg    = safe_str(ai.get("message", ""))
    analysis = ai.get("analysis") or {}

    y_start = pdf.get_y()
    x0      = MARGIN

    # Card background
    _set_fill(pdf, COLORS["surface"])
    _set_draw(pdf, COLORS["border"])
    pdf.set_line_width(0.3)

    # Title row – level badge + "Error #N" + category
    pdf.set_xy(x0 + 6, y_start + 3)
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", "B", 10)
    title_txt = safe_str(f"Erreur #{index}")
    pdf.cell(40, 6, title_txt, ln=False)

    # Level badge
    bx = pdf.get_x() + 2
    _badge(pdf, level, clr, COLORS["white"], x=bx, y=y_start + 3, w=22, h=6)

    # Category badge (if any)
    if cat and cat != "unknown":
        _badge(pdf, cat, COLORS["accent_bg"], COLORS["primary"],
               x=bx + 25, y=y_start + 3, w=40, h=6, uppercase=False)

    # Line number / timestamp row
    line_no  = ai.get("line_number")
    ts       = ai.get("timestamp", "")
    meta_parts = []
    if line_no:
        meta_parts.append(f"Ligne {line_no}")
    if ts:
        meta_parts.append(safe_str(str(ts)))
    if meta_parts:
        pdf.set_xy(x0 + 6, y_start + 10)
        _set_text(pdf, COLORS["muted"])
        pdf.set_font("Arial", "I", 8)
        pdf.cell(CONTENT_W, 5, " | ".join(meta_parts), ln=False)

    # Message
    pdf.set_xy(x0 + 6, y_start + 17)
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", size=9)
    pdf.multi_cell(CONTENT_W - 8, 5, msg)

    # Explanation
    explanation = safe_str(analysis.get("explanation", ""))
    if explanation:
        pdf.set_x(x0 + 6)
        _set_text(pdf, COLORS["muted"])
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(CONTENT_W - 8, 5, "Explication", ln=True)
        pdf.set_x(x0 + 6)
        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        pdf.multi_cell(CONTENT_W - 8, 5, explanation)

    # Causes
    causes = analysis.get("causes", [])
    if causes:
        pdf.set_x(x0 + 6)
        _set_text(pdf, COLORS["warning"])
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(CONTENT_W - 8, 5, "Causes possibles", ln=True)
        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        for c in causes:
            pdf.set_x(x0 + 10)
            pdf.multi_cell(CONTENT_W - 14, 5, safe_str(f"\u2022 {c}"))

    # Solutions
    solutions = analysis.get("solutions", [])
    if solutions:
        pdf.set_x(x0 + 6)
        _set_text(pdf, COLORS["success"])
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(CONTENT_W - 8, 5, "Solutions recommandees", ln=True)
        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        for s in solutions:
            pdf.set_x(x0 + 10)
            pdf.multi_cell(CONTENT_W - 14, 5, safe_str(f"\u2022 {s}"))

    y_end = pdf.get_y() + 3

    # Draw card border and left accent bar
    card_h = max(24, y_end - y_start)
    _set_draw(pdf, COLORS["border"])
    pdf.rect(x0, y_start, CONTENT_W, card_h, "D")
    # Coloured left accent bar
    _set_fill(pdf, clr)
    pdf.rect(x0, y_start, 3.5, card_h, "F")

    pdf.set_y(y_end + 4)


# ── Footer on every page ──────────────────────────────────────────────────────

class ProfessionalPDF(FPDF):
    def footer(self):
        self.set_y(-14)
        self.set_line_width(0.3)
        self.set_draw_color(*COLORS["border"])
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(2)
        self.set_font("Arial", "I", 7.5)
        self.set_text_color(*COLORS["muted"])
        self.cell(0, 5, f"Log Analyzer AI  |  Page {self.page_no()}", align="C")


# ── Public API ────────────────────────────────────────────────────────────────

def build_analysis_pdf(item: dict) -> io.BytesIO:
    data = item.get("data") or {}

    pdf = ProfessionalPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Cover
    _write_cover(pdf, item, data)

    # KPI strip
    _write_stats(pdf, data)

    # Section heading
    pdf.ln(2)
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Details des erreurs analysees", ln=True)
    _rule(pdf, y_offset=1, color=COLORS["primary"])
    pdf.ln(2)

    for ai in data.get("analyzed", []):
        _write_error_card(pdf, ai)

    # Closing note
    pdf.ln(4)
    _set_fill(pdf, COLORS["accent_bg"])
    _set_draw(pdf, COLORS["border"])
    pdf.rect(MARGIN, pdf.get_y(), CONTENT_W, 12, "FD")
    pdf.set_xy(MARGIN + 4, pdf.get_y() + 3)
    _set_text(pdf, COLORS["primary"])
    pdf.set_font("Arial", "B", 8.5)
    pdf.cell(0, 5, "Rapport genere automatiquement par Log Analyzer AI  -  Powered by Ollama / LLaMA 3.2", ln=True)

    bio = io.BytesIO()
    bio.write(pdf.output(dest="S").encode("latin-1"))
    bio.seek(0)
    return bio
