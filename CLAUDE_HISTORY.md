# 微盟香港对账系统 — 改动历史

> 详细改动按批次记录。最新在最上面。CLAUDE.md 是当前规范，本文件是历史轨迹。

---

## 第一批改动（2026-06-25 真金白银/储值区分 + 订单导出 + 分页总数 + 用户管理修复）

### 一、真金白银 / 储值抵扣区分（核心）
**背景**：倍赛思部分订单用储值（余额）支付，`payInfo.payAmount`=0 看起来"没收到钱"，但其实是客户用预存余额付的。需要区分"真金白银（新增现金到账）"和"储值抵扣（动用预存余额）"。

**微盟支付字段语义（实测逆向，重要）**：
- `payInfo.payAmount` = **真金白银**：客户在线实付现金，**已扣掉储值**（储值在微盟记账里算"折扣"，已从应付里减掉）
- `discountType=42` = **储值/余额抵扣**：`totalDiscounts` 里 type=42 的 `discountAmount` 合计
- `discountType=1` = 优惠券，`discountType=46` = 会员折扣 —— 这两类是**真折扣**（商家让利），不是钱
- **客户实际支付价（真实到账） = payAmount + 储值(type42)**；`totalAmount - 券 - 会员折扣 = payAmount + 储值`
- 全储值单特征：`payAmount=0` 必含大额 `type42`

**实现**：
- `models/order.py`：新增 `cash_paid`(真金白银) / `stored_value_paid`(储值) 两列（Numeric(12,2)）
- `main.py` lifespan：ALTER TABLE 加这两列（try/except 幂等）
- `services/order_sync.py`：`_extract_payment(order_info)` 解析；新单写入 + 老单每次同步刷新回填
- `schemas/order.py`：OrderResponse 暴露两字段
- `Orders.vue`：订单表加"真金白银/储值"列（绿色现金大字 + 橙色储值小字）

### 二、每日真金白银统计 `GET /orders/cash-daily`
- 按北京日期分组，排除测试单
- 返回每日 `cash`(真金白银) / `stored_value`(储值) / `full_sv_count`(全储值单数) / `refund_cash`(退款单现金)
- 汇总 `total_cash` / `total_stored_value` / `total_refund_cash` / `net_cash`(=cash-refund)
- 退款单现金单独计入 refund_cash，不从 cash 扣（cash=毛到账）
- `Orders.vue`：顶部绿色"💰真金白银到账"卡片 + "查看每日明细"展开表

### 三、订单明细导出 Excel `GET /orders/export`
- 按当前筛选条件（日期/状态/退款/结算/关键词）导全部，不分页
- 每商品一行；列：订单号/下单时间(北京)/收件人/电话/地址/商品/数量/供货单价/供货小计/客户支付/真金白银(整单)/储值抵扣(整单)/支付方式/发货状态/退款/结算状态
- 真金白银/储值是整单金额，只在订单首行显示，避免多商品行重复累计
- 末尾"合计(不含退款)"行：供货小计 + 真金白银 + 储值
- openpyxl 生成，蓝色表头 + 冻结首行 + 列宽；文件名 ASCII（避免 latin-1 报错）
- `api/index.js` `orders.exportUrl(params)` 拼查询串；`Orders.vue` "导出明细"按钮
- 支付方式判定：cash>0&sv>0=混合，仅sv=储值，否则现金

### 四、分页显示真实总数 `GET /orders/count`
- 之前分页只显示 1/2 不显示总页数，要点到第2页才知道还有更多
- 新增 count 端点返回筛选条件下订单总数
- `Orders.vue`：分页改为 `共 N 条 / M 页`，layout 加 jumper 可跳页

### 五、用户管理修复（auth.py / schemas/user.py / Users.vue）
1. **创建用户 500** — `users.email` 列有唯一索引，前端邮箱留空传 `""`，第二个空邮箱用户撞唯一约束(1062)。修复：create/update 时空 email/phone 归一化为 `NULL`，并加"邮箱已被占用"友好提示。历史脏数据 `email=""` 已清成 NULL。
2. **改不了角色** — `UserUpdate` schema 没有 `role` 字段、前端 `save()` 也没传 `role`，两层都把角色丢了 → 永远改不了。修复：schema 加 `role: Optional[UserRole]`，前端 update 带上 `role`。
3. 数据修正：李艳玲(id=2)原是 distributor，按用户本意改为 operator(运营)。

### 顺带
- `frontend/favicon.ico` / `frontend/logo.png` 资产纳入版本管理（index.html + Layout.vue 引用）
