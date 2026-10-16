from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.services.exchange_rate_service import fetch_and_save_rate
from app.services.order_sync import sync_orders
import logging
import pytz

logger = logging.getLogger(__name__)
# 定时任务的日志以前一行都打不出来(根 logger 没 handler, uvicorn 只管自己的), 跑没跑/报没报错全看不见。
# 只给本模块挂 handler, 不动 uvicorn 和根 logger, 免得日志重复。
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [scheduler] %(message)s"))
    logger.addHandler(_h)
logger.setLevel(logging.INFO)
logger.propagate = False

BJ = pytz.timezone('Asia/Shanghai')
scheduler = AsyncIOScheduler(timezone=BJ)


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
    # ⛔⛔ 每个 CronTrigger 都必须显式 timezone=BJ(2026-10-16 根治)。
    #   APScheduler 3.x 里【直接构造】的 CronTrigger 不传 timezone 时用的是容器本地时区(UTC),
    #   不会继承上面 AsyncIOScheduler(timezone=BJ)。以前全部没传 → 所有任务晚 8 小时:
    #   "9点汇率"实际北京 17:00 跑, "16号10:05结算"实际北京 18:05 才出账单(用户:为什么不是15号晚上出?)。
    # 每天早上9点更新汇率（北京时间）
    scheduler.add_job(_daily_exchange_rate, CronTrigger(hour=9, minute=0, timezone=BJ), id="daily_rate")
    # 每10分钟同步一次订单
    scheduler.add_job(_daily_order_sync, CronTrigger(minute='*/10', timezone=BJ), id="order_sync")
    # 每天凌晨3点半全量同步蔚蓝母库产品（保持产品库完整，防订单误判非供货）
    scheduler.add_job(_daily_product_sync, CronTrigger(hour=3, minute=30, timezone=BJ), id="product_sync")
    # 自动结算: 期末一过就出账单(用户 2026-10-16 要求「15号晚上自动出来」)。
    #   · 放在 16号/1号 00:15(北京): 周期含 15号/月底整天到 23:59:59, 赶在 23 点出会漏掉最后时段的单;
    #     00:00 和 00:10 两轮订单同步先把最后的单拉进来。
    #   · 汇率: 00:15 当天汇率还没抓(9点才抓), 结算逻辑会退回最近一条 = 期末当天(15号/月底)的汇率。
    #   · ⚠️ 2026-09-01踩坑: 和每10分钟的订单同步同一秒触发会抢掉自动结算 → 避开 :00/:10/:20,
    #     misfire_grace_time=3600(晚1小时内仍补跑) + coalesce=True(错过多次只补1次)。
    # 每月16号 00:15 自动结算 1-15号（北京时间）
    scheduler.add_job(_auto_settle, CronTrigger(day=16, hour=0, minute=15, second=0, timezone=BJ),
                      id="auto_settle_first_half", misfire_grace_time=3600, coalesce=True)
    # 每月1号 00:15 自动结算上月16号-月底（北京时间）
    scheduler.add_job(_auto_settle, CronTrigger(day=1, hour=0, minute=15, second=0, timezone=BJ),
                      id="auto_settle_second_half", misfire_grace_time=3600, coalesce=True)
    scheduler.start()
    for j in scheduler.get_jobs():
        logger.info(f"job {j.id} 下次运行: {j.next_run_time}")
    logger.info("Scheduler started with Beijing timezone (CST)")


def stop_scheduler():
    scheduler.shutdown()
