from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class WemallStoreConfig(Base):
    """微盟多店铺配置表 — 只能有一个 is_active=True"""
    __tablename__ = "wemall_store_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)          # 店铺显示名称，如"我的店铺"/"倍赛思甄选"
    client_id = Column(String(128), nullable=False)     # 微盟开放平台 client_id
    client_secret = Column(String(128), nullable=False) # 微盟开放平台 client_secret
    shop_id = Column(String(50), nullable=True)         # 店铺 shop_id（可选）
    notes = Column(String(300), nullable=True)          # 备注说明
    is_active = Column(Boolean, default=False, nullable=False)  # 当前激活使用的配置
    print_enabled = Column(Boolean, default=False, nullable=False, comment="上线打印开关：开启后已付款订单自动推送到快递云打印")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
