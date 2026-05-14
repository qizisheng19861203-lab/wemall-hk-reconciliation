import httpx
import json
from typing import Optional
from app.config import settings


class WemallAPI:
    """微盟云开放平台 API v2.0 封装"""

    def __init__(self):
        self.client_id = settings.WEMALL_APP_KEY
        self.client_secret = settings.WEMALL_APP_SECRET
        self.shop_id = settings.WEMALL_SHOP_ID
        self.base_url = "https://dopen.weimob.com/apigw/weimob_shop/v2.0"
        self._access_token: Optional[str] = None

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
            return self._access_token

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
        payload = {
            "pageNum": page,
            "pageSize": page_size,
            "queryParameter": {
                "goodsStatus": 0,  # 0=全部
                "searchType": 1,
            },
            "basicInfo": {
                "vid": int(self.shop_id),
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
        """获取订单列表

        Args:
            start_time: 开始时间戳（毫秒）
            end_time: 结束时间戳（毫秒）
            page: 页码
            page_size: 每页数量
        """
        payload = {
            "pageNum": page,
            "pageSize": page_size,
            "queryParameter": {
                "searchType": 8,  # 按时间查询
                "queryTime": {
                    "startTime": start_time,
                    "endTime": end_time,
                    "type": 0,  # 0=下单时间
                },
                "orderDomains": [1, 2, 3],  # 查询商品详情
            },
        }
        return await self._request("order/list/search", payload)

    async def get_order_detail(self, order_no: str) -> dict:
        """获取订单详情"""
        payload = {
            "orderNo": order_no,
            "orderDomains": [1, 2, 3],
        }
        return await self._request("order/detail/get", payload)
