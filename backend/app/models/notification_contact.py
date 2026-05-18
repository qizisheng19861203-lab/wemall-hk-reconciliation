from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class NotificationContact(Base):
    __tablename__ = "notification_contacts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="联系人名称")
    phone = Column(String(20), nullable=False, comment="手机号，带+86前缀或不带")
    email = Column(String(200), nullable=True, comment="邮箱地址，用于接收账单邮件")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
