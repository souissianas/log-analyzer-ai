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
    # Normalize multiple inline spaces (e.g. "Stack   trace:   java...") -> "Stack trace: java..."
    cleaned = re.sub(r'[ \t]+', ' ', cleaned).strip()
    return cleaned


# ── Color Palette ─────────────────────────────────────────────────────────────

COLORS = {
    "primary":     (37,  99,  235),   # Blue-600 #2563eb
    "primary_dark":(30,  58,  138),   # Blue-900 #1e3a8a
    "dark":        (15,  23,  42),    # Slate-900 #0f172a
    "surface":     (248, 250, 252),   # Slate-50 #f8fafc
    "surface_card":(241, 245, 249),   # Slate-100 #f1f5f9
    "white":       (255, 255, 255),
    "muted":       (100, 116, 139),   # Slate-500 #64748b
    "success":     (4,   120, 87),    # Emerald-700 #047857
    "success_bg":  (236, 253, 245),   # Emerald-50
    "warning":     (180, 83,  9),     # Amber-700 #b45309
    "warning_bg":  (254, 243, 199),   # Amber-100
    "error":       (220, 38,  38),    # Red-600 #dc2626
    "error_bg":    (254, 226, 226),   # Red-100
    "critical":    (124, 58,  237),   # Violet-600 #7c3aed
    "critical_bg": (243, 232, 255),   # Violet-100
    "border":      (226, 232, 240),   # Slate-200 #e2e8f0
    "accent_bg":   (239, 246, 255),   # Blue-50 #eff6ff
}

LEVEL_SCHEMES = {
    "CRITICAL": {"fg": COLORS["critical"], "bg": COLORS["critical_bg"]},
    "FATAL":    {"fg": COLORS["critical"], "bg": COLORS["critical_bg"]},
    "ERROR":    {"fg": COLORS["error"],    "bg": COLORS["error_bg"]},
    "FAIL":     {"fg": COLORS["error"],    "bg": COLORS["error_bg"]},
    "WARNING":  {"fg": COLORS["warning"],  "bg": COLORS["warning_bg"]},
    "WARN":     {"fg": COLORS["warning"],  "bg": COLORS["warning_bg"]},
}


def _level_scheme(level: str) -> dict:
    return LEVEL_SCHEMES.get((level or "").upper(), {"fg": COLORS["primary"], "bg": COLORS["accent_bg"]})


# ── Page Metrics ──────────────────────────────────────────────────────────────

PAGE_W    = 210
MARGIN    = 16
CONTENT_W = PAGE_W - 2 * MARGIN


def _set_fill(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_fill_color(*rgb)


def _set_text(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_text_color(*rgb)


def _set_draw(pdf: FPDF, rgb: tuple) -> None:
    pdf.set_draw_color(*rgb)


def _badge(pdf: FPDF, text: str, bg: tuple, fg: tuple,
           x: float, y: float, w: float = 26, h: float = 6, uppercase: bool = True) -> None:
    """Draw a rounded filled badge with centered text."""
    pdf.set_xy(x, y)
    _set_fill(pdf, bg)
    _set_text(pdf, fg)
    pdf.set_font("Arial", "B", 8)
    txt_to_draw = text.upper() if uppercase else text
    pdf.cell(w, h, safe_str(txt_to_draw), border=0, ln=0, align="C", fill=True)


# ── PDF Document Class with Footer ───────────────────────────────────────────

class ProfessionalPDF(FPDF):
    def footer(self):
        self.set_y(-14)
        self.set_line_width(0.3)
        _set_draw(self, COLORS["border"])
        self.line(MARGIN, self.get_y(), PAGE_W - MARGIN, self.get_y())
        self.ln(2)
        self.set_font("Arial", "I", 8)
        _set_text(self, COLORS["muted"])
        self.cell(0, 5, f"Log Analyzer AI   -   Page {self.page_no()}", align="C")


# ── Header Block ──────────────────────────────────────────────────────────────

def _write_header_block(pdf: FPDF, item: dict, data: dict) -> None:
    """Branded top header card."""
    # Top banner background
    _set_fill(pdf, COLORS["primary"])
    pdf.rect(0, 0, PAGE_W, 44, "F")

    # App title
    pdf.set_xy(MARGIN, 9)
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, "Log Analyzer AI", ln=False)

    # Document type tag
    pdf.set_xy(PAGE_W - MARGIN - 45, 9)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(220, 235, 255)
    pdf.cell(45, 8, "RAPPORT D'ANALYSE", align="R", ln=False)

    # Filename
    filename = safe_str(data.get("filename", "fichier.log"))
    pdf.set_xy(MARGIN, 20)
    _set_text(pdf, COLORS["white"])
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, f"Fichier analysé : {filename}", ln=True)

    # Metadata (Date & ID)
    created_raw = str(item.get("created_at", ""))
    # Format date cleanly (e.g. 2026-07-29 15:46)
    created_fmt = created_raw[:19].replace("T", " ") if "T" in created_raw else created_raw
    log_id = str(item.get("id", "-"))

    pdf.set_xy(MARGIN, 30)
    pdf.set_font("Arial", size=8.5)
    pdf.set_text_color(200, 225, 255)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    pdf.cell(0, 6, safe_str(f"ID Rapport : #{log_id}   |   Analyse du : {created_fmt}   |   Généré le : {now_str}"), ln=True)

    pdf.set_y(50)


