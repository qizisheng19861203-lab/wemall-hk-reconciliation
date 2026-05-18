import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from app.config import settings
import logging
import os
import base64

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static")


def _get_image_base64(filename: str, mime: str = "image/png") -> str:
    """读取图片并转为 base64 data URI"""
    path = os.path.join(STATIC_DIR, filename)
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{data}"
    except Exception:
        return ""


def render_invoice_html(settlement) -> str:
    """渲染 invoice.html 模板为 HTML 字符串（不转PDF，用于邮件正文）"""
    from jinja2 import Environment, FileSystemLoader
    from datetime import datetime
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("invoice.html")
    return template.render(
        settlement=settlement,
        now=datetime.now(),
        stamp_src=_get_image_base64("seal.png", "image/png"),
        logo_src=_get_image_base64("logo.jpg", "image/jpeg"),
    )


def send_settlement_email(
    to_emails: list,
    settlement,
    invoice_pdf: bytes,
    detail_pdf: bytes = None,
) -> dict:
    """发送结算账单邮件（HTML正文含账单预览，附件含invoice PDF，可选附明细PDF）"""
    if not to_emails:
        return {"sent": 0, "skipped": 0, "error": "no recipients"}
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return {"sent": 0, "skipped": len(to_emails), "error": "SMTP未配置"}

    subject = (
        f"香港蔚蓝健康对账单 "
        f"{settlement.period_start.year}年{settlement.period_start.month}月{settlement.period_start.day}号"
        f"-{settlement.period_end.month}月{settlement.period_end.day}号"
    )

    msg = MIMEMultipart('mixed')
    msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg['To'] = ', '.join(to_emails)
    msg['Subject'] = subject

    # Render invoice HTML for email body
    try:
        invoice_html = render_invoice_html(settlement)
    except Exception as e:
        logger.warning(f"Failed to render invoice HTML for email: {e}")
        invoice_html = ""

    period_start_str = settlement.period_start.strftime('%Y年%m月%d日')
    period_end_str = settlement.period_end.strftime('%Y年%m月%d日')

    html_body = f"""<html><body>
<p>您好，请查收香港蔚蓝健康本期对账单。</p>
<p style="color:#666;font-size:13px;">账期：{period_start_str} — {period_end_str}　|　Invoice 编号：{settlement.invoice_number}</p>
<hr>
{invoice_html}
<hr>
<p>如有问题请联系我们。</p>
<p style="color:#999;font-size:12px;">HONGKONG BLUE HEALTH MANAGEMENT LIMITED 香港蔚蓝健康管理有限公司</p>
</body></html>"""

    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    # Attach Invoice PDF
    _attach_pdf(msg, invoice_pdf, f"Invoice-{settlement.invoice_number}.pdf")
    # Optionally attach detail PDF
    if detail_pdf:
        _attach_pdf(msg, detail_pdf, f"Detail-{settlement.invoice_number}.pdf")

    try:
        ctx = ssl.create_default_context()
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=ctx, timeout=30) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, to_emails, msg.as_bytes())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, to_emails, msg.as_bytes())
        logger.info(f"Email sent to {to_emails} for {settlement.invoice_number}")
        return {"sent": len(to_emails), "skipped": 0}
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return {"sent": 0, "skipped": len(to_emails), "error": str(e)}


def _attach_pdf(msg, pdf_bytes: bytes, filename: str):
    part = MIMEBase('application', 'pdf')
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    # ASCII filename in header, actual name via filename* parameter
    safe_name = filename.encode('ascii', errors='replace').decode('ascii')
    part.add_header('Content-Disposition', 'attachment', filename=safe_name)
    msg.attach(part)
