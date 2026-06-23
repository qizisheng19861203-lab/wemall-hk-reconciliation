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


def _active_store_id(db: Session) -> Optional[int]:
    """返回当前激活微盟店铺的 ID，用于过滤订单"""
    from app.models.wemall_store_config import WemallStoreConfig
    store = db.query(WemallStoreConfig).filter(WemallStoreConfig.is_active == True).first()
    return store.id if store else None


def _store_filter(db: Session):
    """返回 SQLAlchemy filter 条件，按激活店铺过滤订单"""
    sid = _active_store_id(db)
    if sid is not None:
        return Order.wemall_store_id == sid
    return True  # fallback: 不过滤


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    from sqlalchemy.orm import joinedload
    sf = _store_filter(db)

    # 未结清金额
    unsettled_orders = db.query(Order).filter(sf, Order.settlement_id == None, Order.is_refunded == False, Order.is_test == False)\
        .options(joinedload(Order.items)).all()
    unsettled_rmb = sum(
        sum(item.supply_subtotal or 0 for item in o.items)
        for o in unsettled_orders
    )

    # 今日供货额
    today = date.today()
    today_orders = db.query(Order).filter(
        sf,
        func.date(Order.order_date) == today,
        Order.is_refunded == False,
        Order.is_test == False,
    ).options(joinedload(Order.items)).all()
    today_supply = sum(sum(item.supply_subtotal or 0 for item in o.items) for o in today_orders)

    # 本月供货额
    month_orders = db.query(Order).filter(
        sf,
        extract("year", Order.order_date) == today.year,
        extract("month", Order.order_date) == today.month,
        Order.is_refunded == False,
        Order.is_test == False,
    ).options(joinedload(Order.items)).all()
    month_supply = sum(sum(item.supply_subtotal or 0 for item in o.items) for o in month_orders)

    # 待结算结算单数（按激活店铺过滤）
    _sid = _active_store_id(db)
    _pq = db.query(Settlement).filter(Settlement.status != SettlementStatus.settled)
    if _sid is not None:
        _pq = _pq.filter(Settlement.wemall_store_id == _sid)
    pending_settlements = _pq.count()

    return {
        "unsettled_rmb": float(unsettled_rmb),
        "today_supply_rmb": float(today_supply),
        "month_supply_rmb": float(month_supply),
        "pending_settlements": pending_settlements,
        "unsettled_order_count": len(unsettled_orders),
    }


@router.get("/monthly-daily")
def get_monthly_daily(
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """返回指定月份每天的供货额（默认当月）"""
    from sqlalchemy.orm import joinedload
    import calendar
    today = date.today()
    year = year or today.year
    month = month or today.month
    _, days_in_month = calendar.monthrange(year, month)
    sf = _store_filter(db)

    orders = db.query(Order).filter(
        sf,
        extract("year", Order.order_date) == year,
        extract("month", Order.order_date) == month,
        Order.is_refunded == False,
        Order.is_test == False,
    ).options(joinedload(Order.items)).all()

    # 按日期聚合
    daily: dict[int, float] = {}
    for o in orders:
        day = o.order_date.day
        supply = sum(float(item.supply_subtotal or 0) for item in o.items)
        daily[day] = daily.get(day, 0) + supply

    return [
        {"day": d, "supply_rmb": round(daily.get(d, 0), 2)}
        for d in range(1, days_in_month + 1)
    ]


@router.get("/monthly")
def get_monthly_report(
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from sqlalchemy.orm import joinedload
    sf = _store_filter(db)
    result = []
    for month in range(1, 13):
        orders = db.query(Order).filter(
            sf,
            extract("year", Order.order_date) == year,
            extract("month", Order.order_date) == month,
            Order.is_test == False,
        ).options(joinedload(Order.items)).all()
        supply = sum(
            sum(item.supply_subtotal or 0 for item in o.items)
            for o in orders if not o.is_refunded
        )
        refund = sum(o.refund_amount or 0 for o in orders if o.is_refunded)
        result.append({
            "month": month,
            "order_count": sum(1 for o in orders if not o.is_refunded),
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
    sf = _store_filter(db)
    years = db.query(extract("year", Order.order_date).label("year"))\
        .filter(sf).distinct().order_by("year").all()
    result = []
    for (year,) in years:
        orders = db.query(Order).filter(
            sf,
            extract("year", Order.order_date) == year,
            Order.is_test == False,
        ).options(joinedload(Order.items)).all()
        supply = sum(
            sum(item.supply_subtotal or 0 for item in o.items)
            for o in orders if not o.is_refunded
        )
        refund = sum(o.refund_amount or 0 for o in orders if o.is_refunded)
        result.append({
            "year": int(year),
            "order_count": sum(1 for o in orders if not o.is_refunded),
            "supply_rmb": float(supply),
            "refund_rmb": float(refund),
            "net_rmb": float(supply - refund),
        })
    return result
