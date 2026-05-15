from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.config import settings
from app.database import Base, engine
from app.routers.auth import router as auth_router, users_router
from app.routers.products import router as products_router
from app.routers.orders import router as orders_router
from app.routers.settlements import router as settlements_router, rates_router
from app.routers.reports import router as reports_router
from app.services.scheduler import start_scheduler, stop_scheduler
import app.models  # ensure all models are imported for table creation


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(orders_router, prefix="/api")
app.include_router(settlements_router, prefix="/api")
app.include_router(rates_router, prefix="/api")
app.include_router(reports_router, prefix="/api")


@app.get("/health")
def health():
    import os
    from datetime import datetime
    # 使用文件修改时间作为版本标识
    mtime = os.path.getmtime(__file__)
    version = datetime.fromtimestamp(mtime).strftime("%Y%m%d-%H%M%S")
    update_time = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": version,
        "update_time": update_time,
        "wemall_api_configured": bool(settings.WEMALL_APP_KEY),
    }


@app.get("/debug/wemall-config")
def debug_wemall_config():
    """调试端点：查看微盟 API 配置"""
    from app.services.wemall_api import WemallAPI
    api = WemallAPI()
    return {
        "base_url": api.base_url,
        "client_id": api.client_id[:10] + "..." if api.client_id else None,
        "shop_id": api.shop_id,
    }
