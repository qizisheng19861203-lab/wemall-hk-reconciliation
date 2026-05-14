#!/bin/bash
cd /opt/wemall-hk
echo "清除 Python 缓存..."
docker compose exec -T backend find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
docker compose exec -T backend find /app -name "*.pyc" -delete 2>/dev/null || true
echo "重启 backend..."
docker compose restart backend
sleep 8
echo "检查服务状态..."
docker compose exec -T backend curl -f http://localhost:8000/health
echo ""
echo "完成！"
