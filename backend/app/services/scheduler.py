from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.services.exchange_rate_service import fetch_and_save_rate
from app.services.order_sync import sync_orders
import logging
import pytz

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Shanghai'))


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


async def _daily_product_sync():
    """每天全量同步蔚蓝母库产品，保持产品库完整→订单条目正确匹配「我方供货」"""
    from app.services.product_sync import sync_master_products
    db = SessionLocal()
    try:
        result = await sync_master_products(db)
        logger.info(f"Daily product sync: {result}")
    except Exception as e:
        logger.error(f"Product sync failed: {e}")
    finally:
        db.close()


def _auto_settle():
    """自动结算任务（同步函数）"""
    from app.routers.settlements import auto_settle_period
    from app.core.deps import get_db

    db = SessionLocal()
    try:
        # 创建一个临时的管理员用户对象（绕过权限检查）
        from app.models.user import User, UserRole
        admin_user = User(id=0, username="system", role=UserRole.admin)

        result = auto_settle_period(db=db, _=admin_user)
        logger.info(f"Auto settlement completed: {result}")
    except Exception as e:
        logger.error(f"Auto settlement failed: {e}")
    finally:
        db.close()


def start_scheduler():
    # 每天早上9点更新汇率（北京时间）
    scheduler.add_job(_daily_exchange_rate, CronTrigger(hour=9, minute=0), id="daily_rate")
    # 每10分钟同步一次订单
    scheduler.add_job(_daily_order_sync, CronTrigger(minute='*/10'), id="order_sync")
    # 每天凌晨3点全量同步蔚蓝母库产品（保持产品库完整，防订单误判非供货）
    scheduler.add_job(_daily_product_sync, CronTrigger(hour=3, minute=30), id="product_sync")
    # ⚠️ 自动结算必须晚于 9 点汇率任务：结算要用当日汇率，0 点跑时今日汇率还没抓到会失败(2026-07-01踩坑)。
    #    放到 10 点，给汇率任务留足时间；结算逻辑也已加"退回最近可用汇率"兜底。
    # 每月16号上午10点自动结算1-15号（北京时间）
    scheduler.add_job(_auto_settle, CronTrigger(day=16, hour=10, minute=0, second=0), id="auto_settle_first_half")
    # 每月1号上午10点自动结算上月16号-月底（北京时间）
    scheduler.add_job(_auto_settle, CronTrigger(day=1, hour=10, minute=0, second=0), id="auto_settle_second_half")
    scheduler.start()
    logger.info("Scheduler started with Beijing timezone (CST)")


def stop_scheduler():
    scheduler.shutdown()
