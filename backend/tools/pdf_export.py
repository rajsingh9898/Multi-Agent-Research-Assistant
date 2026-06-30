"""PDF Export Tool for the Multi-Agent Research Assistant.

This module generates professional reports using ReportLab and uploads them to Firebase.
"""

from __future__ import annotations

import os
import re
import logging
from io import BytesIO
from datetime import datetime
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


def register_fonts() -> bool:
    """Registers Unicode DejaVu Sans font for multilingual report generation.

    Returns:
        True if fonts registered successfully, False if fallback Helvetica is used.
    """
    font_dir = os.path.join(
        os.path.dirname(__file__),
        "..", "assets", "fonts"
    )

    regular_path = os.path.join(font_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(font_dir, "DejaVuSans-Bold.ttf")

    if os.path.exists(regular_path) and os.path.exists(bold_path):
        try:
            pdfmetrics.registerFont(TTFont("Unicode", regular_path))
            pdfmetrics.registerFont(TTFont("Unicode-Bold", bold_path))
            logger.info("DejaVu Sans Unicode fonts successfully registered.")
            return True
        except Exception as exc:
            logger.warning("Failed to register Unicode fonts: %s. Falling back to Helvetica.", exc)
            return False
    else:
        logger.warning("Unicode DejaVuSans fonts not found at assets path. Falling back to Helvetica.")
        return False


def get_pdf_styles(unicode_available: bool) -> Dict[str, ParagraphStyle]:
    """Creates the paragraph styles sheet based on unicode font availability.

    Args:
        unicode_available: Flag indicating whether registered fonts are present.

    Returns:
        A dictionary of styled layout descriptors.
    """
    base_font = "Unicode" if unicode_available else "Helvetica"
    bold_font = "Unicode-Bold" if unicode_available else "Helvetica-Bold"

    # Use a dummy style sheet just to initialize defaults
    styles = getSampleStyleSheet()

    custom_styles = {
        "title": ParagraphStyle(
            name="CustomTitle",
            fontName=bold_font,
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1a1a2e"),
            spaceAfter=20
        ),
        "subtitle": ParagraphStyle(
            name="CustomSubtitle",
            fontName=base_font,
            fontSize=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#666666"),
            spaceAfter=10
        ),
        "section_heading": ParagraphStyle(
            name="CustomSectionHeading",
            fontName=bold_font,
            fontSize=14,
            textColor=colors.HexColor("#16213e"),
            spaceBefore=15,
            spaceAfter=8,
            keepWithNext=True
        ),
        "body": ParagraphStyle(
            name="CustomBody",
            fontName=base_font,
            fontSize=10,
            leading=15,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor("#2d2d2d"),
            spaceAfter=10
        ),
        "finding": ParagraphStyle(
            name="CustomFinding",
            fontName=base_font,
            fontSize=10,
            leading=14,
            leftIndent=15,
            spaceAfter=6,
            textColor=colors.HexColor("#2d2d2d")
        ),
        "citation": ParagraphStyle(
            name="CustomCitation",
            fontName=base_font,
            fontSize=8,
            leftIndent=15,
            textColor=colors.HexColor("#0f3460"),
            spaceAfter=8
        ),
        "source_item": ParagraphStyle(
            name="CustomSourceItem",
            fontName=base_font,
            fontSize=8.5,
            leading=12,
            spaceAfter=6,
            textColor=colors.HexColor("#2d2d2d")
        ),
        "confidence_badge": ParagraphStyle(
            name="CustomConfidenceBadge",
            fontName=bold_font,
            fontSize=13,
            alignment=TA_CENTER,
            spaceAfter=15
        )
    }

    return custom_styles


def clean_text_for_pdf(text: str) -> str:
    """Escapes XML entities, parses citation tags, and trims whitespace.

    Args:
        text: Raw text content to process.

    Returns:
        ReportLab-safe formatted text block.
    """
    if text is None:
        return ""

    # Ensure type is string
    text = str(text)

    # XML escapes (ReportLab paragraph rendering relies on HTML/XML tags)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")

    # Format source citation brackets in italics
    pattern = r'\[Source:\s*([^\]]+)\]'
    text = re.sub(pattern, r'<i>[Source: \1]</i>', text)

    # Trim excessive whitespaces
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def build_title_page(
    report: Dict[str, Any],
    topic: str,
    styles: Dict[str, ParagraphStyle]
) -> List[Any]:
    """Generates the elements list representing the report title page.

    Args:
        report: Final report payload.
        topic: The original research topic.
        styles: Styles mapping sheet.

    Returns:
        List of layout flowables.
    """
    elements = []

    # Large spacer to push the title down
    elements.append(Spacer(1, 1.8 * inch))

    # Title
    title_text = clean_text_for_pdf(report.get("title", topic))
    elements.append(Paragraph(title_text, styles["title"]))

    elements.append(Spacer(1, 0.2 * inch))

    # Separator Line
    elements.append(HRFlowable(
        width="60%", thickness=1,
        color=colors.HexColor("#0f3460"),
        spaceAfter=20, hAlign='CENTER'
    ))

    # Formatted generated date
    raw_date = report.get("generated_at", "")
    formatted_date = raw_date
    if raw_date:
        try:
            # Parse ISO date (handles Z and offsets)
            clean_date = re.sub(r'(\.\d+)?Z$', '', raw_date)
            clean_date = clean_date.split("+")[0]
            dt = datetime.fromisoformat(clean_date)
            formatted_date = dt.strftime("%B %d, %Y")
        except Exception:
            pass

    elements.append(Paragraph(f"Generated on {formatted_date}", styles["subtitle"]))
    elements.append(Spacer(1, 0.15 * inch))

    # Confidence Badge
    confidence = report.get("confidence_score", 0)
    label = report.get("confidence_label", "Unknown")
    emoji = report.get("confidence_emoji", "")

    if confidence >= 80:
        color = colors.HexColor("#2e7d32")  # Green
    elif confidence >= 60:
        color = colors.HexColor("#f57f17")  # Yellow-orange
    elif confidence >= 40:
        color = colors.HexColor("#e65100")  # Orange
    else:
        color = colors.HexColor("#d50000")  # Red

    confidence_style = ParagraphStyle(
        name="ConfBadge",
        parent=styles["confidence_badge"],
        textColor=color
    )

    badge_text = f"Confidence Score: {confidence}% ({label}) {emoji}"
    elements.append(Paragraph(badge_text, confidence_style))
    elements.append(Spacer(1, 0.4 * inch))

    # Report Stats
    total_sources = report.get("total_sources_used", 0)
    word_count = report.get("word_count", 0)
    info_text = f"Based on {total_sources} sources | {word_count} words"
    elements.append(Paragraph(info_text, styles["subtitle"]))

    # Spacer pushing footer down
    elements.append(Spacer(1, 1.8 * inch))

    # Branding footer
    elements.append(Paragraph("Generated by Multi-Agent Research Assistant", styles["subtitle"]))

    # Break page to move to body
    elements.append(PageBreak())

    return elements


def build_section(
    heading: str,
    content: str,
    styles: Dict[str, ParagraphStyle]
) -> List[Any]:
    """Helper compiling a structured heading + divider + body section.

    Args:
        heading: The heading title.
        content: The text content under the heading.
        styles: Styles mapping sheet.

    Returns:
        List of flowables representing the section.
    """
    if not content or not content.strip():
        return []

    elements = []

    elements.append(Paragraph(heading, styles["section_heading"]))
    elements.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc"),
        spaceAfter=10
    ))

    cleaned_content = clean_text_for_pdf(content)
    elements.append(Paragraph(cleaned_content, styles["body"]))
    elements.append(Spacer(1, 0.15 * inch))

    return elements


