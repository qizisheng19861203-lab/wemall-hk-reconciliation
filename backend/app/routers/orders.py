from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.models.order import Order, OrderItem, ShippingStatus
from app.models.user import User
from app.core.deps import get_current_user, require_admin_or_operator
from app.schemas.order import OrderResponse, OrderUpdate, OrderFilter
from app.services.wemall_api import WemallAPI

router = APIRouter(prefix="/orders", tags=["订单管理"])


def _build_query(db: Session, f: OrderFilter):
    q = db.query(Order).options(joinedload(Order.items))
    if f.start_date:
        q = q.filter(Order.order_date >= f.start_date)
    if f.end_date:
        q = q.filter(Order.order_date <= f.end_date)
    if f.shipping_status:
        q = q.filter(Order.shipping_status == f.shipping_status)
    if f.is_refunded is not None:
        q = q.filter(Order.is_refunded == f.is_refunded)
    if f.settlement_id:
        q = q.filter(Order.settlement_id == f.settlement_id)
    if f.unsettled_only:
        q = q.filter(Order.settlement_id == None)
    if f.keyword:
        q = q.filter(
            or_(
                Order.wemall_order_id.contains(f.keyword),
                Order.buyer_name.contains(f.keyword),
                Order.buyer_phone.contains(f.keyword),
            )
        )
    return q


@router.get("", response_model=List[OrderResponse])
def list_orders(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    shipping_status: Optional[ShippingStatus] = None,
    is_refunded: Optional[bool] = None,
    settlement_id: Optional[int] = None,
    unsettled_only: bool = False,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    f = OrderFilter(
        start_date=start_date, end_date=end_date,
        shipping_status=shipping_status, is_refunded=is_refunded,
        settlement_id=settlement_id, unsettled_only=unsettled_only,
        keyword=keyword,
    )
    return _build_query(db, f).order_by(Order.order_date.desc()).offset(skip).limit(limit).all()


@router.get("/stats")
def get_order_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy import func
    from app.models.order import OrderItem
    from decimal import Decimal

    q = db.query(Order)
    if start_date:
        q = q.filter(Order.order_date >= start_date)
    if end_date:
        q = q.filter(Order.order_date <= end_date)

    orders = q.options(joinedload(Order.items)).all()
    total_supply = sum(
        sum(item.supply_subtotal or 0 for item in o.items)
        for o in orders if not o.is_refunded
    )
    total_refund = sum(o.refund_amount or 0 for o in orders if o.is_refunded)
    unsettled = sum(
        sum(item.supply_subtotal or 0 for item in o.items)
        for o in orders if not o.is_refunded and not o.settlement_id
    )
    return {
        "total_orders": len(orders),
        "total_supply_rmb": float(total_supply),
        "total_refund_rmb": float(total_refund),
        "net_supply_rmb": float(total_supply - total_refund),
        "unsettled_rmb": float(unsettled),
    }


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    payload: OrderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin_or_operator),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(order, k, v)
    db.commit()
    db.refresh(order)
    return order


@router.post("/sync-wemall")
async def sync_orders_from_wemall(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_operator),
):
    """从微盟拉取订单并入库"""
    from app.services.order_sync import sync_orders
    result = await sync_orders(db, start_date, end_date)
    return result
