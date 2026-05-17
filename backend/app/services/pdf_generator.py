from jinja2 import Environment, FileSystemLoader
import os
import base64
from app.models.settlement import Settlement
from app.models.order import Order
from typing import List
from datetime import datetime

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def _get_stamp_base64() -> str:
    """读取公章图片并转为 base64 data URI"""
    seal_path = os.path.join(STATIC_DIR, "seal.png")
    try:
        with open(seal_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:image/png;base64,{data}"
    except Exception:
        return ""


def _render_html(template_name: str, context: dict) -> str:
    template = env.get_template(template_name)
    return template.render(**context)


def _html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


def generate_invoice_pdf(settlement: Settlement) -> bytes:
    html = _render_html("invoice.html", {
        "settlement": settlement,
        "now": datetime.now(),
        "stamp_src": _get_stamp_base64(),
    })
    return _html_to_pdf(html)


def generate_detail_pdf(settlement: Settlement, orders: List[Order]) -> bytes:
    html = _render_html("detail.html", {
        "settlement": settlement,
        "orders": orders,
        "now": datetime.now(),
        "stamp_src": _get_stamp_base64(),
    })
    return _html_to_pdf(html)
