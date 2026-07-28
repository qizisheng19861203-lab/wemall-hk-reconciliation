# 微盟香港对账系统 — 改动历史

> 详细改动按批次记录。最新在最上面。CLAUDE.md 是当前规范，本文件是历史轨迹。

---

## 第六批改动（2026-07-10 会话失效卡死修复 + 令牌10年 + 产品库机构价泄露修复）

### 一、运营导出报"导出失败(401)"根因 = 会话失效卡死（非权限、非导出bug）
- **现象**：运营点导出报 401；查日志发现她**所有**请求全 403（列表/统计/今日），只有导出 401。她看到的页面是旧缓存残留，实际每点必失败。
- **根因**：令牌丢失/过期时，HTTPBearer 无凭证→后端返 **403**"Not authenticated"，但前端 `http.js` 拦截器**只处理 401 跳登录、漏了 403** → 运营卡在"看着正常、点啥都失败"的坏页面，不知道要重登。导出走裸 fetch 发了 `Bearer null`→401。
- **修复**：`http.js` 拦截器把"未认证的 403"(detail 含 Not authenticated)也当成需重登→清令牌跳 `/login`；有效令牌但权限不足的 403(如运营点管理员接口)不跳转只提示。`Orders.vue exportExcel` 令牌缺失/401/403 时清令牌+跳登录+提示"登录已过期，请重新登录"。
- **验证**：运营新令牌实测 orders/stats/today/export/settlements 全 200。

### 二、令牌有效期 24 小时 → 10 年
- `config.py ACCESS_TOKEN_EXPIRE_MINUTES` = `60*24*365*10`（内部专用系统，免频繁重登）。⚠️ 旧令牌有效期出生即定死，改后需各账号**重新登录一次**才拿到 10 年令牌。

### 三、🔴 产品库机构价泄露修复（验证时逮到）
- `GET /products`(list_products) 原用 `get_current_user` → **运营/分销商直接调 API 能拉到全产品库含机构价/供货价**（前端只 adminOnly 藏菜单，后端没拦）。已改 `require_admin`。实测运营打 /products 现在 403。
- 复核：products.py 其余端点全 require_admin；orders 各端点 get_current_user 是对的（运营对账需看供货额）；结算 confirm/delete 是 require_admin（运营不能改结算）；PDF 下载 get_current_user 正确（角色表允许下载）。**前端 adminOnly 只是表面，后端 Depends 才是真权限。**

---

## 第八批改动（2026-07-16 倍赛思商品详情同步：发现专用安全接口 goods/description/update）

**需求**：倍赛思甄选上我方供货的产品，好几个详情(goodsDesc)不完整（当时创建/粘贴只截了一部分），要从蔚蓝母库同步完整详情，且**绝不能动价格/成本/库存/分类/上架**。

### 一、🔑 关键发现：`goods/description/update` 专用改详情接口
- **绝不能用 `goods/update` 改详情**——它是整体覆盖，实测有两个副作用：① `skuStockNum` 是**增量**（传36→库存翻倍成72）② 会**清空店铺分类** `goodsClassifyList`（我传的字段名不被接受）。
- 探测发现微盟有专用接口 **`goods/description/update`**（参数只要 `goodsId` + `basicInfo.vid` + `goodsDesc`）——实测**只改详情，价格/成本/库存/分类/上架/图片分毫不动**。已封装为 `wemall_api.update_goods_description(goods_id, desc)`。
- 附带学到（万一要用 goods/update）：分类字段是 `goodsClassifyIdList`，库存增量传 0 才不变。测试品小球藻(177354386569)被 goods/update 弄乱的库存(kuaidi同步自动修回36)和分类(手动用 goodsClassifyIdList 恢复)都已修复。

### 二、批量同步结果
- 扫描倍赛思 269 个商品：**我方供货且详情不完整 43 个**（220个已完整、4个非我方供货、1个无蔚蓝档）。判定"不完整"= 蔚蓝 goodsDesc 比倍赛思长 >1000 字符。最大缺口 +71080（乳腺保护因子只录了26%）。
- 用 `goods/description/update` 逐个把蔚蓝完整详情推到倍赛思，每个产品前后快照验证：**43 个全部成功，0 失败，0 副作用**（价格/成本/库存/分类/上架全不变，只详情变长）。
- 匹配用 UPC：倍赛思 outerGoodsCode → 产品库 Product.sku → 产品库 wemall_product_id = 蔚蓝 goodsId。

