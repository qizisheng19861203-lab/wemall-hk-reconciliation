# 微盟香港对账系统

## 项目概述
供应商（管理员）与香港分销商（微盟店铺）之间的对账系统。
分销商订单为零售价，供应商按供货价结算，付款为港币。

**结算周期**：每周或每两周一次结算，按月生成大账单。

## 访问地址
- 生产环境：https://weimob.blue-medicine.com
- 服务器IP：175.178.162.121
- SSH：`ssh -i ~/.ssh/tencent_wemall ubuntu@175.178.162.121`

## 技术栈
- 后端：Python 3.12 + FastAPI + SQLAlchemy + MySQL 8.0
- 前端：Vue 3 + Element Plus + ECharts
- 部署：Docker Compose + Nginx + Let's Encrypt
- 自动部署：GitHub Actions（push 到 main 自动触发）

## 核心业务逻辑

### 订单管理页面（Orders.vue）
**设计原则**：订单与结算在同一页面，方便按周期快速结算

**页面布局**：
1. **顶部统计卡片**（橙色醒目）
   - 本月未结算金额（RMB）
   - 本月订单总额
   - 订单数
   - 每 10 分钟自动刷新

2. **快速结算区间选择**
   - 快速按钮：本月/上月/本周/上周/近两周
   - 按月选择器（主要按月生成大账单）
   - 自定义日期范围（支持每周/每两周结算）

3. **订单表格**
   - 每个商品单独一行显示
   - 订单号/日期/状态列自动合并同一订单的多行
   - 列：订单号 | 日期 | 商品名称 | 数量 | 供货单价(RMB) | 供货小计(RMB) | 发货状态 | 退款 | 结算 | 操作
   - 没有供货价的商品显示红色"待录价"标签
   - **只显示 RMB**，不显示港币

**默认行为**：
- 页面打开默认显示本月订单
- 默认勾选"仅未结算"

### 产品管理（Products.vue）
- 支持 Excel 批量导入供货价（优先用商品编码匹配）
- 同步微盟产品（默认 20 个，可选全部）
- 供货价为空时显示"待录价"警告

### 自动任务（scheduler.py）
- **订单同步**：每 10 分钟从微盟同步一次订单
- **汇率更新**：每天早上 9 点自动获取汇率
- **退货订单处理**：新退货订单不入库，已有订单同步退款状态

### 汇率服务（exchange_rate_service.py）
使用免费公开数据源，无需 API Key：
1. 香港金管局 HKMA（官方）
2. Frankfurter（欧洲央行）
3. Open Exchange Rates 免费端点

依次尝试，任一成功即可。

## 目录结构
```
backend/
  app/
    models/       数据库模型（User/Product/Order/Settlement/ExchangeRate）
    routers/      API路由（auth/products/orders/settlements/reports）
    services/     服务层（wemall_api/pdf_generator/sms_service/scheduler/exchange_rate_service）
    templates/    PDF模板（invoice.html/detail.html）
  init_db.py      初始化管理员账号
frontend/
  src/views/      7个页面（Dashboard/Orders/Products/Settlements/ExchangeRates/Reports/Users）
nginx/
  nginx.conf      反向代理 + HTTPS配置
scripts/
  server-init.sh  服务器一键部署脚本
.github/workflows/deploy.yml  GitHub Actions自动部署
```

## 用户角色权限
| 角色 | 编辑供货价 | 确认结清 | 查看订单 | 下载PDF |
|------|-----------|---------|---------|--------|
| admin（管理员）| ✅ | ✅ | ✅ | ✅ |
| operator（运营）| ❌ | ❌ | ✅ | ✅ |
| distributor（分销商）| ❌ | ❌ | ✅ | ✅ |

## 常用命令

### 本地开发
```bash
# 后端
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload

# 前端
cd frontend && npm install && npm run dev
```

### 服务器操作
```bash
# SSH进服务器
ssh root@175.178.162.121

# 查看容器状态
docker compose -f /opt/wemall-hk/docker-compose.yml ps

# 查看日志
docker compose -f /opt/wemall-hk/docker-compose.yml logs -f backend

# 手动重启
docker compose -f /opt/wemall-hk/docker-compose.yml restart

# 更新部署（拉最新代码）
cd /opt/wemall-hk && git pull && docker compose up -d --build
```

### 代码推送（自动触发部署）
```bash
git add . && git commit -m "描述" && git push
# GitHub Actions 自动 SSH 到服务器重新部署
```

## API接口
- `POST /api/auth/login` 登录
- `GET  /api/orders` 订单列表（支持筛选）
- `POST /api/orders/sync-wemall` 从微盟同步订单
- `GET  /api/products` 产品列表
- `POST /api/products/sync-wemall` 从微盟同步产品
- `POST /api/settlements` 创建结算单
- `POST /api/settlements/{id}/confirm` 确认收款结清
- `GET  /api/settlements/{id}/invoice.pdf` 下载Invoice PDF
- `GET  /api/settlements/{id}/detail.pdf` 下载明细PDF
- `GET  /api/reports/dashboard` 总览数据
- `POST /api/exchange-rates/fetch-today` 自动获取今日汇率

## 环境变量（.env）
必填项：
- `MYSQL_ROOT_PASSWORD` 数据库密码（已生成）
- `SECRET_KEY` JWT密钥（已生成）
- `WEMALL_APP_KEY/SECRET/SHOP_ID` 微盟API凭证（已配置）

