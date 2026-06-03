"""PDF export helpers using ReportLab
- Expose `export_pdf(report_md, output_path)` function to create PDFs.
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def export_pdf(markdown_text: str, output_path: str):
    """Simple placeholder that writes markdown as plain text in a PDF.
    Replace with proper formatting and multi-language support.
    """
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    text = c.beginText(40, height - 40)
    for line in markdown_text.splitlines():
        text.textLine(line[:120])
    c.drawText(text)
    c.save()
