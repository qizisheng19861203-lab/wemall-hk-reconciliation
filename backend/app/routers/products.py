from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.product import Product
from app.models.order import OrderItem
from app.models.user import User, UserRole
from app.core.deps import get_current_user, require_admin
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.services.wemall_api import WemallAPI
import pandas as pd
import io

router = APIRouter(prefix="/products", tags=["产品管理"])


@router.get("")
def list_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = db.query(Product)
    if is_active is not None:
        q = q.filter(Product.is_active == is_active)
    if keyword:
        q = q.filter(Product.name.contains(keyword) | Product.sku.contains(keyword))
    if category:
        q = q.filter(Product.category == category)
    total = q.count()
    items = q.order_by(Product.id.desc()).offset(skip).limit(limit).all()
    return {"items": items, "total": total}


@router.post("", response_model=ProductResponse)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),  # 只有admin可以改供货价
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    update_data = payload.model_dump(exclude_none=True)
    new_supply_price = update_data.get("supply_price")

    for k, v in update_data.items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)

    # 自动补录：如果更新了供货价，将所有关联的待录价订单条目补齐
    backfilled_count = 0
    if new_supply_price is not None:
        items_to_backfill = (
            db.query(OrderItem)
            .filter(
                OrderItem.product_id == product_id,
                OrderItem.supply_price.is_(None),
            )
            .all()
        )
        for item in items_to_backfill:
            item.supply_price = new_supply_price
            item.supply_subtotal = float(new_supply_price) * item.quantity
        if items_to_backfill:
            db.commit()
        backfilled_count = len(items_to_backfill)

    # 返回产品信息 + 补录数量
    result = {
        "id": product.id,
        "wemall_product_id": product.wemall_product_id,
        "name": product.name,
        "sku": product.sku,
        "category": product.category,
        "retail_price": float(product.retail_price) if product.retail_price else None,
        "supply_price": float(product.supply_price) if product.supply_price else None,
        "image_url": product.image_url,
        "is_active": product.is_active,
        "backfilled_count": backfilled_count,
    }
    return result


@router.delete("/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    # 检查是否有关联的订单条目
    linked_count = db.query(OrderItem).filter(OrderItem.product_id == product_id).count()
    if linked_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该产品有 {linked_count} 条订单记录，不能删除。可以将其设为【停用】代替。"
        )
    db.delete(product)
    db.commit()
    return {"message": "删除成功"}


def _get_wemall_master_api(db: Session) -> WemallAPI:
    """始终使用蔚蓝医药主店（id=1）的凭证同步产品，不随激活店铺切换。
    产品库来源固定为蔚蓝医药，与当前激活店铺无关。"""
    from app.models.wemall_store_config import WemallStoreConfig
    master = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == 1).first()
    if master:
        return WemallAPI(
            client_id=master.client_id,
            client_secret=master.client_secret,
            shop_id=master.shop_id,
        )
    # 兜底：如果找不到 id=1，用激活店铺
    return WemallAPI()


@router.post("/sync-wemall")
async def sync_products_from_wemall(
    page_limit: int = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """从微盟API同步产品（固定使用蔚蓝医药主店凭证，不随激活店铺切换）"""
    api = _get_wemall_master_api(db)
    created, updated = 0, 0

    page = 1
    max_pages = page_limit if page_limit else 1  # 默认只同步第1页

    while page <= max_pages:
        try:
            result = await api.get_products(page=page, page_size=20)
            products_data = result.get("pageList", [])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"微盟API错误: {str(e)}")

        if not products_data:
            break

        for item in products_data:
            goods_id = str(item.get("goodsId"))
            sku_code = str(item.get("outerGoodsCode", "") or "").strip()

            # 提取价格（取最低售价）
            price_info = item.get("goodsPrice", {})
            retail_price = float(price_info.get("minSalePrice", 0)) if price_info.get("minSalePrice") else None

            # 优先按产品编码（SKU）查找；找不到再按 wemall_product_id
            existing = None
            if sku_code:
                existing = db.query(Product).filter(Product.sku == sku_code).first()
            if not existing:
                existing = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

            if existing:
                existing.name = item.get("title", existing.name)
                existing.wemall_product_id = goods_id  # 顺便更新 wemall_product_id
                if sku_code:
                    existing.sku = sku_code
                existing.image_url = item.get("defaultImageUrl", existing.image_url)
                if retail_price:
                    existing.retail_price = retail_price
                updated += 1
            else:
                product = Product(
                    wemall_product_id=goods_id,
                    name=item.get("title", ""),
                    sku=sku_code,
                    image_url=item.get("defaultImageUrl"),
                    retail_price=retail_price,
                )
                db.add(product)
                created += 1

        db.commit()

        # 如果没有指定page_limit，只同步第1页就退出
        if not page_limit:
            break

        # 检查是否还有下一页
        total_count = result.get("totalCount", 0)
        if page * 20 >= total_count:
            break
        page += 1

    return {"created": created, "updated": updated, "total": created + updated}


