from sqlalchemy import Column, Integer, String, Boolean, DateTime, Numeric, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class SettlementStatus(str, enum.Enum):
    pending = "pending"      # 待结算
    notified = "notified"    # 已发送结算通知
    settled = "settled"      # 已结清


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    total_supply_rmb = Column(Numeric(12, 2), nullable=False, default=0, comment="供货总额(RMB)")
    total_refund_rmb = Column(Numeric(12, 2), nullable=False, default=0, comment="退款总额(RMB)")
    net_supply_rmb = Column(Numeric(12, 2), nullable=False, default=0, comment="净供货额(RMB)")
    hkd_rate = Column(Numeric(8, 4), nullable=False, comment="结算汇率 HKD/RMB")
    payment_amount_hkd = Column(Numeric(12, 2), nullable=False, default=0, comment="应付港币金额")
    actual_payment_hkd = Column(Numeric(12, 2), nullable=True, comment="实际支付港币金额")
    status = Column(Enum(SettlementStatus), default=SettlementStatus.pending)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    wemall_store_id = Column(Integer, nullable=True, comment="来源微盟店铺ID")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    orders = relationship("Order", back_populates="settlement")
    notifications = relationship("SettlementNotification", back_populates="settlement")


class SettlementNotification(Base):
    __tablename__ = "settlement_notifications"

    id = Column(Integer, primary_key=True, index=True)
    settlement_id = Column(Integer, ForeignKey("settlements.id"), nullable=False)
    channel = Column(String(20), nullable=False, comment="sms / wecom / email")
    recipient = Column(String(100), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String(20), default="sent")
    sent_at = Column(DateTime(timezone=True), server_default=func.now())

    settlement = relationship("Settlement", back_populates="notifications")
