from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from app.models.settlement import SettlementStatus
from app.schemas.order import OrderResponse


class SettlementCreate(BaseModel):
    period_start: datetime
    period_end: datetime
    hkd_rate: Decimal
    order_ids: List[int]
    notes: Optional[str] = None


class SettlementConfirm(BaseModel):
    actual_payment_hkd: Decimal
    notes: Optional[str] = None


class SettlementResponse(BaseModel):
    id: int
    invoice_number: str
    period_start: datetime
    period_end: datetime
    total_supply_rmb: Decimal
    total_refund_rmb: Decimal
    net_supply_rmb: Decimal
    hkd_rate: Decimal
    payment_amount_hkd: Decimal
    actual_payment_hkd: Optional[Decimal]
    status: SettlementStatus
    settled_at: Optional[datetime]
    notes: Optional[str]
    order_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ExchangeRateResponse(BaseModel):
    id: int
    date: date
    hkd_to_cny: Decimal
    cny_to_hkd: Decimal
    source: str
    created_at: datetime

    class Config:
        from_attributes = True


class ExchangeRateCreate(BaseModel):
    date: date
    hkd_to_cny: Decimal
