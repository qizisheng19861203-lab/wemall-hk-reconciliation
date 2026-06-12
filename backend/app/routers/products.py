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


@router.get("", response_model=List[ProductResponse])
def list_products(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    skip: int = 0,
    limit: int = 100,
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
    return q.order_by(Product.id.desc()).offset(skip).limit(limit).all()


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

    # 找二级类目（优先取第一个有 children 的）
    category_id = None
    for cat in categories:
        children = cat.get("children", [])
        if children:
            category_id = children[0].get("categoryId")
            break
    if not category_id:
        category_id = categories[0].get("categoryId")

    template_id = templates[0].get("id")

    # 配送方式：取第一个配送方式
    delivery_config = {}
    if fulfill_types:
        ft = fulfill_types[0]
        delivery_config = {
            "deliveryId": ft.get("deliveryId"),
            "deliveryNodeShipId": ft.get("id"),
            "deliveryType": ft.get("deliveryType"),
        }
        # 商家配送需要运费模板
        if ft.get("deliveryType") == 1 and freight_templates:
            delivery_config["templateId"] = freight_templates[0].get("templateId")

    db_products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    if not db_products:
        raise HTTPException(status_code=404, detail="未找到选中的产品")

    results = {"success": [], "failed": []}

    for product in db_products:
        try:
            # 从蔚蓝医药获取完整商品详情（图片、描述等）
            source_detail = None
            if product.wemall_product_id:
                try:
                    detail_result = await source_api.get_product_detail(product.wemall_product_id)
                    source_detail = detail_result.get("goods", {})
                except Exception:
                    pass

            # 图片：优先用源店铺详情里的图片（微盟内部URL），否则用数据库里的
            if source_detail:
                image_url = source_detail.get("defaultImageUrl", "") or product.image_url or ""
                goods_image_urls = source_detail.get("goodsImageUrl", [])
                if not goods_image_urls and image_url:
                    goods_image_urls = [image_url]
                goods_desc = source_detail.get("goodsDesc", "")
                sub_title = source_detail.get("subTitle", "")
            else:
                image_url = product.image_url or ""
                goods_image_urls = [image_url] if image_url else []
                goods_desc = ""
                sub_title = ""

            sale_price = str(product.retail_price) if product.retail_price else "0.01"

            create_payload = {
                "basicInfo": {"vid": target_vid},
                "title": product.name,
                "subTitle": sub_title,
                "outerGoodsCode": product.sku or "",
                "categoryId": category_id,
                "goodsTemplateId": template_id,
                "goodsType": 1,
                "subGoodsType": 101,
                "deductStockType": 1,
                "defaultImageUrl": image_url,
                "goodsImageUrl": goods_image_urls if goods_image_urls else [image_url] if image_url else [],
                "goodsDesc": goods_desc,
                "isMultiSku": False,
                "isOnline": True,
                "initSales": 0,
                "wid": wid,
                "skuList": [{
                    "salePrice": sale_price,
                    "skuStockNum": 9999,
                    "outerSkuCode": product.sku or "",
                    "skuPreStockNum": 0,
                }],
                "performanceWay": {
                    "deliveryList": [delivery_config] if delivery_config else [],
                },
            }

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
