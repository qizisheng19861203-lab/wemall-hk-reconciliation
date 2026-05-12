from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import Optional
from datetime import datetime, date
from app.database import get_db
from app.models.order import Order, OrderItem
from app.models.settlement import Settlement, SettlementStatus
from app.models.user import User
from app.core.deps import get_current_user

router = APIRouter(prefix="/reports", tags=["统计报表"])


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from sqlalchemy.orm import joinedload
    from decimal import Decimal

    # 未结清金额
    unsettled_orders = db.query(Order).filter(Order.settlement_id == None, Order.is_refunded == False)\
        .options(joinedload(Order.items)).all()
    unsettled_rmb = sum(
        sum(item.supply_subtotal or 0 for item in o.items)
        for o in unsettled_orders
    )

    # 今日供货额
    today = date.today()
    today_orders = db.query(Order).filter(
        func.date(Order.order_date) == today,
        Order.is_refunded == False,
    ).options(joinedload(Order.items)).all()
    today_supply = sum(sum(item.supply_subtotal or 0 for item in o.items) for o in today_orders)

    # 本月供货额
    month_orders = db.query(Order).filter(
        extract("year", Order.order_date) == today.year,
        extract("month", Order.order_date) == today.month,
        Order.is_refunded == False,
    ).options(joinedload(Order.items)).all()
    month_supply = sum(sum(item.supply_subtotal or 0 for item in o.items) for o in month_orders)

    # 待结算结算单数
    pending_settlements = db.query(Settlement).filter(
        Settlement.status != SettlementStatus.settled
    ).count()

    return {
        "unsettled_rmb": float(unsettled_rmb),
        "today_supply_rmb": float(today_supply),
        "month_supply_rmb": float(month_supply),
        "pending_settlements": pending_settlements,
        "unsettled_order_count": len(unsettled_orders),
    }


@router.get("/monthly")
def get_monthly_report(
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy.orm import joinedload
    result = []
    for month in range(1, 13):
        orders = db.query(Order).filter(
            extract("year", Order.order_date) == year,
            extract("month", Order.order_date) == month,
        ).options(joinedload(Order.items)).all()
        supply = sum(
            sum(item.supply_subtotal or 0 for item in o.items)
            for o in orders if not o.is_refunded
        )
        refund = sum(o.refund_amount or 0 for o in orders if o.is_refunded)
        result.append({
            "month": month,
            "order_count": len(orders),
            "supply_rmb": float(supply),
            "refund_rmb": float(refund),
            "net_rmb": float(supply - refund),
        })
    return result


@router.get("/yearly")
def get_yearly_report(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy.orm import joinedload
    years = db.query(extract("year", Order.order_date).label("year"))\
        .distinct().order_by("year").all()
    result = []
    for (year,) in years:
        orders = db.query(Order).filter(
            extract("year", Order.order_date) == year,
        ).options(joinedload(Order.items)).all()
        supply = sum(
            sum(item.supply_subtotal or 0 for item in o.items)
            for o in orders if not o.is_refunded
        )
        refund = sum(o.refund_amount or 0 for o in orders if o.is_refunded)
        result.append({
            "year": int(year),
            "order_count": len(orders),
            "supply_rmb": float(supply),
            "refund_rmb": float(refund),
            "net_rmb": float(supply - refund),
        })
    return result
