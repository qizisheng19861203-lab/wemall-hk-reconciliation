#!/bin/bash
set -e

echo "=== 微盟香港对账系统部署脚本 ==="

# 检查.env文件
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  请先编辑 .env 文件填入配置，然后重新运行此脚本"
    exit 1
fi

# 创建静态目录
mkdir -p static nginx/ssl

echo "1. 构建并启动容器..."
docker compose up -d --build

echo "2. 等待数据库就绪..."
sleep 15

echo "3. 初始化数据库（创建管理员账号）..."
docker compose exec backend python init_db.py

echo ""
echo "✅ 部署完成！"
echo "   访问地址: http://服务器IP"
echo "   默认管理员: admin / Admin@2024"
echo "   ⚠️  请登录后立即修改密码"
echo ""
echo "📌 后续操作："
echo "   1. 在产品库页面点击「同步微盟产品」"
echo "   2. 在产品库为每个产品设置供货价"
echo "   3. 在汇率页面点击「获取今日汇率」"
echo "   4. 在订单页面点击「同步微盟订单」"