**不再需要**：
- ~~`EXCHANGE_RATE_API_KEY`~~ 汇率改用免费公开数据源

## 重要设计决策

### 前端缓存问题
- `index.html` 加了 no-cache meta 标签
- `nginx.conf` 和 `nginx-frontend.conf` 都配置了 no-cache
- GitHub Actions 部署时重启 `backend frontend nginx` 三个容器

### 订单同步策略
- 默认同步最近 7 天订单（可选 7/15/30/60/90 天）
- 退货订单（`orderStatus=4`）不入库
- 已有订单如果变成退货状态，同步更新 `is_refunded=True`
- 每 10 分钟自动同步一次

### Excel 导入供货价
- 必须包含"供货价"列
- 优先用"商品编码"匹配（最准确）
- 其次用"商品ID"匹配
- 跳过空供货价行，清理 NaN 避免 JSON 序列化错误

### 版本号显示
- BUILD_NUMBER 和 COMMIT_SHA 由 deploy.yml 写入 `backend/app/`（容器挂载路径是 `backend/app:/app/app`）
- `main.py` 的 `/health` 接口从 `Path(__file__).parent`（即 `/app/app/`）读取这两个文件
- 版本格式：`#63 (c0abcd5)`，显示北京时间 CST

### PDF 生成（weasyprint）⚠️ 重要约束，禁止违反

**版本锁定（不可更改）：**
- `weasyprint==60.2` + `pydyf==0.8.0`（必须同时锁定，见 requirements.txt）
- weasyprint 62.x 有 transform bug；pydyf 0.9+ 与 weasyprint 60.2 API 不兼容

**WeasyPrint CSS 限制（血泪教训）：**
- ❌ **绝对禁止用 `transform: translate()` 或任何 transform** — WeasyPrint 不支持，图片会直接消失
- ❌ 不要用 `position: absolute` + `left/top` 百分比 + transform 居中
- ✅ **公章居中唯一可靠方案：3列 flexbox**，结构固定如下：
  ```html
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <span>合计 Total</span>
    <div style="flex:1; display:flex; justify-content:center;">
      <img src="{{ stamp_src }}" style="width:88px; opacity:0.85; mix-blend-mode:multiply;" />
    </div>
    <span>RMB ¥ {{ amount }}</span>
  </div>
  ```
- ✅ detail.html 的每页公章用 `position: fixed; bottom: 0.6cm; right: 1.2cm;`（固定在页面底部，这个有效）

**Invoice 必须1页约束：**
- `@page margin: 1.2cm 1.5cm`（不可超过这个）
- `font-size: 10.5pt`，`line-height: 1.45`
- 如果超过1页，先缩小 font-size 或 line-height，不要改内容

**HTTP Response Header 文件名：**
- ❌ 禁止在 `Content-Disposition: filename=` 里写中文（latin-1 报 UnicodeEncodeError）
- ✅ header 只写 ASCII 文件名，如 `filename=Invoices-2026.zip`
- ✅ ZIP 内的文件名可以有中文（zf.writestr(中文名, content) 没问题）

**其他：**
- PDF 下载用 fetch + `Authorization: Bearer` header，不用 URL 参数传 token
- 手动触发自动结算需传 `force=true` 参数
- static/logo.jpg 和 static/seal.png 已在仓库中（.gitignore 用 `static/*` + `!static/seal.png` 例外）
- 服务器 static 路径：`/opt/wemall-hk/static/`，挂载到容器 `/app/static/`

### 部署流程
- **前端**：在本地 Mac 执行 `npm run build`，再 rsync dist/ 到服务器（服务器不跑 npm）
- **后端**：rsync 代码到服务器，SSH 执行 `docker compose up -d --build --no-deps backend`
- **重要**：每次改 requirements.txt 都需要重建镜像，普通代码改动只重建也很快（层缓存）

### ⚠️ 腾讯云服务器网络限制
**服务器无法访问外网**，所有安装必须走国内镜像：

| 场景 | 镜像配置 |
|------|---------|
| pip install | `-i https://mirrors.tencent.com/pypi/simple/`（已配置在 Dockerfile）|
| apt-get（Docker build）| Dockerfile 直接覆盖写 `/etc/apt/sources.list.d/debian.sources` 为腾讯云源 |
| npm install | 在本地 Mac 跑，不在服务器跑；若必须在服务器跑用 `--registry=https://registry.npmmirror.com` |
| docker pull 基础镜像 | 若拉取失败需配置 Docker Hub 国内镜像或提前在本机 push |

**Dockerfile apt 镜像配置方式**（直接覆盖，不用 sed，避免 shell 优先级 bug）：
```dockerfile
RUN printf 'Types: deb\nURIs: http://mirrors.tencent.com/debian\nSuites: trixie trixie-updates\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n\nTypes: deb\nURIs: http://mirrors.tencent.com/debian-security\nSuites: trixie-security\nComponents: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n' \
    > /etc/apt/sources.list.d/debian.sources
```

## 待办事项
- [x] 微盟API凭证已配置
- [x] 汇率改用免费数据源
- [x] GitHub Actions 自动部署已配置
- [x] 版本号显示修复（BUILD_NUMBER/COMMIT_SHA 写入正确路径）
- [x] PDF 下载修复（weasyprint==60.2 + pydyf==0.8.0）
- [ ] 上传公章图片到 `static/seal.png`（发票PDF会显示）
- [ ] 申请腾讯云短信模板（结算通知用）
