import httpx
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.exchange_rate import ExchangeRate


async def fetch_and_save_rate(db: Session, target_date: date = None) -> ExchangeRate:
    target_date = target_date or date.today()

    hkd_to_cny = await _fetch_hkd_cny_rate()

    cny_to_hkd = (Decimal(1) / hkd_to_cny).quantize(Decimal("0.0001"))
    existing = db.query(ExchangeRate).filter(ExchangeRate.date == target_date).first()
    if existing:
        existing.hkd_to_cny = hkd_to_cny
        existing.cny_to_hkd = cny_to_hkd
        existing.source = "hkma"
        db.commit()
        db.refresh(existing)
        return existing

    rate = ExchangeRate(date=target_date, hkd_to_cny=hkd_to_cny, cny_to_hkd=cny_to_hkd, source="hkma")
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


async def _fetch_hkd_cny_rate() -> Decimal:
    """从多个免费数据源获取 HKD→CNY 汇率，依次尝试"""
    errors = []

    # 数据源1：香港金管局 HKMA（官方，免费，无需Key）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.hkma.gov.hk/public/market-data-and-statistics/monthly-statistical-bulletin/er-ir/exchange-rates-daily",
                params={"segment": "daily", "choose": "hkd_cny", "sortby": "end_of_date", "sortorder": "desc", "offset": 0, "limit": 1},
            )
            resp.raise_for_status()
            data = resp.json()
            records = data.get("result", {}).get("records", [])
            if records:
                rate_val = records[0].get("hkd_cny")
                if rate_val:
                    return Decimal(str(rate_val)).quantize(Decimal("0.0001"))
    except Exception as e:
        errors.append(f"HKMA: {e}")

    # 数据源2：Frankfurter（欧洲央行数据，免费，无需Key）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.frankfurter.app/latest", params={"from": "HKD", "to": "CNY"})
            resp.raise_for_status()
            data = resp.json()
            rate_val = data.get("rates", {}).get("CNY")
            if rate_val:
                return Decimal(str(rate_val)).quantize(Decimal("0.0001"))
    except Exception as e:
        errors.append(f"Frankfurter: {e}")

    # 数据源3：Open Exchange Rates 免费端点（USD为基准，换算）
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://open.er-api.com/v6/latest/HKD")
            resp.raise_for_status()
            data = resp.json()
            rate_val = data.get("rates", {}).get("CNY")
            if rate_val:
                return Decimal(str(rate_val)).quantize(Decimal("0.0001"))
    except Exception as e:
        errors.append(f"OpenER: {e}")

    raise RuntimeError(f"所有汇率数据源均失败: {'; '.join(errors)}")
