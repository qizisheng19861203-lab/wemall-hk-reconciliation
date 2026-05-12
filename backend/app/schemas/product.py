from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    barcode: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    retail_price: Optional[Decimal] = None
    supply_price: Optional[Decimal] = None
    unit: str = "件"
    notes: Optional[str] = None
    wemall_product_id: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category: Optional[str] = None
    retail_price: Optional[Decimal] = None
    supply_price: Optional[Decimal] = None
    unit: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    wemall_product_id: Optional[str]
    name: str
    sku: Optional[str]
    barcode: Optional[str]
    image_url: Optional[str]
    category: Optional[str]
    retail_price: Optional[Decimal]
    supply_price: Optional[Decimal]
    unit: str
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
