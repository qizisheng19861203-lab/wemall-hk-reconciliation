from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.product import Product
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


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),  # 只有admin可以改供货价
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(product, k, v)
    db.commit()
    db.refresh(product)
    return product


@router.post("/sync-wemall")
async def sync_products_from_wemall(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """从微盟API同步产品"""
    api = WemallAPI()
    created, updated = 0, 0

    page = 1
    while True:
        try:
            result = await api.get_products(page=page, page_size=20)
            products_data = result.get("pageList", [])
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"微盟API错误: {str(e)}")

        if not products_data:
            break

        for item in products_data:
            goods_id = str(item.get("goodsId"))
            existing = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

            # 提取价格（取最低售价）
            price_info = item.get("goodsPrice", {})
            retail_price = float(price_info.get("minSalePrice", 0)) if price_info.get("minSalePrice") else None

            if existing:
                existing.name = item.get("title", existing.name)
                existing.image_url = item.get("defaultImageUrl", existing.image_url)
                if retail_price:
                    existing.retail_price = retail_price
                updated += 1
            else:
                product = Product(
                    wemall_product_id=goods_id,
                    name=item.get("title", ""),
                    sku=item.get("outerGoodsCode", ""),
                    image_url=item.get("defaultImageUrl"),
                    retail_price=retail_price,
                )
                db.add(product)
                created += 1

        db.commit()

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
    """批量同步指定的商品ID（支持商品ID或商品编码）"""
    api = WemallAPI()
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
            existing = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

            # 提取价格
            price_info = item.get("goodsPrice", {})
            retail_price = float(price_info.get("minSalePrice", 0)) if price_info.get("minSalePrice") else None

            if existing:
                existing.name = item.get("title", existing.name)
                existing.image_url = item.get("defaultImageUrl", existing.image_url)
                if retail_price:
                    existing.retail_price = retail_price
                updated += 1
            else:
                product = Product(
                    wemall_product_id=goods_id,
                    name=item.get("title", ""),
                    sku=item.get("outerGoodsCode", ""),
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
    """导入Excel更新供货价（支持商品ID或商品编码匹配）"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")

    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))

        # 检查必需的列
        required_cols = ['商品ID', '供货价']
        if not all(col in df.columns for col in required_cols):
            raise HTTPException(
                status_code=400,
                detail=f"Excel必须包含以下列: {', '.join(required_cols)}"
            )

        updated, not_found = 0, 0
        not_found_list = []

        for _, row in df.iterrows():
            goods_id = str(row['商品ID']).strip()
            supply_price = float(row['供货价'])

            # 先尝试用商品ID匹配
            product = db.query(Product).filter(Product.wemall_product_id == goods_id).first()

            # 如果没找到，尝试用商品编码匹配
            if not product and '商品编码' in df.columns:
                goods_code = str(row['商品编码']).strip()
                product = db.query(Product).filter(Product.sku == goods_code).first()

            if product:
                product.supply_price = supply_price
                updated += 1
            else:
                not_found += 1
                not_found_list.append({
                    "goods_id": goods_id,
                    "title": row.get('商品标题', ''),
                })

        db.commit()

        return {
            "updated": updated,
            "not_found": not_found,
            "not_found_list": not_found_list[:20],  # 最多返回20个未找到的
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理Excel失败: {str(e)}")
