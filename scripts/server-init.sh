#!/bin/bash
# 腾讯云CVM 一键完整部署脚本
# 将此脚本内容直接粘贴到服务器终端运行
set -e

DOMAIN="weimob.blue-medicine.com"
REPO="https://github.com/qizisheng19861203-lab/wemall-hk-reconciliation.git"
DEPLOY_DIR="/opt/wemall-hk"

echo "========================================"
echo "  微盟香港对账 - 一键服务器部署"
echo "  域名: $DOMAIN"
echo "========================================"

# ---- 1. 安装依赖 ----
echo "[1/6] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq git curl certbot

# 安装Docker（如果没有）
if ! command -v docker &>/dev/null; then
    echo "  安装Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker && systemctl start docker
fi

# 确认docker compose可用
docker compose version &>/dev/null || apt-get install -y docker-compose-plugin

# ---- 2. 克隆/更新代码 ----
echo "[2/6] 拉取代码..."
if [ -d "$DEPLOY_DIR/.git" ]; then
    cd "$DEPLOY_DIR" && git pull origin main
else
    git clone "$REPO" "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

mkdir -p static nginx/ssl

# ---- 3. 检查.env ----
echo "[3/6] 检查配置文件..."
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
    echo ""
    echo "  ⚠️  请先编辑 .env 文件填写配置，然后重新运行此脚本！"
    echo "  命令: nano $DEPLOY_DIR/.env"
    echo ""
    exit 1
fi

# ---- 4. 申请SSL证书 ----
echo "[4/6] 申请SSL证书..."
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    # 临时用 standalone 模式（此时80端口需要空闲）
    docker compose -f "$DEPLOY_DIR/docker-compose.yml" stop nginx 2>/dev/null || true
    certbot certonly --standalone --non-interactive --agree-tos \
        --register-unsafely-without-email \
        -d "$DOMAIN"
    echo "  ✅ 证书申请成功"
else
    echo "  ✅ 证书已存在，跳过"
fi

# ---- 5. 启动服务 ----
echo "[5/6] 构建并启动容器..."
cd "$DEPLOY_DIR"
docker compose up -d --build --remove-orphans
echo "  等待服务就绪..."
sleep 20

# ---- 6. 初始化数据库 ----
echo "[6/6] 初始化数据库..."
docker compose exec -T backend python init_db.py

# ---- 设置SSL自动续期 ----
cat > /etc/cron.d/certbot-renew << 'CRON'
0 3 1 */2 * root cd /opt/wemall-hk && docker compose stop nginx && certbot renew --standalone --quiet && docker compose start nginx
CRON

echo ""
echo "========================================"
echo "  ✅ 部署完成！"
echo "========================================"
echo ""
echo "  访问地址: https://$DOMAIN"
echo "  管理员账号: admin"
echo "  默认密码:   Admin@2024  ← 登录后请立即修改！"
echo ""
echo "  查看日志: docker compose -f $DEPLOY_DIR/docker-compose.yml logs -f"
echo ""
