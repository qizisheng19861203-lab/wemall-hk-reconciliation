from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.services.exchange_rate_service import fetch_and_save_rate
from app.services.order_sync import sync_orders
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _daily_exchange_rate():
    db = SessionLocal()
    try:
        rate = await fetch_and_save_rate(db)
        logger.info(f"Daily exchange rate updated: HKD/CNY = {rate.hkd_to_cny}")
    except Exception as e:
        logger.error(f"Failed to fetch exchange rate: {e}")
    finally:
        db.close()


async def _daily_order_sync():
    db = SessionLocal()
    try:
        result = await sync_orders(db)
        logger.info(f"Daily order sync: {result}")
    except Exception as e:
        logger.error(f"Order sync failed: {e}")
    finally:
        db.close()


def start_scheduler():
    # 每天早上9点更新汇率
    scheduler.add_job(_daily_exchange_rate, CronTrigger(hour=9, minute=0), id="daily_rate")
    # 每10分钟同步一次订单
    scheduler.add_job(_daily_order_sync, CronTrigger(minute='*/10'), id="order_sync")
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown()