### 三、教训（写死铁律）
- **同步详情永远用 `goods/description/update`，绝不用 `goods/update`**（后者整体覆盖，动库存+清分类）。
- 长时间微盟批量操作用**后台 detached 脚本 + 写文件 + Monitor 轮询**，别用 SSH 一次性长跑（会话易断；且服务器 sshd 对频繁连接会掐断，遵新加坡命脉铁律不重连风暴）。

---

## 第七批改动（2026-07-16 ADEK建档遗漏修正 + 零供货价告警机制）

### 一、青少年ADEK建档遗漏 → 第一期账单更正（数据修正）
- **根因**：青少年版ADEK（UPC `879452100084`，255元）未在对账产品库建档 → order_sync 匹配不上 → 118件里62件经goodsId fallback误配到成人ADEK(id=115)按300结、56件按0结。成人版(`8794521000842`,300元)一直正确(259件@300)，两者未混（sku条目交集=0）。
- **修**：新建产品 id=979(sku 879452100084, 供货价255, 取倍赛思goodsId 149184271799679)；把第一期(#3)+第二期(#4)+未结算里所有该sku条目改为255。
- **结算单就地更新(保留发票号)**：改条目后 `total=Σ挂单条目supply_subtotal`(快照口径，不加is_refunded过滤，否则会把结算后才退款的单误剔缩水)。第一期 #3 `1,479,007.37 → 1,490,497.37`(+11,490)，HKD 1,719,738.51；第二期 #4 → 177,056.36。
- **给倍赛思的更正对照说明**已做成 artifact（对比图：成人259件不变 vs 青少年118件更正）。

### 二、全系统零供货价彻查
- 扫所有账单+订单：我方供货却0价 = **0**（全清）。剩余0价全是Ani系列(`934978600xxxx`)=倍赛思自营，非我方供货，0价可接受。
- 判定"我方供货"：sku 在产品库有档 或 在倍赛思供货价Excel(264产品)里。

### 三、🔴 零供货价告警机制（防复发，`GET /orders/price-alerts`）
- 后端扫本店非测试非退款订单里 supply_price 0/空 的条目，按sku聚合分两类：
  - **red = sku在产品库有档(=我方供货)却0价** → 绝对禁止(亏钱)，必须补。
  - **yellow = sku产品库无档** → 疑似倍赛思自营(Ani)或漏建的我方产品，需人工确认。
- 前端 `Orders.vue` 顶部：red>0 显示红色 el-alert(列出产品+未结/已结件数+库价/需录价提示)；yellow>0 显示黄色温和提示。仅管理员(`auth.isAdmin`)可见；随页面加载+10分钟自动刷新+手动刷新。`api/index.js orders.priceAlerts()`。
- 当前 red=0（干净），yellow=3(Ani)。以后任何我方产品出现0价会即时红标。

---

## 第五批改动（2026-07-03 对账全量审计 + "问题订单"入口）

用户要求审计"钱有没有算对"。代码级+数据级双重核对，结论：**核心算钱正确**（0 条小计错误、结算单#3重算完全一致、支付金额抽样80单0误差、无供货价≥零售价、无重复订单）。修了几处非致命但影响金额完整性的问题，并新增"问题订单"入口。

### 一、供货价回填遗漏（审计发现，已修 + 已回填）
- **根因**：`order_sync` 补录 supply_price 只在 `product_id 从空→有` 时执行；一旦 product_id 已设、supply_price 却为空（产品当时还没机构价），后续同步**永远补不上**。导致"产品库明明有机构价，订单条目却是待录价"。
- **修复**：`order_sync` 改为——解析产品后，只要产品库有价、条目没价就补（不再限定 product_id 从空→有）。
- **一次性回填**：未结算订单里补了 16 条明细，追回可结算供货额 ¥7,210.70。剩 3 条是 2 个真没录价的产品（VSL3益生菌 `271213608102721`、VASCEPA鱼油 `277657312102721`）。

### 二、回填只补未结算订单（防账实不符）
- `products.py` `update_product` + `import_supply_price` 的待录价回填加 `Order.settlement_id IS NULL` 过滤——**已结算订单的金额已开票，回填会让结算单总额≠订单明细**。`order_sync` 同类回填也已加 `settlement_id is None` 守卫。

### 三、"问题订单"入口（已发货却退款，需追回）
- **背景**：104 张未结算退款单里，多数是"部分售后+退储值+货没退(returnNum=0)"。用户决定：这些都当退款、不进供货款；但要一个入口盯"货已发却退款"的单。
- **⚠️ 关键坑**：对账系统的 `shipping_status` 是从微盟订单状态推的，**对退款单不可靠**——全退单会被微盟标成"已完成"→ 误判"已签收/已发货"。第一版 tab 用它筛出 40 单，实测 **34 单是假阳性**（打印系统根本没物流单号=货没真发，如 coffee 单）。
- **正确做法（已实现）**：真发货以**物流单号**为准，而单号只在打印系统里（微盟 list 接口不返回、对账 raw_data 里也没有）。
  - **打印系统**新增 `GET /api/inventory/beisi_shipped_waybills?secret=bp_toggle_2026_wm`（已加入 auth 豁免白名单）→ 返回倍赛思 `{order_no: waybill}`（review_status.waybill / third_party_waybill 任一非空）。
  - **对账系统** `GET /orders/problem-refunds`：`_fetch_beisi_waybills()` httpx 拉上面接口，只列"已退款 且 打印系统真有物流单号"的单，直接展示单号。数据源拉不到时返回 `waybill_source_ok=false`（前端提示，宁可少列不误列）。
  - 前端新页 `ProblemOrders.vue` + 路由 `/problem-orders`(adminOnly) + 菜单"⚠️ 问题订单"。红色统计卡 + 表格(订单号/收件人/时间/物流单号/供货值) + 可展开看商品明细。
- **结果**：准确筛出 **6 单**真"已发货+退款"（供货值 ¥20,266），各带 SF/OC 单号。

### 四、退款处理口径（确认无误）
- 退款单（is_refunded，rightsInfos 含 rightsStatus=2）**整单**排除结算，保守（绝不多收）。用户确认这些不追供货款。"待发货就退款"的 59 单货没发、退了无损失。

---

## 第四批改动（2026-07-01 产品同步撞唯一键崩溃修复：母库重复UPC）

**现象**：点"同步蔚蓝产品"报 502 `(1062, "Duplicate entry '123779020102721' for key 'products.ix_products_wemall_product_id'")`，新建的产品一个都导不进来（整批崩溃）。

**根因**：产品库有一对重复产品（id=941/947，都是"念珠菌全效配方"，同 UPC `855571001051`，但 wemall_product_id 不同）。因为**蔚蓝母库把同一个 UPC 挂在了两个 goodsId 上**（旧 `123774049102721` + 用户新建的 `123779020102721`）。同步按 SKU 匹配到 941（`.first()` 取 id 最小），却盲目 `ex.wemall_product_id = gid` 把 941 改成 947 已占用的 gid → `wemall_product_id` 唯一索引撞 1062 → 整批同步事务崩溃。

**修复（product_sync.py `sync_master_products` + products.py `sync_products_by_ids` 两处）**：赋值 `wemall_product_id` 前先查是否有**别的产品**已占用该 gid（`filter(wemall_product_id==gid, id!=ex.id)`），占用了就**跳过赋值、不覆盖**，避免撞唯一键。总额/匹配不受影响。

**数据清理**：删除孤立重复行 id=947（确认 `order_items` 无任何引用，安全）。清理后全库重复 SKU 组=0。重跑同步：created 2 / updated 995 / 共 997，无崩溃，新产品成功导入。

**遗留（用户侧）**：蔚蓝母库 UPC `855571001051` 仍挂在两个 goodsId 上（用户新建产品时复用了已存在 UPC）。建议每个新产品用唯一 UPC，或去蔚蓝删重复——否则该记录的 wemall_product_id 会在两个 goodsId 间来回跳（无害，仅不干净）。

---

## 第三批改动（2026-07-01 结算三修：未录价漏结7万 + 汇率兜底 + 自动结算时序）

**背景**：7/1 结算管理页无自动账单，用户问为何 6/16–6/30 那期没自动 loading 出来。排查发现自动结算 0 点跑时报 `今日汇率未录入`，且逻辑有漏结 bug。

### 一、未录价拦截 bug（最关键，漏结 ¥70,894）
- **旧逻辑**：`create_settlement` + `auto_settle_period` 都用 `any(it.supply_subtotal is None)` 判断——只要一单有任何未录价商品就整单拦截/跳过。
- **bug**：`supply_subtotal is None` 有两种来源——① 我方产品待录价（该等）② **倍赛思自营品**（`product_id` 为空、我们不供货、本就该按 0）。把②也当"待录价"→ 含自营品的**混合单**里我方那部分货款被一起跳过。6/16–6/30 有 26 张混合单，漏结 **¥70,894.19**（应结 1,479,007.37，旧逻辑只会结出 1,408,113.18）。
- **修复**：新增 `_order_has_our_unpriced(o)` = `any(it.product_id is not None and it.supply_subtotal is None)`。只有"我方产品未录价"才拦/跳整单；非我方供货自营品按 0 处理、不影响整单结算。两处结算都改用它。总额仍 `sum(supply_subtotal or 0)`（自营品贡献 0）。

### 二、汇率硬失败 → 兜底
- **旧**：`auto_settle_period` 硬要求 `ExchangeRate.date == 今日`，没有就 400 `今日汇率未录入`。
- **修**：新增 `_latest_rate(db, today)`——今日没有则**退回最近一条可用汇率**，只有系统零汇率记录才报错。
- 今日(7/1)汇率缺失根因：9 点汇率自动抓取偶发失败（源头正常，实测能抓到 0.8667），无重试。已手动补 7/1=0.8667。

### 三、自动结算时序（根治 0 点必失败）
- `scheduler.py`：自动结算从 `hour=0` 挪到 **`hour=10`**（每月 1/16 号）——晚于 9 点汇率任务，确保结算时当日汇率已就位。配合汇率兜底双保险。

### 生成结果
- 手动生成 6/16–6/30 账单：`INV20260701QA3V`，671 单，净供货 **¥1,479,007.37**，应付 HKD 1,706,481.33（0.8667），状态待确认。
- ⚠️ `auto_settle_period` 完成后**自动发账单邮件**给启用+有邮箱的通知联系人——当前仅 `蔚蓝医学 332771759@qq.com`（=系统发件邮箱本身，内部自留，无外发）。
- 结算后剩余未结算=今日(7/1) 5 单 ¥2,637。671 单含 57 张纯自营单（贡献 0 但一并 settlement_id 置位，清掉"永久未结算"）。

---

## 第二批改动（2026-06-30 订单页"今日"统计卡片 + 供货额/真金白银归属标注）

### 一、今日统计卡片 `GET /orders/today`
- 订单页顶部"本月"卡片下方新增**常驻蓝色"今日"卡片**，不受上方区间选择影响，显示：今日订单数 / 供货额 / 真金白银 / 储值抵扣(>0才显示) / 退款(>0才显示)。
- **北京时区正确**：`order_date` 存 naive UTC，北京今日 00:00 = UTC 今日-8h，据此过滤避免漏掉北京 0–8 点的单（`bj_midnight - timedelta(hours=8)`）。排除测试单；退款单不计入订单数/供货额，单列退款。
- 随页面 10 分钟自动刷新 + "刷新今日"按钮；`api/index.js` `orders.today()`；`Orders.vue` `loadToday()` 接入 onMounted/refreshStats/autoRefresh。

### 二、供货额 vs 真金白银 归属标注（用户混淆 → 澄清）
- **用户疑问**：今日供货额 5604 < 真金白银 10176，为何供货额低于真金白银？
- **澄清（非bug，不同主体/口径）**：供货额=倍赛思**欠我方**货款(批发价、只算我方供货品)；真金白银=**客户付倍赛思**现金(零售价、整店含倍赛思自营品)。今日11单逐单核实：3单全是倍赛思自营商品(供货额=0但客户付了3851)，其余单零售>供货有加价 → 真金白银>供货额正常。
- **标注**：今日卡片标题下加一行说明口径；"今日真金白银/储值"标"· 客户付倍赛思"；绿色区间卡片标题加"客户付倍赛思"。("今日供货额"后的"· 倍赛思欠我方"按用户要求去掉，保持简洁)

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
