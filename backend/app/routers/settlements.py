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
    q = db.query(Settlement)
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
