from sqlalchemy import Column, Integer, Date, Numeric, String, DateTime
from sqlalchemy.sql import func
from app.database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    hkd_to_cny = Column(Numeric(8, 4), nullable=False, comment="1 HKD = ? CNY")
    cny_to_hkd = Column(Numeric(8, 4), nullable=False, comment="1 CNY = ? HKD")
    source = Column(String(50), default="api", comment="api / manual")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
