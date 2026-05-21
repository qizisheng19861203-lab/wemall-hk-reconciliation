"""
微盟多店铺配置管理（仅 admin 可操作）
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.models.wemall_store_config import WemallStoreConfig
from app.models.user import User, UserRole
from app.core.deps import get_current_user

router = APIRouter(prefix="/admin/wemall-stores", tags=["wemall-stores"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class StoreCreate(BaseModel):
    name: str
    client_id: str
    client_secret: str
    shop_id: Optional[str] = None
    notes: Optional[str] = None


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    shop_id: Optional[str] = None
    notes: Optional[str] = None


class StoreOut(BaseModel):
    id: int
    name: str
    client_id: str
    client_secret_masked: str   # 只返回脱敏后的 secret
    shop_id: Optional[str]
    notes: Optional[str]
    is_active: bool

    class Config:
        from_attributes = True


def _mask(s: str) -> str:
    """返回脱敏字符串，如 ABC***XYZ"""
    if not s:
        return ""
    if len(s) <= 8:
        return s[:2] + "***"
    return s[:4] + "***" + s[-4:]


def _to_out(store: WemallStoreConfig) -> StoreOut:
    return StoreOut(
        id=store.id,
        name=store.name,
        client_id=store.client_id,
        client_secret_masked=_mask(store.client_secret),
        shop_id=store.shop_id,
        notes=store.notes,
        is_active=store.is_active,
    )


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    return current_user


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[StoreOut])
def list_stores(
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """列出所有店铺配置"""
    stores = db.query(WemallStoreConfig).order_by(WemallStoreConfig.id).all()
    return [_to_out(s) for s in stores]


@router.post("", response_model=StoreOut)
def create_store(
    body: StoreCreate,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """新增店铺配置"""
    store = WemallStoreConfig(
        name=body.name,
        client_id=body.client_id,
        client_secret=body.client_secret,
        shop_id=body.shop_id,
        notes=body.notes,
        is_active=False,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return _to_out(store)


@router.put("/{store_id}", response_model=StoreOut)
def update_store(
    store_id: int,
    body: StoreUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """更新店铺配置"""
    store = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="店铺配置不存在")

    if body.name is not None:
        store.name = body.name
    if body.client_id is not None:
        store.client_id = body.client_id
    if body.client_secret is not None:
        store.client_secret = body.client_secret
    if body.shop_id is not None:
        store.shop_id = body.shop_id
    if body.notes is not None:
        store.notes = body.notes

    db.commit()
    db.refresh(store)
    return _to_out(store)


@router.delete("/{store_id}")
def delete_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """删除店铺配置（不能删除激活中的配置）"""
    store = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="店铺配置不存在")
    if store.is_active:
        raise HTTPException(status_code=400, detail="不能删除当前激活的店铺配置，请先切换到其他店铺")

    db.delete(store)
    db.commit()
    return {"ok": True}


@router.post("/{store_id}/activate")
async def activate_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """切换激活店铺，同时验证凭证是否有效"""
    store = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="店铺配置不存在")

    # 验证新店铺凭证
    try:
        import httpx
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://dopen.weimob.com/fuwu/b/oauth2/token",
                data={
                    "client_id": store.client_id,
                    "client_secret": store.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            data = resp.json()
            if "access_token" not in data:
                raise HTTPException(status_code=400, detail=f"凭证验证失败：{data}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"网络请求失败：{str(e)}")

    # 取消所有激活，激活新的
    db.query(WemallStoreConfig).update({"is_active": False})
    store.is_active = True
    db.commit()
    db.refresh(store)

    return {"ok": True, "active_store": _to_out(store)}


@router.post("/{store_id}/test")
async def test_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    """测试店铺凭证并获取基本信息（不切换）"""
    store = db.query(WemallStoreConfig).filter(WemallStoreConfig.id == store_id).first()
    if not store:
        raise HTTPException(status_code=404, detail="店铺配置不存在")

    try:
        import httpx
        # 1. 获取 token
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://dopen.weimob.com/fuwu/b/oauth2/token",
                data={
                    "client_id": store.client_id,
                    "client_secret": store.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            data = resp.json()
            if "access_token" not in data:
                return {"ok": False, "error": f"Token 获取失败: {data}"}
            token = data["access_token"]

        # 2. 获取组织信息
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://dopen.weimob.com/apigw/bos/v2.0/organization/getList?accesstoken={token}",
                json={"pageNum": 1, "pageSize": 20},
            )
            org_data = resp.json()
            if org_data.get("code", {}).get("errcode") != "0":
                errmsg = org_data.get("code", {}).get("errmsg", "unknown")
                return {"ok": False, "error": f"获取组织信息失败: {errmsg}"}

            org_list = org_data.get("data", {}).get("data", [])
            org_info = org_list[0] if org_list else {}

        return {
            "ok": True,
            "token_prefix": token[:10] + "...",
            "vid": org_info.get("vid"),
            "org_name": org_info.get("name") or org_info.get("orgName"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
