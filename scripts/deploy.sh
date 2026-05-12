#!/bin/bash
# 手动触发部署（在服务器上运行，或者本地通过SSH调用）
set -e

echo "=== 手动部署 ==="
cd /opt/wemall-hk

echo "拉取最新代码..."
git pull origin main

echo "重建容器..."
docker compose up -d --build --remove-orphans

echo "清理旧镜像..."
docker image prune -f

echo "运行状态："
docker compose ps

echo "=== 部署完成 ==="
