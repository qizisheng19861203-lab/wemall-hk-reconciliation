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
    import subprocess
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    CST = timezone(timedelta(hours=8))

    # 优先读取构建时写入的版本信息
    build_number = None
    commit_sha = None

    # 查找 BUILD_NUMBER 文件（在 backend/ 目录下）
    base_dir = Path(__file__).parent.parent  # backend/
    build_file = base_dir / 'BUILD_NUMBER'
    sha_file = base_dir / 'COMMIT_SHA'

    try:
        if build_file.exists():
            build_number = build_file.read_text().strip()
    except Exception as e:
        print(f"Failed to read BUILD_NUMBER: {e}")

    try:
        if sha_file.exists():
            commit_sha = sha_file.read_text().strip()[:7]  # 短格式
    except Exception as e:
        print(f"Failed to read COMMIT_SHA: {e}")

    # 如果文件不存在，尝试从 git 获取
    if not commit_sha:
        try:
            git_hash = subprocess.check_output(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=os.path.dirname(__file__), stderr=subprocess.DEVNULL
            ).decode().strip()
            commit_sha = git_hash
        except Exception:
            pass

    # 获取更新时间
    try:
        git_time_raw = subprocess.check_output(
            ['git', 'log', '-1', '--format=%ct'],
            cwd=os.path.dirname(__file__), stderr=subprocess.DEVNULL
        ).decode().strip()
        update_dt = datetime.fromtimestamp(int(git_time_raw), tz=CST)
        update_time = update_dt.strftime("%Y-%m-%d %H:%M CST")
    except Exception:
        now = datetime.now(CST)
        update_time = now.strftime("%Y-%m-%d %H:%M CST")

    # 构造版本号显示
    if build_number and commit_sha:
        version = f"#{build_number} ({commit_sha})"
    elif commit_sha:
        version = commit_sha
    elif build_number:
        version = f"#{build_number}"
    else:
        now = datetime.now(CST)
        version = now.strftime("%Y%m%d-%H%M%S")

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
