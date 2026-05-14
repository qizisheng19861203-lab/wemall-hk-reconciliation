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
    """从微盟云同步订单"""
    if not start_date:
        start_date = datetime.now() - timedelta(days=7)
    if not end_date:
        end_date = datetime.now()

    api = WemallAPI()
    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    created, updated, skipped = 0, 0, 0
    page = 1

    while True:
        result = await api.get_orders(start_ts, end_ts, page=page, page_size=50)
        orders_list = result.get("pageList", [])
        if not orders_list:
            break

        for order_data in orders_list:
            order_info = order_data.get("orderInfo", {})
            base_info = order_info.get("orderBaseInfo", {})
            buyer_info = order_info.get("buyerInfo", {})
            pay_info = order_info.get("payInfo", {})
            items_list = order_info.get("items", [])

            order_no = str(base_info.get("orderNo", ""))
            if not order_no:
                skipped += 1
                continue

            existing = db.query(Order).filter(Order.wemall_order_id == order_no).first()

            # 解析订单时间
            create_time = base_info.get("createTime")
            if create_time:
                order_date = datetime.fromtimestamp(create_time / 1000)
            else:
                order_date = datetime.now()

            # 映射发货状态
            status_map = {
                0: ShippingStatus.PENDING,
                1: ShippingStatus.PENDING,
                2: ShippingStatus.SHIPPED,
                3: ShippingStatus.DELIVERED,
                4: ShippingStatus.RETURNED,
            }
            order_status = base_info.get("orderStatus", 0)
            shipping_status = status_map.get(order_status, ShippingStatus.PENDING)

            if existing:
                existing.shipping_status = shipping_status
                updated += 1
                continue

            # 创建新订单
            order = Order(
                wemall_order_id=order_no,
                order_date=order_date,
                buyer_name=buyer_info.get("userNickName", ""),
                buyer_phone=buyer_info.get("phone", ""),
                shipping_address="",  # 微盟 v2.0 需要单独获取地址
                shipping_status=shipping_status,
                raw_data=json.dumps(order_data, ensure_ascii=False),
            )
            db.add(order)
            db.flush()

            # 解析订单商品
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

        # 检查是否还有下一页
        total_count = result.get("totalCount", 0)
        if page * 50 >= total_count:
            break
        page += 1

    return {"created": created, "updated": updated, "skipped": skipped}
