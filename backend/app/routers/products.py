from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.product import Product
from app.models.user import User, UserRole
from app.core.deps import get_current_user, require_admin
from app.schemas.product import ProductCreate, ProductUpdate, ProductResponse
from app.services.wemall_api import WemallAPI

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
    try:
        result = await api.get_products()
        products_data = result.get("pageList", [])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"微盟API错误: {str(e)}")

    created, updated = 0, 0
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
    return {"created": created, "updated": updated, "total": len(products_data)}
