from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.services.wemall_api import WemallAPI
import json


async def sync_orders(
    db: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict:
    if not start_date:
        start_date = datetime.now() - timedelta(days=7)
    if not end_date:
        end_date = datetime.now()

    api = WemallAPI()
    start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")

    created, updated, skipped = 0, 0, 0
    page = 1

    while True:
        result = await api.get_orders(start_str, end_str, page=page, page_size=50)
        items = result.get("items", result if isinstance(result, list) else [])
        if not items:
            break

        for raw_order in items:
            order_id = str(raw_order.get("orderId") or raw_order.get("orderNo", ""))
            if not order_id:
                continue

            existing = db.query(Order).filter(Order.wemall_order_id == order_id).first()

            order_time = raw_order.get("createTime") or raw_order.get("orderTime")
            if isinstance(order_time, str):
                try:
                    order_date = datetime.strptime(order_time, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    order_date = datetime.now()
            elif isinstance(order_time, (int, float)):
                order_date = datetime.fromtimestamp(order_time / 1000)
            else:
                order_date = datetime.now()

            if existing:
                # 更新发货状态
                status_map = {1: "pending", 2: "shipped", 3: "delivered", 4: "returned"}
                wemall_status = raw_order.get("deliveryStatus") or raw_order.get("status")
                if wemall_status in status_map:
                    existing.shipping_status = status_map[wemall_status]
                updated += 1
                continue

            order = Order(
                wemall_order_id=order_id,
                order_date=order_date,
                buyer_name=raw_order.get("receiverName") or raw_order.get("buyerName"),
                buyer_phone=raw_order.get("receiverPhone") or raw_order.get("buyerPhone"),
                shipping_address=raw_order.get("receiverAddress") or raw_order.get("address"),
                raw_data=json.dumps(raw_order, ensure_ascii=False),
            )
            db.add(order)
            db.flush()

            # 解析订单商品
            goods_list = raw_order.get("goodsList") or raw_order.get("items") or []
            for goods in goods_list:
                wemall_pid = str(goods.get("productId") or goods.get("goodsId", ""))
                product = db.query(Product).filter(Product.wemall_product_id == wemall_pid).first() if wemall_pid else None

                supply_price = product.supply_price if product else None
                qty = int(goods.get("num") or goods.get("quantity") or 1)
                supply_subtotal = (supply_price * qty) if supply_price else None

                item = OrderItem(
                    order_id=order.id,
                    product_id=product.id if product else None,
                    product_name=goods.get("goodsName") or goods.get("productName") or "未知商品",
                    sku=goods.get("sku") or goods.get("skuNo"),
                    quantity=qty,
                    retail_price=goods.get("price") or goods.get("salePrice"),
                    supply_price=supply_price,
                    supply_subtotal=supply_subtotal,
                )
                db.add(item)
            created += 1

        db.commit()
        total = result.get("total") or result.get("totalCount", 0)
        if page * 50 >= int(total):
            break
        page += 1

    return {"created": created, "updated": updated, "skipped": skipped}