@router.post("/sync-by-ids")
async def sync_products_by_ids(
    product_ids: List[str],
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """批量同步指定的商品ID（固定使用蔚蓝医药主店凭证）"""
    api = _get_wemall_master_api(db)
    created, updated, not_found = 0, 0, 0

    for product_id in product_ids:
        try:
            # 尝试通过商品ID获取详情
            result = await api.get_product_detail(str(product_id).strip())
            item = result.get("goods", {})

            if not item:
                not_found += 1
                continue

            goods_id = str(item.get("goodsId"))
            sku_code = str(item.get("outerGoodsCode", "") or "").strip()

            # 提取价格
            price_info = item.get("goodsPrice", {})
            retail_price = float(price_info.get("minSalePrice", 0)) if price_info.get("minSalePrice") else None

            # 优先按 SKU 查找，再按 wemall_product_id
            existing = None
            if sku_code:
                existing = db.query(Product).filter(Product.sku == sku_code).first()
            if not existing:
                existing = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

            if existing:
                existing.name = item.get("title", existing.name)
                existing.wemall_product_id = goods_id
                if sku_code:
                    existing.sku = sku_code
                existing.image_url = item.get("defaultImageUrl", existing.image_url)
                if retail_price:
                    existing.retail_price = retail_price
                updated += 1
            else:
                product = Product(
                    wemall_product_id=goods_id,
                    name=item.get("title", ""),
                    sku=sku_code,
                    image_url=item.get("defaultImageUrl"),
                    retail_price=retail_price,
                )
                db.add(product)
                created += 1

        except Exception as e:
            not_found += 1
            continue

    db.commit()
    return {"created": created, "updated": updated, "not_found": not_found}


def _get_wemall_target_api(db: Session) -> WemallAPI:
    """使用倍赛思甄选（id=2）的凭证"""
    from app.models.wemall_store_config import WemallStoreConfig
    target = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == 2).first()
    if not target:
        raise HTTPException(status_code=404, detail="倍赛思甄选店铺配置不存在（id=2）")
    return WemallAPI(
        client_id=target.client_id,
        client_secret=target.client_secret,
        shop_id=target.shop_id,
    )


@router.get("/target-store-skus")
async def get_target_store_skus(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """获取倍赛思甄选店铺已有的所有商品 SKU 列表（含在售+下架，goodsStatus=1和0）"""
    api = _get_wemall_target_api(db)
    vid = await api._get_organization_vid()
    all_skus = set()
    try:
        # goodsStatus=0 下架, goodsStatus=1 在售 — 两者都要计入"已同步"
        for goods_status in [0, 1]:
            page = 1
            while True:
                result = await api._request("goods/getList", {
                    "pageNum": page,
                    "pageSize": 20,
                    "queryParameter": {"goodsStatus": goods_status, "searchType": 1},
                    "basicInfo": {"vid": vid},
                })
                products_data = result.get("pageList", [])
                if not products_data:
                    break
                for item in products_data:
                    sku = str(item.get("outerGoodsCode", "") or "").strip()
                    if sku:
                        all_skus.add(sku)
                total_count = result.get("totalCount", 0)
                if page * 20 >= total_count:
                    break
                page += 1
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"查询倍赛思甄选商品失败: {str(e)}")

    return {"skus": list(all_skus), "count": len(all_skus)}


