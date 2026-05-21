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
