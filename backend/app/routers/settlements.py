from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.database import get_db
from app.models.settlement import Settlement, SettlementStatus
from app.models.order import Order
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.core.deps import get_current_user, require_admin
from app.schemas.settlement import (
    SettlementCreate, SettlementConfirm, SettlementResponse,
    ExchangeRateResponse, ExchangeRateCreate,
)
from app.services.pdf_generator import generate_invoice_pdf, generate_detail_pdf
from app.services.sms_service import send_settlement_notification
import random, string
from datetime import date

router = APIRouter(prefix="/settlements", tags=["结算管理"])
rates_router = APIRouter(prefix="/exchange-rates", tags=["汇率管理"])


def _active_store_id(db: Session) -> Optional[int]:
    from app.models.wemall_store_config import WemallStoreConfig
    store = db.query(WemallStoreConfig).filter(WemallStoreConfig.is_active == True).first()
    return store.id if store else None


def _make_invoice_number():
    now = datetime.now()
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"INV{now.strftime('%Y%m%d')}{suffix}"


@router.get("", response_model=List[SettlementResponse])
def list_settlements(
    status: Optional[SettlementStatus] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    sid = _active_store_id(db)
    q = db.query(Settlement)
    if sid is not None:
        q = q.filter(Settlement.wemall_store_id == sid)
    if status:
        q = q.filter(Settlement.status == status)
    settlements = q.order_by(Settlement.created_at.desc()).offset(skip).limit(limit).all()
    result = []
    for s in settlements:
        count = db.query(Order).filter(Order.settlement_id == s.id).count()
        data = SettlementResponse.model_validate(s)
        data.order_count = count
        result.append(data)
    return result


@router.post("", response_model=SettlementResponse)
def create_settlement(
    payload: SettlementCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    orders = db.query(Order).filter(
        Order.id.in_(payload.order_ids),
        Order.settlement_id == None,
        Order.is_test == False,
    ).options(joinedload(Order.items)).all()

    if not orders:
        raise HTTPException(status_code=400, detail="没有找到可结算的订单")

    total_supply = Decimal(0)
    total_refund = Decimal(0)
    for o in orders:
        if o.is_refunded:
            total_refund += o.refund_amount or 0
        else:
            for item in o.items:
                total_supply += item.supply_subtotal or 0

    net_supply = total_supply - total_refund
    payment_hkd = (net_supply / payload.hkd_rate).quantize(Decimal("0.01"))

    settlement = Settlement(
        invoice_number=_make_invoice_number(),
        period_start=payload.period_start,
        period_end=payload.period_end,
        total_supply_rmb=total_supply,
        total_refund_rmb=total_refund,
        net_supply_rmb=net_supply,
        hkd_rate=payload.hkd_rate,
        payment_amount_hkd=payment_hkd,
        notes=payload.notes,
        wemall_store_id=_active_store_id(db),
    )
    db.add(settlement)
    db.flush()

    for o in orders:
        o.settlement_id = settlement.id

    db.commit()
    db.refresh(settlement)
    return settlement


@router.post("/{settlement_id}/confirm", response_model=SettlementResponse)
def confirm_settlement(
    settlement_id: int,
    payload: SettlementConfirm,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="结算单不存在")
    if s.status == SettlementStatus.settled:
        raise HTTPException(status_code=400, detail="已结清，不可重复操作")
    s.actual_payment_hkd = payload.actual_payment_hkd
    s.status = SettlementStatus.settled
    s.settled_at = datetime.utcnow()
    if payload.notes:
        s.notes = payload.notes
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{settlement_id}")
def delete_settlement(
    settlement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="结算单不存在")
    if s.status == SettlementStatus.settled:
        raise HTTPException(status_code=400, detail="已结清的结算单不能删除")

    # 解除订单关联
    db.query(Order).filter(Order.settlement_id == settlement_id).update({"settlement_id": None})

    # 删除结算单
    db.delete(s)
    db.commit()
    return {"message": "删除成功"}


@router.get("/batch-invoice.zip")
def batch_invoice_zip(
    ids: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """批量下载多个 invoice PDF，打包为 ZIP。ids 为逗号分隔的结算单ID"""
    import zipfile, io
    from app.services.pdf_generator import generate_invoice_pdf
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sid in id_list:
            s = db.query(Settlement).filter(Settlement.id == sid).first()
            if not s:
                continue
            date_str = s.period_end.strftime("%Y%m%d")
            filename = f"Invoice#{s.invoice_number}+香港蔚蓝+{date_str}.pdf"
            zf.writestr(filename, generate_invoice_pdf(s))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=invoices.zip"},
    )


@router.get("/batch-detail.zip")
def batch_detail_zip(
    ids: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """批量下载多个明细 PDF，打包为 ZIP。ids 为逗号分隔的结算单ID"""
    import zipfile, io
    from app.services.pdf_generator import generate_detail_pdf
    from app.models.order import Order
    id_list = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sid in id_list:
            s = db.query(Settlement).filter(Settlement.id == sid).first()
            if not s:
                continue
            orders = db.query(Order).filter(Order.settlement_id == sid).all()
            date_str = s.period_end.strftime("%Y%m%d")
            filename = f"OrderDetail+香港蔚蓝+{date_str}.pdf"
            zf.writestr(filename, generate_detail_pdf(s, orders))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=details.zip"},
    )


@router.get("/year-invoice.zip")
def year_invoice_zip(
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """下载指定年份所有结算单的 invoice PDF，打包为 ZIP"""
    import zipfile, io
    from app.services.pdf_generator import generate_invoice_pdf
    settlements = db.query(Settlement).filter(
        Settlement.period_end >= f"{year}-01-01",
        Settlement.period_end < f"{year + 1}-01-01",
    ).all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in settlements:
            date_str = s.period_end.strftime("%Y%m%d")
            filename = f"Invoice#{s.invoice_number}+香港蔚蓝+{date_str}.pdf"
            zf.writestr(filename, generate_invoice_pdf(s))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=Invoices-{year}.zip"},
    )


@router.get("/year-detail.zip")
def year_detail_zip(
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """下载指定年份所有结算单的明细 PDF，打包为 ZIP"""
    import zipfile, io
    from app.services.pdf_generator import generate_detail_pdf
    from app.models.order import Order
    settlements = db.query(Settlement).filter(
        Settlement.period_end >= f"{year}-01-01",
        Settlement.period_end < f"{year + 1}-01-01",
    ).all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for s in settlements:
            orders = db.query(Order).filter(Order.settlement_id == s.id).all()
            date_str = s.period_end.strftime("%Y%m%d")
            filename = f"OrderDetail+香港蔚蓝+{date_str}.pdf"
            zf.writestr(filename, generate_detail_pdf(s, orders))
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=OrderDetails-{year}.zip"},
    )


@router.post("/{settlement_id}/send-email")
def send_settlement_email_route(
    settlement_id: int,
    include_detail: bool = True,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """发送结算账单邮件给所有启用邮箱的联系人"""
    from app.services.email_service import send_settlement_email
    from app.models.notification_contact import NotificationContact

    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="结算单不存在")

    # 获取所有启用且有邮箱的联系人
    contacts = db.query(NotificationContact).filter(
        NotificationContact.is_active == True,
        NotificationContact.email.isnot(None),
        NotificationContact.email != "",
    ).all()
    if not contacts:
        raise HTTPException(status_code=400, detail="没有配置邮箱通知联系人，请先在「通知号码」页面添加邮箱")

    to_emails = [c.email for c in contacts]

    # Generate PDFs
    invoice_pdf = generate_invoice_pdf(s)
    detail_pdf = None
    if include_detail:
        orders = db.query(Order).filter(Order.settlement_id == settlement_id).all()
        detail_pdf = generate_detail_pdf(s, orders)

    result = send_settlement_email(to_emails, s, invoice_pdf, detail_pdf)
    return {
        "sent": result["sent"],
        "recipients": to_emails,
        "error": result.get("error"),
    }


@router.get("/{settlement_id}/invoice.pdf")
def download_invoice(
    settlement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="结算单不存在")
    pdf_bytes = generate_invoice_pdf(s)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{s.invoice_number}.pdf"'},
    )


@router.get("/{settlement_id}/detail.pdf")
def download_detail(
    settlement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="结算单不存在")
    orders = db.query(Order).filter(Order.settlement_id == s.id).options(joinedload(Order.items)).all()
    pdf_bytes = generate_detail_pdf(s, orders)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{s.invoice_number}_detail.pdf"'},
    )


