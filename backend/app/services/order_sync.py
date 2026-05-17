from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.order import Order, OrderItem, ShippingStatus
from app.models.product import Product
from app.services.wemall_api import WemallAPI
import json


async def sync_orders(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    """从微盟云同步订单（每次最多查30天，自动分段）"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=7)
    if not end_date:
        end_date = datetime.now()

    api = WemallAPI()
    created, updated, skipped = 0, 0, 0

    # 微盟订单查询时间跨度不能超过30天，按29天分段
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=29), end_date)
        start_ts = int(current_start.timestamp() * 1000)
        end_ts = int(current_end.timestamp() * 1000)

        page = 1
        while True:
            result = await api.get_orders(start_ts, end_ts, page=page, page_size=50)
            # 响应结构: data.pageList[]
            orders_list = result.get("pageList", [])
            if not orders_list:
                break

            for order_data in orders_list:
                order_info = order_data.get("orderInfo", {})
                base_info = order_info.get("orderBaseInfo", {})
                buyer_info = order_info.get("buyerInfo", {})
                items_list = order_info.get("items", [])

                order_no = str(base_info.get("orderNo", ""))
                if not order_no:
                    skipped += 1
                    continue

                existing = db.query(Order).filter(Order.wemall_order_id == order_no).first()

                create_time = base_info.get("createTime")
                order_date = datetime.fromtimestamp(create_time / 1000) if create_time else datetime.now()

                status_map = {
                    0: ShippingStatus.pending,
                    1: ShippingStatus.pending,
                    2: ShippingStatus.shipped,
                    3: ShippingStatus.delivered,
                    4: ShippingStatus.returned,
                }
                order_status = base_info.get("orderStatus", 0)
                shipping_status = status_map.get(order_status, ShippingStatus.pending)

                if existing:
                    existing.shipping_status = shipping_status
                    if shipping_status == ShippingStatus.returned:
                        existing.is_refunded = True
                    updated += 1
                    continue

                # 退款/退货订单不入库
                if shipping_status == ShippingStatus.returned:
                    skipped += 1
                    continue

                order = Order(
                    wemall_order_id=order_no,
                    order_date=order_date,
                    buyer_name=buyer_info.get("userNickName", ""),
                    buyer_phone=buyer_info.get("phone", ""),
                    shipping_address="",
                    shipping_status=shipping_status,
                    raw_data=json.dumps(order_data, ensure_ascii=False),
                )
                db.add(order)
                db.flush()

                for item_data in items_list:
                    goods_id = str(item_data.get("goodsId", ""))
                    product = db.query(Product).filter(Product.wemall_product_id == goods_id).first() if goods_id else None

                    qty = int(item_data.get("skuNum", 1))
                    retail_price = float(item_data.get("salePrice", 0))
                    supply_price = product.supply_price if product else None
                    supply_subtotal = (supply_price * qty) if supply_price else None

                    item = OrderItem(
                        order_id=order.id,
                        product_id=product.id if product else None,
                        product_name=item_data.get("goodsTitle", "未知商品"),
                        sku=str(item_data.get("skuId", "")),
                        quantity=qty,
                        retail_price=retail_price,
                        supply_price=supply_price,
                        supply_subtotal=supply_subtotal,
                    )
                    db.add(item)
                created += 1

            db.commit()

            total_count = result.get("totalCount", 0)
            if page * 50 >= total_count:
                break
            page += 1

        current_start = current_end + timedelta(seconds=1)

    return {"created": created, "updated": updated, "skipped": skipped}
