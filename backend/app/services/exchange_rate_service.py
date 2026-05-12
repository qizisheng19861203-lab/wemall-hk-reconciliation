import httpx
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.config import settings
from app.models.exchange_rate import ExchangeRate


async def fetch_and_save_rate(db: Session, target_date: date = None) -> ExchangeRate:
    target_date = target_date or date.today()

    async with httpx.AsyncClient(timeout=10) as client:
        url = f"{settings.EXCHANGE_RATE_API_URL}/{settings.EXCHANGE_RATE_API_KEY}/pair/HKD/CNY"
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        hkd_to_cny = Decimal(str(data["conversion_rate"])).quantize(Decimal("0.0001"))

    cny_to_hkd = (Decimal(1) / hkd_to_cny).quantize(Decimal("0.0001"))
    existing = db.query(ExchangeRate).filter(ExchangeRate.date == target_date).first()
    if existing:
        existing.hkd_to_cny = hkd_to_cny
        existing.cny_to_hkd = cny_to_hkd
        existing.source = "api"
        db.commit()
        db.refresh(existing)
        return existing

    rate = ExchangeRate(date=target_date, hkd_to_cny=hkd_to_cny, cny_to_hkd=cny_to_hkd, source="api")
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate
