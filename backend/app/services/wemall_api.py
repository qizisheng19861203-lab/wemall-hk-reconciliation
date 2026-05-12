import httpx
import hashlib
import time
import json
from app.config import settings


class WemallAPI:
    """微盟开放平台API封装"""

    def __init__(self):
        self.app_key = settings.WEMALL_APP_KEY
        self.app_secret = settings.WEMALL_APP_SECRET
        self.shop_id = settings.WEMALL_SHOP_ID
        self.base_url = settings.WEMALL_API_BASE

    def _sign(self, params: dict) -> str:
        sorted_params = sorted(params.items())
        param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        sign_str = self.app_secret + param_str + self.app_secret
        return hashlib.md5(sign_str.encode()).hexdigest().upper()

    def _build_params(self, method: str, biz_content: dict) -> dict:
        params = {
            "method": method,
            "appKey": self.app_key,
            "timestamp": str(int(time.time() * 1000)),
            "v": "1.0",
            "shopId": self.shop_id,
            "bizContent": json.dumps(biz_content),
        }
        params["sign"] = self._sign(params)
        return params

    async def _request(self, method: str, biz_content: dict) -> dict:
        params = self._build_params(method, biz_content)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/openapi/", data=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                raise Exception(f"微盟API error: {data.get('errmsg', 'unknown')}")
            return data.get("data", {})

    async def get_products(self, page: int = 1, page_size: int = 100) -> list:
        result = await self._request("product.getProductList", {
            "page": page,
            "pageSize": page_size,
            "shopId": self.shop_id,
        })
        return result.get("items", result if isinstance(result, list) else [])

    async def get_orders(self, start_time: str, end_time: str, page: int = 1, page_size: int = 50) -> dict:
        result = await self._request("trade.getOrderList", {
            "startTime": start_time,
            "endTime": end_time,
            "page": page,
            "pageSize": page_size,
            "shopId": self.shop_id,
        })
        return result

    async def get_order_detail(self, order_id: str) -> dict:
        result = await self._request("trade.getOrderDetail", {
            "orderId": order_id,
            "shopId": self.shop_id,
        })
        return result