# ── KPI Summary Cards ─────────────────────────────────────────────────────────

def _write_kpi_summary(pdf: FPDF, data: dict) -> None:
    """Summary metric boxes."""
    total    = data.get("total_errors_found", 0)
    analyzed = data.get("total_analyzed", len(data.get("analyzed", [])))
    skipped  = data.get("skipped", 0)

    labels = ["Erreurs Détectées", "Erreurs Analysées par IA", "Lignes Ignorées"]
    values = [str(total), str(analyzed), str(skipped)]
    colors = [COLORS["error"], COLORS["primary"], COLORS["muted"]]
    box_w  = CONTENT_W / 3
    y      = pdf.get_y()

    for i, (lbl, val, clr) in enumerate(zip(labels, values, colors)):
        x = MARGIN + i * box_w
        # Draw background card
        _set_fill(pdf, COLORS["surface"])
        _set_draw(pdf, COLORS["border"])
        pdf.set_line_width(0.3)
        pdf.rect(x, y, box_w - 3, 20, "FD")

        # Metric value
        pdf.set_xy(x, y + 2)
        _set_text(pdf, clr)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(box_w - 3, 9, val, align="C", ln=False)

        # Metric label
        pdf.set_xy(x, y + 12)
        _set_text(pdf, COLORS["muted"])
        pdf.set_font("Arial", "B", 7)
        pdf.cell(box_w - 3, 5, safe_str(lbl.upper()), align="C", ln=False)

    pdf.set_y(y + 26)


# ── Single Error Section (Clean, Structured, Colored Titles) ─────────────────