def build_key_findings_section(
    findings: List[Dict[str, Any]],
    styles: Dict[str, ParagraphStyle]
) -> List[Any]:
    """Compiles the key findings list elements.

    Args:
        findings: List of finding dictionaries.
        styles: Styles mapping sheet.

    Returns:
        List of flowables representing key findings.
    """
    if not findings:
        return []

    elements = []

    elements.append(Paragraph("Key Findings", styles["section_heading"]))
    elements.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc"),
        spaceAfter=10
    ))

    for i, finding in enumerate(findings, 1):
        point = clean_text_for_pdf(finding.get("point", ""))
        citation = finding.get("citation", "")
        status = finding.get("status", "verified")

        status_icon = "✓" if status == "verified" else "~"
        status_label = "Verified" if status == "verified" else "Uncertain"

        finding_text = f"<b>{i}.</b> {point} <b>[{status_icon} {status_label}]</b>"
        elements.append(Paragraph(finding_text, styles["finding"]))

        if citation:
            citation_text = f"Source: {clean_text_for_pdf(citation)}"
            elements.append(Paragraph(citation_text, styles["citation"]))

    elements.append(Spacer(1, 0.15 * inch))
    return elements


def build_sources_section(
    sources: List[Dict[str, Any]],
    styles: Dict[str, ParagraphStyle]
) -> List[Any]:
    """Compiles the source credentials bibliography page.

    Args:
        sources: List of source dictionaries.
        styles: Styles mapping sheet.

    Returns:
        List of flowables representing bibliography.
    """
    elements = []

    # Sources always starts on a fresh page
    elements.append(PageBreak())

    elements.append(Paragraph("Sources", styles["section_heading"]))
    elements.append(HRFlowable(
        width="100%", thickness=0.5,
        color=colors.HexColor("#cccccc"),
        spaceAfter=10
    ))

    if not sources:
        elements.append(Paragraph("No sources available.", styles["body"]))
        return elements

    for i, source in enumerate(sources, 1):
        url = source.get("url") or source.get("source_url") or ""
        title = clean_text_for_pdf(source.get("title") or "Untitled Source")
        cred = (source.get("credibility") or source.get("rating") or "unknown").title()

        source_text = (
            f"<b>{i}.</b> {title}<br/>"
            f"<font size=7.5 color='#0f3460'>{url}</font> "
            f"<font size=7.5>[{cred}]</font>"
        )
        elements.append(Paragraph(source_text, styles["source_item"]))

    return elements


