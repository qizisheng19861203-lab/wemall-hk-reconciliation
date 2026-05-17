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


def _get_image_base64(filename: str, mime: str = "image/png") -> str:
    """读取图片并转为 base64 data URI"""
    path = os.path.join(STATIC_DIR, filename)
    try:
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{data}"
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
        "stamp_src": _get_image_base64("seal.png", "image/png"),
        "logo_src": _get_image_base64("logo.jpg", "image/jpeg"),
    })
    return _html_to_pdf(html)


def generate_detail_pdf(settlement: Settlement, orders: List[Order]) -> bytes:
    html = _render_html("detail.html", {
        "settlement": settlement,
        "orders": orders,
        "now": datetime.now(),
        "stamp_src": _get_image_base64("seal.png", "image/png"),
    })
    return _html_to_pdf(html)
