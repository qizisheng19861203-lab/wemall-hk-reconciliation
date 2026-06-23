from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    wemall_product_id = Column(String(100), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    sku = Column(String(100), nullable=True, index=True)
    barcode = Column(String(100), nullable=True)
    image_url = Column(String(500), nullable=True)
    category = Column(String(100), nullable=True)
    retail_price = Column(Numeric(10, 2), nullable=True, comment="零售价(RMB)")
    supply_price = Column(Numeric(10, 2), nullable=True, comment="供货价(RMB)")
    unit = Column(String(20), default="件")
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    temp_stock_enabled = Column(Boolean, default=False, comment="临时库存开关：开=跳过自动同步并保持固定库存")
    temp_stock_qty = Column(Integer, nullable=True, comment="临时库存数量（temp_stock_enabled开启时生效）")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order_items = relationship("OrderItem", back_populates="product")