@router.get("/beisi-stock")
async def get_beisi_stock(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """实时查询倍赛思甄选店铺所有商品库存（goodsStock.goodsStockNum，page_size最大20）"""
    api = _get_wemall_target_api(db)
    stock_map: dict = {}  # {sku: {"total_stock": N, "name": "..."}}
    page = 1

    try:
        while True:
            result = await api.get_products(page=page, page_size=20)
            items = result.get("pageList", [])
            if not items:
                break
            for item in items:
                sku = str(item.get("outerGoodsCode", "") or "").strip()
                if not sku:
                    continue
                name = item.get("title", "")
                goods_stock = item.get("goodsStock") or {}
                total_stock = goods_stock.get("goodsStockNum", -1)
                stock_map[sku] = {"total_stock": int(total_stock), "name": name}
            total_count = result.get("totalCount", 0)
            if page * 20 >= total_count:
                break
            page += 1
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"查询倍赛思甄选商品失败: {str(e)}")

    zero_skus = [sku for sku, info in stock_map.items() if info["total_stock"] == 0]
    return {"items": stock_map, "zero_stock": zero_skus, "count": len(stock_map)}


@router.post("/sync-cost-price")
async def sync_cost_price_to_beisi(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """把我们产品库的供货价同步到倍赛思甄选店铺的商品成本价（costPrice）"""
    from app.models.product import Product

    # 1. 构建 DB 供货价映射：sku -> supply_price
    db_products = db.query(Product).filter(Product.supply_price != None, Product.sku != None).all()
    sku_to_price: dict = {p.sku: float(p.supply_price) for p in db_products if p.sku}
    if not sku_to_price:
        return {"updated_skus": 0, "skipped_products": 0, "errors": ["产品库无供货价数据"]}

    api = _get_wemall_target_api(db)
    try:
        all_items = await api.get_all_on_sale_products()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取倍赛思甄选商品列表失败: {str(e)}")

    updated_skus = 0
    skipped_products = 0
    errors = []

    for item in all_items:
        outer_code = str(item.get("outerGoodsCode", "") or "").strip()
        goods_id = item.get("goodsId")
        if not goods_id:
            continue
        # 快速检查：该商品（或其变体）是否有匹配的供货价
        base_match = outer_code in sku_to_price
        if not base_match:
            skipped_products += 1
            continue

        try:
            detail = await api.get_product_detail(str(goods_id))
            skus = detail.get("skuList", [])
            sku_updates = []
            for sku in skus:
                outer_sku = str(sku.get("outerSkuCode", "") or "").strip()
                # 精确匹配，或去掉 -2/-3 后缀后匹配（多规格产品）
                cost = sku_to_price.get(outer_sku)
                if cost is None:
                    base = outer_sku.rsplit("-", 1)[0] if "-" in outer_sku else outer_sku
                    cost = sku_to_price.get(base)
                if cost is not None:
                    sku_updates.append({
                        "skuId": sku["skuId"],
                        "salePrice": float(sku.get("salePrice") or 0),
                        "costPrice": cost,
                    })
            if sku_updates:
                await api.update_goods_cost_price(goods_id, sku_updates)
                updated_skus += len(sku_updates)
            else:
                skipped_products += 1
        except Exception as e:
            errors.append(f"goodsId={goods_id}: {str(e)}")

    return {"updated_skus": updated_skus, "skipped_products": skipped_products, "errors": errors}


@router.get("/target-store-config")
async def get_target_store_config(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """获取目标店铺（倍赛思甄选）的类目、模板、配送方式等配置"""
    api = _get_wemall_target_api(db)
    try:
        categories = await api.get_goods_categories()
        templates = await api.get_goods_templates()
        fulfill_types = await api.get_fulfill_types()
        wid = await api.get_employee_wid()
        freight_templates = await api.get_freight_templates()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"查询目标店铺配置失败: {str(e)}")

    return {
        "categories": categories,
        "templates": templates,
        "fulfillTypes": fulfill_types,
        "freightTemplates": freight_templates,
        "wid": wid,
    }


@router.post("/push-to-store")
async def push_products_to_store(
    payload: dict,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """将选中的产品推送到倍赛思甄选店铺（全自动，后端自动获取配置）"""
    product_ids = payload.get("product_ids", [])
    if not product_ids:
        raise HTTPException(status_code=400, detail="请选择要同步的产品")

    source_api = _get_wemall_master_api(db)
    target_api = _get_wemall_target_api(db)

    target_vid = await target_api._get_organization_vid()

    # 自动获取目标店铺配置
    try:
        categories = await target_api.get_goods_categories()
        templates = await target_api.get_goods_templates()
        fulfill_types = await target_api.get_fulfill_types()
        wid = await target_api.get_employee_wid()
        freight_templates = await target_api.get_freight_templates()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"获取目标店铺配置失败: {str(e)}")

    # 取第一个可用值
    if not categories:
        raise HTTPException(status_code=502, detail="目标店铺没有可用的商品类目")
    if not templates:
        raise HTTPException(status_code=502, detail="目标店铺没有可用的商详模板")
    if not wid:
        raise HTTPException(status_code=502, detail="无法获取目标店铺管理员 wid")

    # 找二级类目：固定使用「食品→营养保健」(categoryId=30)
    category_id = 30

    template_id = templates[0].get("id")

    # 配送方式：固定使用「商家配送」(deliveryType=1)
    delivery_config = {}
    merchant_delivery = next((ft for ft in fulfill_types if ft.get("deliveryType") == 1), None)
    if merchant_delivery:
        delivery_config = {
            "deliveryId": merchant_delivery.get("deliveryId"),
            "deliveryNodeShipId": merchant_delivery.get("id"),
            "deliveryType": 1,
        }
        if freight_templates:
            delivery_config["templateId"] = freight_templates[0].get("templateId")

    # 获取目标店铺已有的所有规格值（逐个取详情直到收集够）
    target_spec_values = {}  # {specValueName: {specId, specValueId}}
    target_spec_id = None
    try:
        target_products = await target_api.get_products(page=1, page_size=20)
        specs_found_from = 0
        for tp in target_products.get("pageList", []):
            tp_detail = await target_api.get_product_detail(str(tp.get("goodsId")))
            has_spec = False
            for spec in tp_detail.get("specInfoList", []):
                if not target_spec_id:
                    target_spec_id = spec.get("specId")
                for sv in spec.get("skuSpecValueList", []):
                    name = sv.get("specValueName", "")
                    if name and name not in target_spec_values:
                        target_spec_values[name] = {
                            "specId": spec.get("specId"),
                            "specValueId": sv.get("specValueId"),
                        }
                        has_spec = True
            if has_spec:
                specs_found_from += 1
            # 从5个不同产品收集到规格值就够了
            if specs_found_from >= 5:
                break
    except Exception:
        pass

    db_products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    if not db_products:
        raise HTTPException(status_code=404, detail="未找到选中的产品")

    results = {"success": [], "failed": []}

    for product in db_products:
        try:
            # 从蔚蓝医药获取完整商品详情（规格/SKU/库存/图片/详情）
            source_detail = None
            if product.wemall_product_id:
                try:
                    source_detail = await source_api.get_product_detail(product.wemall_product_id)
                except Exception:
                    pass

            if source_detail:
                image_url = source_detail.get("defaultImageUrl", "") or product.image_url or ""
                goods_image_urls = source_detail.get("goodsImageUrl", [])
                if not goods_image_urls and image_url:
                    goods_image_urls = [image_url]
                goods_desc = source_detail.get("goodsDesc", "") or ""
                sub_title = source_detail.get("subTitle", "") or ""
                is_multi_sku = source_detail.get("isMultiSku", False)
                source_spec_list = source_detail.get("specInfoList", [])
                source_sku_list = source_detail.get("skuList", [])
            else:
                image_url = product.image_url or ""
                goods_image_urls = [image_url] if image_url else []
                goods_desc = ""
                sub_title = ""
                is_multi_sku = False
                source_spec_list = []
                source_sku_list = []

            sale_price = str(product.retail_price) if product.retail_price else "0.01"
            cost_price = float(product.supply_price) if product.supply_price else None

            # 构建规格和SKU：必须使用目标店铺已有的specId/specValueId
            spec_info_list = []
            if is_multi_sku and source_spec_list and source_sku_list and target_spec_values:
                # 匹配源规格值到目标已有值
                def _match_spec_value(name):
                    """模糊匹配规格值名称到目标店铺已有的specValueId"""
                    if name in target_spec_values:
                        return target_spec_values[name]
                    # 去括号内容匹配
                    base = name.split("(")[0].split("（")[0].strip()
                    if base in target_spec_values:
                        return target_spec_values[base]
                    # 关键字匹配
                    if "直邮" in name:
                        for k, v in target_spec_values.items():
                            if "直邮" in k:
                                return v
                    if "现货" in name:
                        for k, v in target_spec_values.items():
                            if "现货" in k and "香港" not in k:
                                return v
                    if "香港" in name:
                        for k, v in target_spec_values.items():
                            if "香港" in k:
                                return v
                    # 默认返回第一个
                    first = list(target_spec_values.values())
                    return first[0] if first else None

                # 建立映射：源(specId, specValueId) → 目标specValueId
                src_to_target = {}
                used_target_values = []
                for spec in source_spec_list:
                    src_sid = spec.get("specId")
                    for sv in spec.get("skuSpecValueList", []):
                        src_vid = sv.get("specValueId")
                        matched = _match_spec_value(sv.get("specValueName", ""))
                        if matched:
                            src_to_target[(src_sid, src_vid)] = matched
                            if matched not in used_target_values:
                                used_target_values.append(matched)

                if used_target_values and target_spec_id:
                    spec_info_list = [{
                        "specId": target_spec_id,
                        "specName": "规格",
                        "skuSpecValueList": [
                            {"specValueId": v["specValueId"], "specValueName": k}
                            for k, v in target_spec_values.items()
                            if v in used_target_values
                        ],
                    }]

                    sku_list = []
                    seen_spec_combos = set()
                    for idx, src_sku in enumerate(source_sku_list):
                        if src_sku.get("isDisabled"):
                            continue
                        # 所有规格SKU统一使用商品编码（outerGoodsCode），不加后缀
                        outer_code = product.sku or ""
                        sku_entry = {
                            "salePrice": sale_price,
                            "skuStockNum": src_sku.get("skuStockNum", 0),
                            "outerSkuCode": outer_code,
                            "skuPreStockNum": 0,
                            "skuSpecValueList": [],
                        }
                        if cost_price is not None:
                            sku_entry["costPrice"] = cost_price
                        for sv in src_sku.get("skuSpecValueList", []):
                            key = (sv.get("specId"), sv.get("specValueId"))
                            matched = src_to_target.get(key)
                            if matched:
                                sku_entry["skuSpecValueList"].append({
                                    "specId": matched["specId"],
                                    "specValueId": matched["specValueId"],
                                })
                        if sku_entry["skuSpecValueList"]:
                            # 去重：不允许两个SKU指向同一个specValueId组合
                            combo_key = tuple(sv["specValueId"] for sv in sku_entry["skuSpecValueList"])
                            if combo_key not in seen_spec_combos:
                                seen_spec_combos.add(combo_key)
                                sku_list.append(sku_entry)

                    def _single_sku(stock):
                        entry = {"salePrice": sale_price, "skuStockNum": stock, "outerSkuCode": product.sku or "", "skuPreStockNum": 0}
                        if cost_price is not None:
                            entry["costPrice"] = cost_price
                        return entry

                    if not sku_list:
                        # 匹配失败，降级为单SKU
                        stock_num = source_sku_list[0].get("skuStockNum", 9999) if source_sku_list else 9999
                        sku_list = [_single_sku(stock_num)]
                        is_multi_sku = False
                        spec_info_list = []
                    else:
                        # 确保 skuList 数量不超过 specInfoList 中规格值组合数
                        max_skus = len(spec_info_list[0]["skuSpecValueList"]) if spec_info_list else 1
                        if len(sku_list) > max_skus:
                            sku_list = sku_list[:max_skus]
                else:
                    # 没有可用的目标规格值，降级为单SKU
                    stock_num = source_sku_list[0].get("skuStockNum", 9999) if source_sku_list else 9999
                    single = {"salePrice": sale_price, "skuStockNum": stock_num, "outerSkuCode": product.sku or "", "skuPreStockNum": 0}
                    if cost_price is not None:
                        single["costPrice"] = cost_price
                    sku_list = [single]
                    is_multi_sku = False
            else:
                stock_num = source_sku_list[0].get("skuStockNum", 9999) if source_sku_list else 9999
                single = {"salePrice": sale_price, "skuStockNum": stock_num, "outerSkuCode": product.sku or "", "skuPreStockNum": 0}
                if cost_price is not None:
                    single["costPrice"] = cost_price
                sku_list = [single]

            create_payload = {
                "basicInfo": {"vid": target_vid},
                "title": product.name,
                "subTitle": sub_title,
                "outerGoodsCode": product.sku or "",
                "categoryId": category_id,
                "goodsTemplateId": template_id,
                "goodsType": 1,
                "subGoodsType": 102,
                "deductStockType": 1,
                "defaultImageUrl": image_url,
                "goodsImageUrl": goods_image_urls if goods_image_urls else [image_url] if image_url else [],
                "goodsDesc": goods_desc,
                "isMultiSku": is_multi_sku,
                "isOnline": True,
                "initSales": 0,
                "wid": wid,
                "skuList": sku_list,
                "performanceWay": {
                    "deliveryList": [delivery_config] if delivery_config else [],
                },
            }
            if spec_info_list:
                create_payload["specInfoList"] = spec_info_list

            result = await target_api.create_goods(create_payload)
            results["success"].append({
                "product_id": product.id,
                "name": product.name,
                "goods_id": result.get("goodsId"),
            })
        except Exception as e:
            results["failed"].append({
                "product_id": product.id,
                "name": product.name,
                "error": str(e),
            })

    return results


@router.post("/import-supply-price")
async def import_supply_price(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """导入Excel更新供货价（优先使用商品编码匹配）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        # 检查必需的列
        if '供货价' not in df.columns:
            raise HTTPException(status_code=400, detail="Excel必须包含'供货价'列")

        if '商品编码' not in df.columns and '商品ID' not in df.columns:
            raise HTTPException(status_code=400, detail="Excel必须包含'商品编码'或'商品ID'列")

        updated, not_found = 0, 0
        not_found_list = []

        for _, row in df.iterrows():
            # 跳过供货价为空的行
            raw_price = row['供货价']
            if pd.isna(raw_price):
                continue
            try:
                supply_price = float(raw_price)
            except (ValueError, TypeError):
                continue

            product = None

            # 优先使用商品编码匹配（这是最准确的）
            if '商品编码' in df.columns:
                goods_code = str(row['商品编码']).strip()
                if goods_code and goods_code != 'nan':
                    product = db.query(Product).filter(Product.sku == goods_code).first()

            # 如果商品编码没找到，尝试用商品ID匹配
            if not product and '商品ID' in df.columns:
                goods_id = str(row['商品ID']).strip()
                # 处理数字格式的ID（如 7553141818.0）
                if '.' in goods_id:
                    goods_id = goods_id.split('.')[0]
                if goods_id and goods_id != 'nan':
                    product = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

            if product:
                product.supply_price = supply_price
                updated += 1
                # 补录该产品的待录价订单条目
                items_to_backfill = (
                    db.query(OrderItem)
                    .filter(
                        OrderItem.product_id == product.id,
                        OrderItem.supply_price.is_(None),
                    )
                    .all()
                )
                for item in items_to_backfill:
                    item.supply_price = supply_price
                    item.supply_subtotal = supply_price * item.quantity
            else:
                not_found += 1
                # 确保not_found_list里没有NaN值
                not_found_list.append({
                    "goods_code": str(row.get('商品编码', '') or '').replace('nan', ''),
                    "goods_id": str(row.get('商品ID', '') or '').replace('nan', ''),
                    "title": str(row.get('商品标题', '') or '').replace('nan', ''),
                })

        db.commit()

        return {
            "updated": updated,
            "not_found": not_found,
            "not_found_list": not_found_list[:20],  # 最多返回20个未找到的
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理Excel失败: {str(e)}")
