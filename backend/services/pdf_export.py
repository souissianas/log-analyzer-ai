import io
import json

from fpdf import FPDF
from anyascii import anyascii


def safe_str(s: str) -> str:
    """
    Sanitizes strings to prevent UnicodeEncodeError in FPDF (which only supports Latin-1 by default).
    Converts smart quotes, em-dashes, emojis, and unrepresentable characters into safe CP1252/Latin-1 equivalents.
    Uses anyascii to transliterate characters that are not representable in Latin-1.
    """
    if not isinstance(s, str):
        return str(s or "")
    
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "—": "-",
        "–": "-",
        "œ": "oe",
        "Œ": "OE",
        "æ": "ae",
        "Æ": "AE",
        "…": "...",
        "•": "*",
        "🚨": "[ALERT]",
        "📁": "[FILE]",
        "💥": "[CRITICAL]",
        "🏷️": "[TAG]",
        "⚠️": "[WARN]",
        "✅": "[OK]",
        "❌": "[ERROR]"
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


def build_analysis_pdf(item: dict) -> io.BytesIO:
    data = item.get("data") or {}
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, safe_str(f"Analyse de {data.get('filename', 'fichier')}"), ln=True)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 8, safe_str(f"ID: {item['id']} - Date: {item['created_at']}"), ln=True)
    pdf.ln(4)

    for analysis_item in data.get("analyzed", []):
        category = safe_str(analysis_item.get("category"))
        pdf.set_font("Arial", "B", 11)
        title = f"Erreur #{analysis_item.get('index')} - {analysis_item.get('level')}"
        if category and category != "unknown":
            title += f" [{category}]"
        pdf.cell(0, 8, safe_str(title), ln=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 6, safe_str(f"Message: {analysis_item.get('message')}"))
        
        analysis = analysis_item.get("analysis")
        if not isinstance(analysis, dict):
            analysis = {}

        explanation = analysis.get("explanation", "")
        pdf.multi_cell(
            0,
            6,
            safe_str(f"Explication: {explanation}"),
        )
        
        causes = analysis.get("causes", [])
        if causes:
            pdf.multi_cell(0, 6, safe_str("Causes:"))
            for cause in causes:
                pdf.multi_cell(0, 6, safe_str(f" - {cause}"))
                
        solutions = analysis.get("solutions", [])
        if solutions:
            pdf.multi_cell(0, 6, safe_str("Solutions:"))
            for solution in solutions:
                pdf.multi_cell(0, 6, safe_str(f" - {solution}"))
        pdf.ln(3)

    bio = io.BytesIO()
    bio.write(pdf.output(dest="S").encode("latin-1"))
    bio.seek(0)
    return bio