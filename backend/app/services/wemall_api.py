import httpx
import json
from typing import Optional
from app.config import settings


def get_active_wemall_credentials() -> dict:
    """
    从数据库获取当前激活的微盟店铺配置。
    若 DB 中无激活配置则回落到 .env 中的默认值。
    返回 {"client_id": ..., "client_secret": ..., "shop_id": ...}
    """
    try:
        from app.database import SessionLocal
        from app.models.wemall_store_config import WemallStoreConfig
        db = SessionLocal()
        try:
            active = db.query(WemallStoreConfig).filter(WemallStoreConfig.is_active == True).first()
            if active:
                return {
                    "client_id": active.client_id,
                    "client_secret": active.client_secret,
                    "shop_id": active.shop_id or "",
                    "store_name": active.name,
                }
        finally:
            db.close()
    except Exception as e:
        print(f"[WemallAPI] get_active_wemall_credentials fallback to .env: {e}")

    # Fallback to .env
    return {
        "client_id": settings.WEMALL_APP_KEY,
        "client_secret": settings.WEMALL_APP_SECRET,
        "shop_id": settings.WEMALL_SHOP_ID,
        "store_name": "默认店铺",
    }


class WemallAPI:
    """微盟云开放平台 API v2.0 封装"""

    def __init__(self, client_id: str = None, client_secret: str = None, shop_id: str = None):
        """
        优先使用传入的凭证；若不传则从 DB 激活配置读取，再回落 .env。
        """
        if client_id and client_secret:
            self.client_id = client_id
            self.client_secret = client_secret
            self.shop_id = shop_id or ""
        else:
            creds = get_active_wemall_credentials()
            self.client_id = creds["client_id"]
            self.client_secret = creds["client_secret"]
            self.shop_id = creds["shop_id"]

        self.base_url = "https://dopen.weimob.com/apigw/weimob_shop/v2.0"
        self._access_token: Optional[str] = None
        self._business_id: Optional[str] = None
        self._org_vid: Optional[int] = None

    async def _get_access_token(self) -> str:
        """获取 access_token（使用 client_credentials 授权）"""
        if self._access_token:
            return self._access_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://dopen.weimob.com/fuwu/b/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if "access_token" not in data:
                raise Exception(f"获取 access_token 失败: {data}")

            self._access_token = data["access_token"]
            self._business_id = data.get("business_id", self.shop_id)
            return self._access_token

    async def _get_organization_vid(self) -> int:
        """获取组织 vid（通过 bos/organization/getList 接口）"""
        if self._org_vid:
            return self._org_vid

        token = await self._get_access_token()
        url = f"https://dopen.weimob.com/apigw/bos/v2.0/organization/getList?accesstoken={token}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"pageNum": 1, "pageSize": 20})
            resp.raise_for_status()
            data = resp.json()

            if data.get("code", {}).get("errcode") != "0":
                errmsg = data.get("code", {}).get("errmsg", "unknown")
                raise Exception(f"获取组织列表失败: {errmsg}")

            # 响应结构: data.data[].vid
            org_list = data.get("data", {}).get("data", [])
            if not org_list:
                raise Exception("组织列表为空，请检查店铺配置")

            self._org_vid = org_list[0].get("vid")
            return self._org_vid

    async def _request(self, endpoint: str, payload: dict) -> dict:
        """统一请求方法"""
        token = await self._get_access_token()
        url = f"{self.base_url}/{endpoint}?accesstoken={token}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code", {}).get("errcode") != "0":
                errmsg = data.get("code", {}).get("errmsg", "unknown")
                raise Exception(f"微盟 API 错误: {errmsg}")

            return data.get("data", {})

    async def get_products(self, page: int = 1, page_size: int = 50) -> dict:
        """获取商品列表"""
        await self._get_access_token()

        # 获取正确的组织 vid
        vid = await self._get_organization_vid()

        payload = {
            "pageNum": page,
            "pageSize": page_size,
            "queryParameter": {
                "goodsStatus": 0,
                "searchType": 1,
            },
            "basicInfo": {
                "vid": vid,
            },
        }
        return await self._request("goods/getList", payload)

    async def get_orders(
        self,
        start_time: int,
        end_time: int,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """获取订单列表"""
        vid = await self._get_organization_vid()
        payload = {
            "pageNum": page,
            "pageSize": page_size,
            "queryParameter": {
                "searchType": 8,
                "queryTime": {
                    "startTime": start_time,
                    "endTime": end_time,
                    "type": 1,  # 1=按创建时间查询（0会被API误识别为null）
                },
                "orderDomains": [1, 2, 3],
            },
            "basicInfo": {
                "vid": vid,
            },
        }
        return await self._request("order/list/search", payload)

    async def get_order_detail(self, order_no: str) -> dict:
        """获取订单详情"""
        vid = await self._get_organization_vid()
        payload = {
            "orderNo": order_no,
            "orderDomains": [1, 2, 3],
            "basicInfo": {
                "vid": vid,
            },
        }
        return await self._request("order/detail/get", payload)

    async def get_goods_categories(self) -> list:
        """获取商品类目列表"""
        vid = await self._get_organization_vid()
        result = await self._request("goods/category/getList", {
            "basicInfo": {"vid": vid},
        })
        return result.get("goodsCategoryInfoList", [])

    async def get_goods_templates(self) -> list:
        """获取商详模板列表"""
        vid = await self._get_organization_vid()
        result = await self._request("goods/goodtemplate/getList", {
            "pageNum": 1,
            "pageSize": 50,
            "basicInfo": {"vid": vid},
        })
        return result.get("pageList", [])

    async def get_fulfill_types(self) -> list:
        """获取配送方式列表"""
        vid = await self._get_organization_vid()
        result = await self._request("fulfill/goods/fulfilltype/getList", {
            "basicInfo": {"vid": vid},
        })
        return result.get("nodeDeliveryDtoList", [])

    async def create_goods(self, payload: dict) -> dict:
        """创建商品（添加在售商品）"""
        return await self._request("goods/create", payload)

    async def get_employee_wid(self) -> int:
        """获取管理员 wid（通过 employee/getList）"""
        token = await self._get_access_token()
        url = f"https://dopen.weimob.com/apigw/bos/v2.0/employee/getList?accesstoken={token}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"pageNum": 1, "pageSize": 10})
            resp.raise_for_status()
            data = resp.json()
            if data.get("code", {}).get("errcode") != "0":
                raise Exception(f"获取员工列表失败: {data.get('code', {}).get('errmsg')}")
            employees = data.get("data", {}).get("data", [])
            if not employees:
                raise Exception("员工列表为空")
            return employees[0].get("wid")

    async def get_freight_templates(self) -> list:
        """获取商家配送运费模板列表"""
        vid = await self._get_organization_vid()
        result = await self._request("fulfill/freight/merchant/template/getList", {
            "basicInfo": {"vid": vid},
        })
        default_tpl = result.get("defaultFreightTemplate")
        custom_list = result.get("freightTemplateList", [])
        all_templates = []
        if default_tpl:
            all_templates.append(default_tpl)
        all_templates.extend(custom_list)
        return all_templates

    async def get_product_detail(self, goods_id: str) -> dict:
        """获取商品详情（含规格/SKU/库存/图片/详情）"""
        vid = await self._get_organization_vid()
        payload = {
            "goodsId": int(goods_id),
            "basicInfo": {
                "vid": vid,
            },
        }
        return await self._request("goods/get", payload)

    async def get_all_on_sale_products(self) -> list:
        """分页拉取所有在售商品列表（goodsStatus=1）"""
        vid = await self._get_organization_vid()
        all_items = []
        page = 1
        while True:
            result = await self._request("goods/getList", {
                "pageNum": page,
                "pageSize": 20,
                "queryParameter": {"goodsStatus": 1, "searchType": 1},
                "basicInfo": {"vid": vid},
            })
            items = result.get("pageList", [])
            if not items:
                break
            all_items.extend(items)
            total = result.get("totalCount", 0)
            if page * 20 >= total:
                break
            page += 1
        return all_items

    async def update_goods_cost_price(self, goods_id: int, sku_updates: list) -> dict:
        """更新商品成本价（goods/price/update）。
        sku_updates: [{"skuId": N, "salePrice": x, "costPrice": y}, ...]
        """
        vid = await self._get_organization_vid()
        return await self._request("goods/price/update", {
            "goodsId": goods_id,
            "basicInfo": {"vid": vid},
            "skuList": sku_updates,
        })