def _write_error_section(pdf: FPDF, ai: dict) -> None:
    """Renders one structured error block with colored headers and clean indentation."""
    # Ensure we don't start a new card right at the bottom of the page
    if pdf.get_y() > 240:
        pdf.add_page()

    level    = (ai.get("level") or "ERROR").upper()
    scheme   = _level_scheme(level)
    cat      = ai.get("category", "")
    index    = ai.get("index", "?")
    msg      = safe_str(ai.get("message", ""))
    analysis = ai.get("analysis") or {}

    y_start = pdf.get_y()
    x0      = MARGIN

    # 1. Header Bar for Error Item
    _set_fill(pdf, scheme["bg"])
    _set_draw(pdf, COLORS["border"])
    pdf.set_line_width(0.4)
    pdf.rect(x0, y_start, CONTENT_W, 9, "FD")

    # Title text
    pdf.set_xy(x0 + 4, y_start + 1.5)
    _set_text(pdf, scheme["fg"])
    pdf.set_font("Arial", "B", 10)
    pdf.cell(30, 6, safe_str(f"Erreur #{index}"), ln=False)

    # Level Badge
    _badge(pdf, level, scheme["fg"], COLORS["white"], x=x0 + 32, y=y_start + 1.5, w=24, h=6)

    # Category Badge (if any)
    if cat and cat != "unknown":
        _badge(pdf, f"[{cat}]", COLORS["accent_bg"], COLORS["primary_dark"],
               x=x0 + 58, y=y_start + 1.5, w=35, h=6, uppercase=False)

    # Line number & timestamp meta info on the right
    line_no = ai.get("line_number")
    ts      = ai.get("timestamp", "")
    meta_str = []
    if line_no:
        meta_str.append(f"Ligne {line_no}")
    if ts:
        meta_str.append(str(ts)[:19])
    if meta_str:
        pdf.set_xy(PAGE_W - MARGIN - 60, y_start + 1.5)
        _set_text(pdf, COLORS["muted"])
        pdf.set_font("Arial", "I", 8)
        pdf.cell(56, 6, safe_str(" | ".join(meta_str)), align="R", ln=False)

    pdf.set_y(y_start + 11)

    # 2. Message Block
    pdf.set_x(x0 + 2)
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", "B", 8.5)
    pdf.cell(20, 5, "Message : ", ln=False)

    pdf.set_font("Arial", size=8.5)
    _set_text(pdf, (30, 41, 59))
    pdf.multi_cell(CONTENT_W - 22, 5, msg)
    pdf.ln(1)

    # 3. Explication Block
    explanation = safe_str(analysis.get("explanation", ""))
    if explanation:
        pdf.set_x(x0 + 2)
        _set_text(pdf, COLORS["primary_dark"])
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(CONTENT_W - 4, 5, "Explication :", ln=True)

        pdf.set_x(x0 + 6)
        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        pdf.multi_cell(CONTENT_W - 8, 5, explanation)
        pdf.ln(1)

    # 4. Causes Block
    causes = analysis.get("causes", [])
    if causes:
        pdf.set_x(x0 + 2)
        _set_text(pdf, COLORS["warning"])
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(CONTENT_W - 4, 5, "Causes possibles :", ln=True)

        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        for cause in causes:
            pdf.set_x(x0 + 8)
            pdf.multi_cell(CONTENT_W - 10, 4.5, safe_str(f" - {cause}"))
        pdf.ln(1)

    # 5. Solutions Block
    solutions = analysis.get("solutions", [])
    if solutions:
        pdf.set_x(x0 + 2)
        _set_text(pdf, COLORS["success"])
        pdf.set_font("Arial", "B", 8.5)
        pdf.cell(CONTENT_W - 4, 5, "Solutions recommandées :", ln=True)

        _set_text(pdf, COLORS["dark"])
        pdf.set_font("Arial", size=8.5)
        for sol in solutions:
            pdf.set_x(x0 + 8)
            pdf.multi_cell(CONTENT_W - 10, 4.5, safe_str(f" - {sol}"))
        pdf.ln(1)

    # Separator line between error cards
    pdf.set_draw_color(*COLORS["border"])
    pdf.set_line_width(0.2)
    pdf.line(MARGIN, pdf.get_y() + 2, PAGE_W - MARGIN, pdf.get_y() + 2)
    pdf.ln(6)


# ── Public Export Function ────────────────────────────────────────────────────

def build_analysis_pdf(item: dict) -> io.BytesIO:
    data = item.get("data") or {}

    pdf = ProfessionalPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # 1. Header Banner
    _write_header_block(pdf, item, data)

    # 2. KPI Summary Cards
    _write_kpi_summary(pdf, data)

    # 3. Main Section Title
    _set_text(pdf, COLORS["dark"])
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Détails des Erreurs Analysées", ln=True)

    _set_draw(pdf, COLORS["primary"])
    pdf.set_line_width(0.6)
    pdf.line(MARGIN, pdf.get_y(), MARGIN + 45, pdf.get_y())
    pdf.ln(6)

    # 4. Error Cards
    analyzed_items = data.get("analyzed", [])
    for ai in analyzed_items:
        _write_error_section(pdf, ai)

    # Return BytesIO stream
    bio = io.BytesIO()
    bio.write(pdf.output(dest="S").encode("latin-1"))
    bio.seek(0)
    return bio
