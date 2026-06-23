"""蔚蓝医药（母库 id=1）产品全量同步 —— 拉在售(1)+下架(0)全部页，upsert 进产品库。
产品库完整 = 订单条目能正确匹配「我方供货」，避免误判非供货。"""
from sqlalchemy.orm import Session
from app.models.product import Product
from app.models.wemall_store_config import WemallStoreConfig
from app.services.wemall_api import WemallAPI


async def sync_master_products(db: Session) -> dict:
    master = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == 1).first()
    if not master:
        return {"created": 0, "updated": 0, "error": "母库(id=1)凭证不存在"}
    api = WemallAPI(client_id=master.client_id, client_secret=master.client_secret, shop_id=master.shop_id)
    vid = await api._get_organization_vid()

    created = updated = 0
    for goods_status in (1, 0):  # 在售 + 下架都要（母库大量产品是下架"只供货"状态）
        page = 1
        while True:
            result = await api._request("goods/getList", {
                "pageNum": page, "pageSize": 20,
                "queryParameter": {"goodsStatus": goods_status, "searchType": 1},
                "basicInfo": {"vid": vid},
            })
            items = result.get("pageList", [])
            if not items:
                break
            for it in items:
                gid = str(it.get("goodsId"))
                sku = str(it.get("outerGoodsCode") or "").strip()
                pinfo = it.get("goodsPrice", {}) or {}
                rp = float(pinfo.get("minSalePrice")) if pinfo.get("minSalePrice") else None
                ex = None
                if sku:
                    ex = db.query(Product).filter(Product.sku == sku).first()
                if not ex:
                    ex = db.query(Product).filter(Product.wemall_product_id == gid).first()
                if ex:
                    ex.name = it.get("title", ex.name)
                    ex.wemall_product_id = gid
                    if sku:
                        ex.sku = sku
                    ex.image_url = it.get("defaultImageUrl", ex.image_url)
                    if rp:
                        ex.retail_price = rp
                    updated += 1
                else:
                    db.add(Product(wemall_product_id=gid, name=it.get("title", ""), sku=sku,
                                   image_url=it.get("defaultImageUrl"), retail_price=rp))
                    created += 1
            db.commit()
            if page * 20 >= result.get("totalCount", 0):
                break
            page += 1

    return {"created": created, "updated": updated, "total": created + updated}