@router.post("/{settlement_id}/notify")
async def send_notification(
    settlement_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    s = db.query(Settlement).filter(Settlement.id == settlement_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="结算单不存在")
    result = await send_settlement_notification(db, s)
    return result


# ---- Exchange Rates ----

@rates_router.get("", response_model=List[ExchangeRateResponse])
def list_rates(limit: int = 30, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(ExchangeRate).order_by(ExchangeRate.date.desc()).limit(limit).all()


@rates_router.get("/today", response_model=ExchangeRateResponse)
def get_today_rate(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    today = date.today()
    rate = db.query(ExchangeRate).filter(ExchangeRate.date == today).first()
    if not rate:
        raise HTTPException(status_code=404, detail="今日汇率未录入")
    return rate


@rates_router.post("", response_model=ExchangeRateResponse)
def create_or_update_rate(
    payload: ExchangeRateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    existing = db.query(ExchangeRate).filter(ExchangeRate.date == payload.date).first()
    cny_to_hkd = (Decimal(1) / payload.hkd_to_cny).quantize(Decimal("0.0001"))
    if existing:
        existing.hkd_to_cny = payload.hkd_to_cny
        existing.cny_to_hkd = cny_to_hkd
        existing.source = "manual"
        db.commit()
        db.refresh(existing)
        return existing
    rate = ExchangeRate(date=payload.date, hkd_to_cny=payload.hkd_to_cny, cny_to_hkd=cny_to_hkd, source="manual")
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


@rates_router.post("/fetch-today")
async def fetch_today_rate(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    from app.services.exchange_rate_service import fetch_and_save_rate
    rate = await fetch_and_save_rate(db)
    return rate


@router.post("/auto-settle")
def auto_settle_period(
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    force: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    自动结算指定周期的未结算订单
    如果不传参数，则自动判断当前应该结算哪个周期
    force=True 时，即使不是16号或1号也可以手动触发
    """
    from datetime import datetime, timezone
    import pytz

    beijing_tz = pytz.timezone('Asia/Shanghai')
    now_beijing = datetime.now(beijing_tz)

    # 如果没有指定周期，自动判断
    if not period_start or not period_end:
        today = now_beijing.date()

        # 如果不是16号或1号，且没有强制执行，则报错
        if not force and today.day not in [1, 16]:
            raise HTTPException(
                status_code=400,
                detail=f"今天是{today.day}号，不是自动结算日期（16号或1号）。如需手动结算，请使用快速结算按钮。"
            )

        if today.day == 16 or (force and today.day > 15):
            # 16号凌晨或手动触发时，结算1-15号
            period_start = datetime(today.year, today.month, 1, 0, 0, 0, tzinfo=beijing_tz)
            period_end = datetime(today.year, today.month, 15, 23, 59, 59, tzinfo=beijing_tz)
        elif today.day == 1 or (force and today.day <= 15):
            # 1号凌晨或手动触发时，结算上月16号-月底
            last_month = today.month - 1 if today.month > 1 else 12
            last_year = today.year if today.month > 1 else today.year - 1
            from calendar import monthrange
            last_day = monthrange(last_year, last_month)[1]
            period_start = datetime(last_year, last_month, 16, 0, 0, 0, tzinfo=beijing_tz)
            period_end = datetime(last_year, last_month, last_day, 23, 59, 59, tzinfo=beijing_tz)
        else:
            raise HTTPException(status_code=400, detail="无法确定结算周期")
    else:
        period_start = datetime.fromisoformat(period_start).replace(tzinfo=beijing_tz)
        period_end = datetime.fromisoformat(period_end).replace(tzinfo=beijing_tz)

    # 查找该周期内的未结算订单
    orders = db.query(Order).filter(
        Order.order_date >= period_start,
        Order.order_date <= period_end,
        Order.settlement_id == None,
        Order.is_refunded == False,
        Order.is_test == False,
    ).options(joinedload(Order.items)).all()

    if not orders:
        return {"message": "该周期没有未结算订单", "period_start": period_start.isoformat(), "period_end": period_end.isoformat()}

    # 获取今日汇率
    today = now_beijing.date()
    rate_record = db.query(ExchangeRate).filter(ExchangeRate.date == today).first()
    if not rate_record:
        raise HTTPException(status_code=400, detail="今日汇率未录入，无法自动结算")

    # 计算总金额
    total_supply = Decimal(0)
    for o in orders:
        for item in o.items:
            total_supply += item.supply_subtotal or 0

    payment_hkd = (total_supply / rate_record.hkd_to_cny).quantize(Decimal("0.01"))

    # 创建结算单
    settlement = Settlement(
        invoice_number=_make_invoice_number(),
        period_start=period_start.replace(tzinfo=None),
        period_end=period_end.replace(tzinfo=None),
        total_supply_rmb=total_supply,
        total_refund_rmb=Decimal(0),
        net_supply_rmb=total_supply,
        hkd_rate=rate_record.hkd_to_cny,
        payment_amount_hkd=payment_hkd,
        notes=f"自动结算 {period_start.strftime('%Y-%m-%d')} ~ {period_end.strftime('%Y-%m-%d')}",
    )
    db.add(settlement)
    db.flush()

    # 关联订单
    for o in orders:
        o.settlement_id = settlement.id

    db.commit()
    db.refresh(settlement)

    # Auto-send email if SMTP is configured
    email_result = None
    try:
        from app.config import settings
        from app.services.email_service import send_settlement_email
        from app.services.pdf_generator import generate_invoice_pdf
        from app.models.notification_contact import NotificationContact
        if settings.SMTP_HOST and settings.SMTP_USER:
            contacts = db.query(NotificationContact).filter(
                NotificationContact.is_active == True,
                NotificationContact.email.isnot(None),
                NotificationContact.email != "",
            ).all()
            if contacts:
                to_emails = [c.email for c in contacts]
                invoice_pdf = generate_invoice_pdf(settlement)
                detail_orders = db.query(Order).filter(Order.settlement_id == settlement.id).all()
                detail_pdf = generate_detail_pdf(settlement, detail_orders)
                email_result = send_settlement_email(to_emails, settlement, invoice_pdf, detail_pdf)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Auto-send email failed: {e}")
        email_result = {"sent": 0, "error": str(e)}

    return {
        "message": "自动结算成功",
        "settlement_id": settlement.id,
        "invoice_number": settlement.invoice_number,
        "order_count": len(orders),
        "total_rmb": float(total_supply),
        "payment_hkd": float(payment_hkd),
        "email_result": email_result,
    }
