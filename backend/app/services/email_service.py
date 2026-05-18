import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def send_settlement_email(
    to_emails: list,
    settlement,
    invoice_pdf: bytes,
    detail_pdf: bytes = None,
) -> dict:
    """发送结算账单邮件（附件含invoice PDF，可选附明细PDF）"""
    if not to_emails:
        return {"sent": 0, "skipped": 0, "error": "no recipients"}
    if not settings.SMTP_HOST or not settings.SMTP_USER:
        return {"sent": 0, "skipped": len(to_emails), "error": "SMTP未配置"}

    period_start = settlement.period_start.strftime('%Y年%m月%d日')
    period_end = settlement.period_end.strftime('%Y年%m月%d日')
    subject = f"结算账单 {settlement.invoice_number} | {period_start} ~ {period_end}"

    msg = MIMEMultipart()
    msg['From'] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_USER}>"
    msg['To'] = ', '.join(to_emails)
    msg['Subject'] = subject

    body = f"""您好，

附件为本期结算账单，请查收。

账期：{period_start} — {period_end}
Invoice 编号：{settlement.invoice_number}
净供货额：RMB ¥{float(settlement.net_supply_rmb):.2f}
应付港币：HK${float(settlement.payment_amount_hkd):.2f}
订单数：{settlement.order_count}

如有疑问请回复此邮件。

HONGKONG BLUE HEALTH MANAGEMENT LIMITED
香港蔚蓝健康管理有限公司
"""
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

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