def add_page_number_and_footer(
    canvas_obj: canvas.Canvas,
    doc: SimpleDocTemplate
) -> None:
    """Callback function executed on page drawing to paint header/footer elements.

    Args:
        canvas_obj: Native reportlab canvas graphics context.
        doc: SimpleDocTemplate layout context.
    """
    canvas_obj.saveState()

    page_num = canvas_obj.getPageNumber()

    # Draw bottom horizontal separator line
    canvas_obj.setStrokeColor(colors.HexColor("#dddddd"))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(
        0.85 * inch, 0.65 * inch,
        A4[0] - 0.85 * inch, 0.65 * inch
    )

    # Draw footer branding (left)
    canvas_obj.setFont("Helvetica", 7.5)
    canvas_obj.setFillColor(colors.HexColor("#999999"))
    canvas_obj.drawString(
        0.85 * inch, 0.45 * inch,
        "Generated by Multi-Agent Research Assistant"
    )

    # Draw footer page count (right)
    canvas_obj.drawRightString(
        A4[0] - 0.85 * inch, 0.45 * inch,
        f"Page {page_num}"
    )

    canvas_obj.restoreState()


def generate_pdf(
    report: Dict[str, Any],
    topic: str
) -> bytes:
    """Generates a complete research report PDF in-memory.

    Args:
        report: Final report document state dictionary.
        topic: The original research topic query.

    Returns:
        Binary bytes representing the generated PDF.
    """
    try:
        unicode_ok = register_fonts()
        styles = get_pdf_styles(unicode_ok)

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=0.85 * inch,
            bottomMargin=0.85 * inch,
            leftMargin=0.85 * inch,
            rightMargin=0.85 * inch,
            title=report.get("title", topic),
            author="Multi-Agent Research Assistant"
        )

        elements = []

        # 1. Build Title Page
        elements.extend(build_title_page(report, topic, styles))

        # 2. Executive Summary Section
        elements.extend(build_section("Executive Summary", report.get("executive_summary", ""), styles))

        # 3. Key Findings Section
        elements.extend(build_key_findings_section(report.get("key_findings", []), styles))

        # 4. Detailed Analysis Section
        elements.extend(build_section("Detailed Analysis", report.get("detailed_analysis", ""), styles))

        # 5. Limitations Section
        elements.extend(build_section("Limitations & Uncertainties", report.get("limitations", ""), styles))

        # 6. Conclusion Section
        elements.extend(build_section("Conclusion", report.get("conclusion", ""), styles))

        # 7. Sources Bibliography Section
        elements.extend(build_sources_section(report.get("sources", []), styles))

        # Build doc with page numbers
        doc.build(
            elements,
            onFirstPage=add_page_number_and_footer,
            onLaterPages=add_page_number_and_footer
        )

        pdf_bytes = buffer.getvalue()
        buffer.close()

        logger.info(f"Report PDF successfully compiled. Size: {len(pdf_bytes)} bytes.")
        return pdf_bytes

    except Exception as exc:
        logger.error("Failed to generate report PDF: %s", exc, exc_info=True)
        raise


def upload_to_firebase(
    pdf_bytes: bytes,
    report_id: str
) -> str:
    """Uploads PDF bytes to Firebase Storage and returns its public URL.

    Args:
        pdf_bytes: Binary contents of the PDF.
        report_id: Document ID.

    Returns:
        Publicly readable Firebase download URL.
    """
    try:
        from utils.firebase_config import get_storage

        bucket = get_storage()
        blob_path = f"reports/{report_id}.pdf"
        blob = bucket.blob(blob_path)

        blob.upload_from_string(
            pdf_bytes,
            content_type="application/pdf"
        )

        # Make the uploaded PDF publicly readable
        blob.make_public()
        public_url = blob.public_url

        logger.info(f"Uploaded report {report_id}.pdf to Firebase. URL: {public_url}")
        return public_url

    except Exception as exc:
        logger.error("Firebase Storage upload failed for report %s: %s", report_id, exc, exc_info=True)
        raise


def generate_and_upload_pdf(
    report: Dict[str, Any],
    topic: str,
    report_id: str
) -> Dict[str, Any]:
    """Combines generation and Firebase upload workflows.

    Args:
        report: Final report payload.
        topic: Research query.
        report_id: Active report id.

    Returns:
        Status mapping detailing successes or failures.
    """
    try:
        pdf_bytes = generate_pdf(report, topic)
        pdf_url = upload_to_firebase(pdf_bytes, report_id)

        return {
            "success": True,
            "pdf_url": pdf_url,
            "size_bytes": len(pdf_bytes)
        }

    except Exception as exc:
        logger.error("Failed to generate and upload PDF for report %s: %s", report_id, exc, exc_info=True)
        return {
            "success": False,
            "error": str(exc)
        }
