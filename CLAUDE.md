# 微盟香港对账系统

## 项目概述
供应商（管理员）与香港分销商（微盟店铺）之间的对账系统。
分销商订单为零售价，供应商按供货价结算，付款为港币。

## 访问地址
- 生产环境：https://weimob.blue-medicine.com
- 服务器IP：175.178.162.121

## 技术栈
- 后端：Python 3.12 + FastAPI + SQLAlchemy + MySQL 8.0
- 前端：Vue 3 + Element Plus + ECharts
- 部署：Docker Compose + Nginx + Let's Encrypt

## 目录结构
```
backend/
  app/
    models/       数据库模型（User/Product/Order/Settlement/ExchangeRate）
    routers/      API路由（auth/products/orders/settlements/reports）
    services/     服务层（wemall_api/pdf_generator/sms_service/scheduler）
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
- `WEMALL_APP_KEY/SECRET/SHOP_ID` 微盟API（拿到后填）
- `EXCHANGE_RATE_API_KEY` 汇率API密钥

## 待办事项
- [ ] 填写微盟API凭证（WEMALL_APP_KEY等）
- [ ] 上传公章图片到 `static/seal.png`（发票PDF会显示）
- [ ] 配置GitHub Actions Secrets（SERVER_HOST/SERVER_USER/SERVER_SSH_KEY）实现自动部署
- [ ] 注册 exchangerate-api.com 获取免费汇率API Key
- [ ] 申请腾讯云短信模板（结算通知用）
