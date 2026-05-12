#!/bin/bash
# 腾讯云CVM一键初始化脚本（Ubuntu 22.04）
# 使用方式：ssh root@你的服务器IP 后运行此脚本
set -e

echo "========================================"
echo "  微盟香港对账系统 - 服务器初始化"
echo "========================================"

# 1. 更新系统
echo "[1/7] 更新系统包..."
apt-get update -qq && apt-get upgrade -y -qq

# 2. 安装Docker
echo "[2/7] 安装Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 3. 安装Docker Compose插件
echo "[3/7] 确认Docker Compose..."
docker compose version || (apt-get install -y docker-compose-plugin)

# 4. 安装Certbot（Let's Encrypt SSL）
echo "[4/7] 安装Certbot..."
apt-get install -y certbot python3-certbot-nginx -qq

# 5. 安装Git
echo "[5/7] 安装Git..."
apt-get install -y git -qq

# 6. 克隆项目
echo "[6/7] 克隆项目..."
mkdir -p /opt
if [ ! -d /opt/wemall-hk ]; then
    git clone https://github.com/你的用户名/微盟香港对账.git /opt/wemall-hk
    echo "⚠️  请修改上面的GitHub仓库地址"
else
    echo "项目目录已存在，跳过克隆"
fi

# 7. 配置防火墙
echo "[7/7] 配置防火墙..."
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
ufw --force enable

echo ""
echo "========================================"
echo "  ✅ 服务器初始化完成！"
echo "========================================"
echo ""
echo "下一步操作："
echo "  1. cd /opt/wemall-hk"
echo "  2. cp .env.example .env && nano .env  （填写配置）"
echo "  3. 运行 ./scripts/ssl-setup.sh 你的域名  （申请SSL证书）"
echo "  4. docker compose up -d --build"
echo "  5. docker compose exec backend python init_db.py"
echo ""
