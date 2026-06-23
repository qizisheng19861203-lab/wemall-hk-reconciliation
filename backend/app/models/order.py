from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ShippingStatus(str, enum.Enum):
    pending = "pending"        # 待发货
    shipped = "shipped"        # 已发货
    delivered = "delivered"    # 已签收
    returned = "returned"      # 已退货


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    wemall_order_id = Column(String(100), unique=True, nullable=False, index=True)
    order_date = Column(DateTime(timezone=True), nullable=False)
    buyer_name = Column(String(100), nullable=True)
    buyer_phone = Column(String(20), nullable=True)
    shipping_address = Column(Text, nullable=True)
    shipping_status = Column(Enum(ShippingStatus), default=ShippingStatus.pending)
    tracking_number = Column(String(100), nullable=True)
    is_refunded = Column(Boolean, default=False)
    is_test = Column(Boolean, default=False, comment="测试订单，不计入结算")
    refund_amount = Column(Numeric(10, 2), default=0, comment="退款金额(RMB)")
    refund_date = Column(DateTime(timezone=True), nullable=True)
    refund_reason = Column(Text, nullable=True)
    settlement_id = Column(Integer, ForeignKey("settlements.id"), nullable=True)
    wemall_store_id = Column(Integer, nullable=True, comment="来源微盟店铺ID（关联wemall_store_configs）")
    notes = Column(Text, nullable=True)
    raw_data = Column(Text, nullable=True, comment="微盟原始数据JSON")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    settlement = relationship("Settlement", back_populates="orders")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    product_name = Column(String(255), nullable=False, comment="下单时产品名称快照")
    sku = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    retail_price = Column(Numeric(10, 2), nullable=True, comment="零售单价(RMB)")
    supply_price = Column(Numeric(10, 2), nullable=True, comment="供货单价(RMB)，下单时快照")
    supply_subtotal = Column(Numeric(10, 2), nullable=True, comment="供货小计(RMB)")

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

    @property
    def image_url(self):
        return self.product.image_url if self.product else None
