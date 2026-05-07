"""
FNID PDF Export

Generates PDF documents for CR forms, case summaries, and reports
using xhtml2pdf. Falls back to HTML-only print view if unavailable.
"""

import io
from datetime import datetime


def render_pdf(html_content):
    """Convert HTML content to a PDF byte buffer.

    Args:
        html_content: Rendered HTML string

    Returns:
        io.BytesIO buffer with PDF content, or None if xhtml2pdf unavailable
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        return None

    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=buffer)

    if pisa_status.err:
        return None

    buffer.seek(0)
    return buffer


def pdf_header_html(title, case_id=None, form_type=None):
    """Generate standard JCF header HTML for PDF documents."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    case_line = f"<p><strong>Case Ref:</strong> {case_id}</p>" if case_id else ""
    form_line = f"<p><strong>Form:</strong> {form_type}</p>" if form_type else ""

    return f"""
    <div style="text-align: center; margin-bottom: 20px; border-bottom: 2px solid #1F3864; padding-bottom: 10px;">
        <h2 style="color: #1F3864; margin: 0;">Jamaica Constabulary Force</h2>
        <h3 style="color: #1F3864; margin: 5px 0;">Firearms & Narcotics Investigation Division — Area 3</h3>
        <h4 style="margin: 5px 0;">{title}</h4>
        {case_line}
        {form_line}
        <p style="font-size: 10px; color: #666;">Generated: {now} | RESTRICTED — Official Use Only</p>
    </div>
    """


def pdf_base_css():
    """Return base CSS for PDF rendering."""
    return """
    <style>
        body { font-family: 'Helvetica', 'Arial', sans-serif; font-size: 11px; color: #333; }
        h1, h2, h3, h4 { color: #1F3864; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th { background-color: #1F3864; color: white; padding: 6px 8px; text-align: left; font-size: 10px; }
        td { padding: 5px 8px; border-bottom: 1px solid #ddd; font-size: 10px; }
        .section { margin: 15px 0; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        .section-title { font-weight: bold; color: #1F3864; border-bottom: 1px solid #1F3864;
                         padding-bottom: 4px; margin-bottom: 8px; }
        .field-label { font-weight: bold; color: #555; }
        .field-value { margin-left: 10px; }
        .footer { text-align: center; font-size: 9px; color: #999; margin-top: 20px;
                  border-top: 1px solid #ddd; padding-top: 5px; }
        @page { margin: 1.5cm; }
    </style>
    """
