from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.models.order import ShippingStatus


class OrderItemResponse(BaseModel):
    id: int
    product_id: Optional[int]
    product_name: str
    sku: Optional[str]
    quantity: int
    retail_price: Optional[Decimal]
    supply_price: Optional[Decimal]
    supply_subtotal: Optional[Decimal]
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: int
    wemall_order_id: str
    order_date: datetime
    buyer_name: Optional[str]
    buyer_phone: Optional[str]
    shipping_address: Optional[str]
    shipping_status: ShippingStatus
    tracking_number: Optional[str]
    is_refunded: bool
    is_test: bool = False
    refund_amount: Decimal
    refund_date: Optional[datetime]
    refund_reason: Optional[str]
    settlement_id: Optional[int]
    cash_paid: Optional[Decimal] = None
    stored_value_paid: Optional[Decimal] = None
    notes: Optional[str]
    items: List[OrderItemResponse] = []
    created_at: datetime

    class Config:
        from_attributes = True


class OrderUpdate(BaseModel):
    shipping_status: Optional[ShippingStatus] = None
    tracking_number: Optional[str] = None
    is_refunded: Optional[bool] = None
    is_test: Optional[bool] = None
    refund_amount: Optional[Decimal] = None
    refund_date: Optional[datetime] = None
    refund_reason: Optional[str] = None
    notes: Optional[str] = None


class OrderFilter(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    shipping_status: Optional[ShippingStatus] = None
    is_refunded: Optional[bool] = None
    settlement_id: Optional[int] = None
    unsettled_only: bool = False
    keyword: Optional[str] = None
