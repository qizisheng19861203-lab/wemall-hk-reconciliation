from jinja2 import Environment, FileSystemLoader
import os
import subprocess
from app.models.settlement import Settlement
from app.models.order import Order
from typing import List
from datetime import datetime

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


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
    })
    return _html_to_pdf(html)


def generate_detail_pdf(settlement: Settlement, orders: List[Order]) -> bytes:
    html = _render_html("detail.html", {
        "settlement": settlement,
        "orders": orders,
        "now": datetime.now(),
    })
    return _html_to_pdf(html)
