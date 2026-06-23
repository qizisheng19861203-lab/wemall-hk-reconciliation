from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from app.models.order import Order, OrderItem, ShippingStatus
from app.models.product import Product
from app.models.wemall_store_config import WemallStoreConfig
from app.services.wemall_api import WemallAPI
import json


def _extract_address(order_info: dict) -> str:
    """从 orderFulfill.receiverInfo 拼收货地址"""
    ri = ((order_info.get("orderFulfill") or {}).get("receiverInfo")) or {}
    parts = []
    for key in ("province", "city", "county", "area", "address"):
        v = str(ri.get(key) or "").strip()
        if v and v not in parts:
            parts.append(v)
    return "".join(parts)


def _extract_phone(order_info: dict) -> str:
    """手机号优先 buyerInfo.buyerExtInfo.buyerPhone"""
    bi = order_info.get("buyerInfo") or {}
    return str((bi.get("buyerExtInfo") or {}).get("buyerPhone") or bi.get("phone") or "")


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

    # 获取当前激活店铺 ID，用于标记订单来源
    active_store = db.query(WemallStoreConfig).filter(WemallStoreConfig.is_active == True).first()
    active_store_id = active_store.id if active_store else None

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

                order_status = base_info.get("orderStatus", 0)
                # 已取消(9)：不新建；若已入库则标记退款，排除结算/统计
                if order_status == 9:
                    if existing and not existing.is_refunded:
                        existing.is_refunded = True
                        updated += 1
                    else:
                        skipped += 1
                    continue
                # 微盟 orderStatus: 3=待发货 4=部分发货 5=已发货 7=已收货 8=已完成（与快递云打印口径一致）
                status_map = {
                    0: ShippingStatus.pending,
                    1: ShippingStatus.pending,
                    2: ShippingStatus.pending,
                    3: ShippingStatus.pending,
                    4: ShippingStatus.shipped,
                    5: ShippingStatus.shipped,
                    7: ShippingStatus.delivered,
                    8: ShippingStatus.delivered,
                }
                shipping_status = status_map.get(order_status, ShippingStatus.pending)
                addr = _extract_address(order_info)
                phone = _extract_phone(order_info)
                # 存 raw_data 前剥离身份证证件信息（隐私 + 体积，避免 raw_data 超长）
                try:
                    order_info.get("orderFulfill", {}).get("receiverInfo", {}).pop("certificateInfo", None)
                except Exception:
                    pass

                if existing:
                    existing.shipping_status = shipping_status
                    if addr and not (existing.shipping_address or "").strip():
                        existing.shipping_address = addr
                    if phone and not (existing.buyer_phone or "").strip():
                        existing.buyer_phone = phone
                    # 补录：重新匹配 product_id 和 supply_price
                    if items_list and existing.items:
                        for ex_item in existing.items:
                            # 如果 product_id 为空，尝试重新匹配
                            if ex_item.product_id is None:
                                sku_code = str(ex_item.sku or "").strip()
                                matched_product = None
                                # 先按 goodsCode/skuCode 匹配
                                for item_data in items_list:
                                    if str(item_data.get("skuId", "")) == (ex_item.sku or ""):
                                        gc = str(item_data.get("goodsCode") or item_data.get("skuCode") or "").strip()
                                        if gc:
                                            matched_product = db.query(Product).filter(Product.sku == gc).first()
                                        if not matched_product:
                                            gid = str(item_data.get("goodsId", ""))
                                            if gid:
                                                matched_product = db.query(Product).filter(Product.wemall_product_id == gid).first()
                                        break
                                if matched_product:
                                    ex_item.product_id = matched_product.id
                                    if matched_product.supply_price and not ex_item.supply_price:
                                        ex_item.supply_price = matched_product.supply_price
                                        ex_item.supply_subtotal = matched_product.supply_price * ex_item.quantity
                            # 补录零售价
                            if ex_item.retail_price is None or float(ex_item.retail_price) == 0:
                                for item_data in items_list:
                                    if str(item_data.get("skuId", "")) == (ex_item.sku or ""):
                                        rp = float(item_data.get("salePrice") or item_data.get("skuPrice") or item_data.get("goodsPrice") or 0)
                                        if rp > 0:
                                            ex_item.retail_price = rp
                                        break
                    updated += 1
                    continue

                order = Order(
                    wemall_order_id=order_no,
                    order_date=order_date,
                    buyer_name=buyer_info.get("userNickName", ""),
                    buyer_phone=phone,
                    shipping_address=addr,
                    shipping_status=shipping_status,
                    wemall_store_id=active_store_id,
                    raw_data=json.dumps(order_data, ensure_ascii=False),
                )
                db.add(order)
                db.flush()

                for item_data in items_list:
                    goods_id = str(item_data.get("goodsId", ""))
                    sku_code = str(item_data.get("goodsCode") or item_data.get("skuCode") or "").strip()

                    # 匹配产品：优先用 SKU 编码匹配，再用 goodsId
                    product = None
                    if sku_code:
                        product = db.query(Product).filter(Product.sku == sku_code).first()
                    if not product and goods_id:
                        product = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

                    qty = int(item_data.get("skuNum", 1))
                    # 尝试多个价格字段名（微盟API字段名可能不同）
                    _rp_raw = item_data.get("salePrice") or item_data.get("skuPrice") or item_data.get("goodsPrice") or 0
                    retail_price = float(_rp_raw) if _rp_raw else None
                    supply_price = product.supply_price if product else None
                    supply_subtotal = (supply_price * qty) if supply_price else None

                    item = OrderItem(
                        order_id=order.id,
                        product_id=product.id if product else None,
                        product_name=item_data.get("goodsTitle", "未知商品"),
                        sku=sku_code or str(item_data.get("skuId", "")),
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
