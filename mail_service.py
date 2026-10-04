import smtplib
import ssl
import logging
import io
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import markdown
    from xhtml2pdf import pisa
    PDF_LIBS_AVAILABLE = True
except ImportError:
    PDF_LIBS_AVAILABLE = False

from config import config

logger = logging.getLogger(__name__)

def is_smtp_configured() -> bool:
    """Returns True if minimum SMTP settings are provided in configuration."""
    return bool(config.SMTP_HOST and config.SMTP_USERNAME and config.SMTP_PASSWORD)


def convert_markdown_to_pdf(markdown_text: str, title: Optional[str] = None) -> bytes:
    """
    Converts the markdown evaluation dossier into a publication-ready PDF document
    with full Polish diacritics support, clean typography, tables, and official header/footer.
    """
    if not markdown_text or not PDF_LIBS_AVAILABLE:
        logger.warning("PDF libraries not available or empty markdown text.")
        return b""

    try:
        # 1. Clean emojis and terminal artifacts for official PDF typography
        clean_md = re.sub(r'[\U00010000-\U0010ffff]', '', markdown_text)
        clean_md = re.sub(r'[⚖️⚙️]', '', clean_md)
        clean_md = clean_md.replace('> [!NOTE]', '> **Informacja o naborze**:')
        clean_md = clean_md.replace('> [!TIP]', '> **Rekomendacja ekspercka**:')
        clean_md = clean_md.replace('> [!IMPORTANT]', '> **Ważne wytyczne**:')
        clean_md = clean_md.replace('[ ]', '&#9633;')  # Clean checkbox symbol

        # 2. Convert markdown to HTML
        html_body = markdown.markdown(
            clean_md,
            extensions=['tables', 'fenced_code', 'nl2br']
        )

        # 3. Locate DejaVu font files for full Polish UTF-8 diacritics
        base_dir = os.path.dirname(__file__)
        possible_regular = [
            "/app/fonts/DejaVuSans.ttf",
            os.path.join(base_dir, "fonts", "DejaVuSans.ttf"),
            "/home/tobi303x/Code/HackYeah2026/fonts/DejaVuSans.ttf"
        ]
        font_regular = next((p for p in possible_regular if os.path.exists(p)), "")

        possible_bold = [
            "/app/fonts/DejaVuSans-Bold.ttf",
            os.path.join(base_dir, "fonts", "DejaVuSans-Bold.ttf"),
            "/home/tobi303x/Code/HackYeah2026/fonts/DejaVuSans-Bold.ttf"
        ]
        font_bold = next((p for p in possible_bold if os.path.exists(p)), font_regular)

        font_css = ""
        if font_regular:
            font_css = f"""
            @font-face {{
                font-family: 'DejaVu';
                src: url('{font_regular}');
            }}
            """
            if font_bold and font_bold != font_regular:
                font_css += f"""
                @font-face {{
                    font-family: 'DejaVu';
                    font-weight: bold;
                    src: url('{font_bold}');
                }}
                """
            font_family = "'DejaVu', Helvetica, Arial, sans-serif"
        else:
            font_family = "Helvetica, Arial, sans-serif"

        # 4. Construct complete styled HTML for PDF engine
        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: a4 portrait;
    margin: 1.6cm 1.5cm 1.6cm 1.5cm;
    @top-center {{
        content: "Regionalny Ośrodek Polityki Społecznej w Krakowie · Autonomiczny Doradca Grantowy";
        font-family: {font_family};
        font-size: 7.5pt;
        color: #94a3b8;
        border-bottom: 0.5pt solid #e2e8f0;
        padding-bottom: 3pt;
    }}
    @bottom-left {{
        content: "Dossier Aplikacyjne ROPS · Wygenerowano automatycznie";
        font-family: {font_family};
        font-size: 7.5pt;
        color: #94a3b8;
    }}
    @bottom-right {{
        content: "Strona " counter(page) " z " counter(pages);
        font-family: {font_family};
        font-size: 7.5pt;
        color: #64748b;
    }}
}}
{font_css}
body {{
    font-family: {font_family};
    font-size: 9pt;
    line-height: 1.45;
    color: #1e293b;
}}
h1 {{
    font-size: 15pt;
    font-weight: bold;
    color: #0f172a;
    border-bottom: 2pt solid #2563eb;
    padding-bottom: 4pt;
    margin-top: 0;
    margin-bottom: 10pt;
}}
h2 {{
    font-size: 11.5pt;
    font-weight: bold;
    color: #1e3a8a;
    margin-top: 14pt;
    margin-bottom: 6pt;
    border-bottom: 0.5pt solid #cbd5e1;
    padding-bottom: 2pt;
}}
h3 {{
    font-size: 10pt;
    font-weight: bold;
    color: #334155;
    margin-top: 10pt;
    margin-bottom: 4pt;
}}
p {{
    margin-top: 0;
    margin-bottom: 6pt;
}}
blockquote {{
    border-left: 2.5pt solid #2563eb;
    background-color: #f8fafc;
    padding: 6pt 10pt;
    margin: 8pt 0;
    color: #334155;
    font-size: 8.5pt;
}}
table {{
    width: 100%;
    margin: 10pt 0;
}}
th, td {{
    border: 0.5pt solid #cbd5e1;
    padding: 4.5pt 6pt;
    text-align: left;
    font-size: 8pt;
    line-height: 1.35;
}}
th {{
    background-color: #f1f5f9;
    font-weight: bold;
    color: #0f172a;
}}
hr {{
    border: 0;
    border-top: 0.5pt solid #e2e8f0;
    margin: 10pt 0;
}}
code {{
    font-family: {font_family};
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 1pt 3pt;
    font-size: 8pt;
}}
ul, ol {{
    margin-top: 2pt;
    margin-bottom: 6pt;
    padding-left: 14pt;
}}
li {{
    margin-bottom: 2pt;
}}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

        pdf_buf = io.BytesIO()
        pisa_status = pisa.CreatePDF(full_html, dest=pdf_buf, encoding='utf-8')
        if pisa_status.err:
            logger.warning(f"xhtml2pdf reported {pisa_status.err} non-fatal rendering notices.")
        return pdf_buf.getvalue()

    except Exception as e:
        logger.error(f"Error generating PDF from markdown: {e}", exc_info=True)
        return b""


def send_dossier_email(
    recipient_email: str,
    subject: Optional[str] = None,
    markdown_report: str = "",
    query: Optional[str] = None,
    powiat: Optional[str] = None,
    applicant_type: Optional[str] = None,
    scorecard: Optional[Dict[str, Any]] = None,
    recipient_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Sends the generated ROPS evaluation dossier and grant strategy to the specified email address.
    Attaches the complete dossier as a publication-ready .pdf document and includes a rich HTML executive summary.
    If SMTP is not yet configured, gracefully simulates delivery (dry-run).
    """
    if not recipient_email or "@" not in recipient_email:
        return {
            "status": "error",
            "message": "Podano nieprawidłowy adres e-mail odbiorcy."
        }

    date_str = datetime.now().strftime("%d.%m.%Y, %H:%M")
    default_subject = f"📋 Dossier Grantowe ROPS: {query[:45] + '...' if query else 'Diagnoza Społeczna'}"
    email_subject = subject or default_subject

    # Check if SMTP credentials exist
    if not is_smtp_configured():
        logger.warning(
            f"[SMTP DRY-RUN] SMTP not fully configured. Simulating email to {recipient_email}. "
            f"Set SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD to send real emails."
        )
        return {
            "status": "success",
            "mock": True,
            "recipient": recipient_email,
            "message": f"Wiadomość testowa przygotowana dla {recipient_email}. Skonfiguruj dane SMTP w .env aby wysyłać prawdziwe e-maile."
        }

    try:
        from_email = config.SMTP_FROM_EMAIL or config.SMTP_USERNAME
        from_header = f"{config.SMTP_FROM_NAME} <{from_email}>"

        msg = MIMEMultipart("mixed")
        msg["From"] = from_header
        msg["To"] = recipient_email
        msg["Subject"] = email_subject

        # Build clean, modern HTML body
        powiat_label = f"Powiat {powiat}" if powiat else "Województwo Małopolskie"
        applicant_label = applicant_type or "JST / NGO / CUS"

        # Calculate summary highlight from scorecard if available
        score_html = ""
        if scorecard:
            wtd = scorecard.get("total_wtd") or scorecard.get("diagnostic_subtotal", 85)
            grade = scorecard.get("grade", "Klasa A")
            rec = scorecard.get("recommendation", "Rekomendowane złożenie wniosku")
            score_html = f"""
            <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px 18px; margin: 18px 0;">
                <div style="font-size: 13px; font-weight: 600; color: #166534; text-transform: uppercase; letter-spacing: 0.5px;">Indeks Gotowości Projektowej (IGP)</div>
                <div style="font-size: 24px; font-weight: 700; color: #15803d; margin: 4px 0;">{wtd} / 100 pkt · {grade}</div>
                <div style="font-size: 13px; color: #166534;">{rec}</div>
            </div>
            """

        greeting_text = f"Dzień dobry, {recipient_name}!" if recipient_name else "Twój Raport i Strategia Wdrożenia są gotowe"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; padding: 24px; margin: 0;">
          <div style="max-width: 640px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
            
            <div style="background-color: #0f172a; color: #ffffff; padding: 24px 28px;">
              <h1 style="font-size: 20px; font-weight: 600; margin: 0 0 6px 0;">Regionalny Ośrodek Polityki Społecznej w Krakowie</h1>
              <p style="font-size: 13px; color: #94a3b8; margin: 0;">Autonomiczny Doradca Grantowy i Analityk Polityki Społecznej</p>
            </div>

            <div style="padding: 28px;">
              <h2 style="font-size: 17px; font-weight: 600; color: #0f172a; margin: 0 0 12px 0;">{greeting_text}</h2>
              <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 0 0 14px 0;">
                Dziękujemy za skorzystanie z generatora wniosków i doradcy ROPS. Poniżej znajduje się podsumowanie analizy Twojego zgłoszenia:
              </p>

              <div style="background-color: #f8fafc; border-left: 3px solid #3b82f6; padding: 12px 16px; margin: 16px 0; border-radius: 0 6px 6px 0;">
                <p style="margin: 0; font-size: 13px; color: #334155;"><strong>Zgłoszony pomysł:</strong> „{query or 'Inicjatywa społeczna'}”</p>
                <p style="margin: 6px 0 0 0; font-size: 12px; color: #64748b;"><strong>Obszar:</strong> {powiat_label} | <strong>Wnioskodawca:</strong> {applicant_label} | <strong>Data analizy:</strong> {date_str}</p>
              </div>

              {score_html}

              <p style="font-size: 14px; line-height: 1.6; color: #475569; margin: 18px 0 10px 0;">
                Kompletny dokument aplikacyjny, szczegółowy kosztorys oraz plan wdrożenia został dołączony do tej wiadomości w formacie PDF gotowym do druku i prezentacji: 
                <strong><code>dossier_aplikacyjne_rops.pdf</code></strong>.
              </p>

              <div style="margin-top: 24px; padding-top: 18px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #94a3b8;">
                Wiadomość wygenerowana automatycznie przez system HackYeah 2026 – Doradca Grantowy ROPS Kraków.
              </div>
            </div>

          </div>
        </body>
        </html>
        """

        msg_body = MIMEMultipart("alternative")
        msg_body.attach(MIMEText(markdown_report or "Brak treści raportu.", "plain", "utf-8"))
        msg_body.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(msg_body)

        # Generate and attach the complete evaluation dossier as a professional PDF document
        pdf_attached = False
        if markdown_report and PDF_LIBS_AVAILABLE:
            try:
                pdf_bytes = convert_markdown_to_pdf(markdown_report, title=query)
                if pdf_bytes:
                    attachment = MIMEBase("application", "pdf")
                    attachment.set_payload(pdf_bytes)
                    encoders.encode_base64(attachment)
                    filename = f"dossier_aplikacyjne_rops_{datetime.now().strftime('%Y%m%d')}.pdf"
                    attachment.add_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
                    msg.attach(attachment)
                    pdf_attached = True
                    logger.info(f"Attached PDF dossier ({len(pdf_bytes)} bytes) to email.")
            except Exception as e_pdf:
                logger.error(f"Failed to generate PDF attachment: {e_pdf}")

        # Fallback to UTF-8 markdown if PDF generation was unavailable
        if not pdf_attached and markdown_report:
            attachment = MIMEBase("text", "markdown", charset="utf-8")
            attachment.set_payload(markdown_report.encode("utf-8"))
            encoders.encode_base64(attachment)
            filename = f"dossier_rops_{datetime.now().strftime('%Y%m%d')}.md"
            attachment.add_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
            msg.attach(attachment)

        # Connect and send via SMTP
        server = None
        if config.SMTP_USE_SSL:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
            if config.SMTP_USE_TLS:
                context = ssl.create_default_context()
                server.starttls(context=context)

        server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
        server.sendmail(from_email, [recipient_email], msg.as_string())
        server.quit()

        logger.info(f"Successfully sent dossier email (PDF: {pdf_attached}) to {recipient_email}")
        return {
            "status": "success",
            "mock": False,
            "pdf_attached": pdf_attached,
            "recipient": recipient_email,
            "message": f"Raport w formacie PDF został pomyślnie wysłany na adres {recipient_email}."
        }

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return {
            "status": "error",
            "code": "AUTH_FAILED",
            "message": "Błąd autoryzacji serwera pocztowego. Sprawdź poprawność loginu i Hasła aplikacji."
        }
    except Exception as e:
        logger.error(f"Error sending email to {recipient_email}: {e}")
        return {
            "status": "error",
            "message": f"Nie udało się wysłać wiadomości: {str(e)}"
        }
