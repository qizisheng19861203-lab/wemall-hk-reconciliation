#!/bin/bash
set -e

# 微盟香港对账系统 - 本地部署脚本
# 用法: ./deploy.sh         (默认: build + sync + restart)
#       ./deploy.sh --full  (含 rebuild docker 镜像，改了 requirements.txt 时用)

SERVER="ubuntu@175.178.162.121"
SSH_KEY="$HOME/.ssh/tencent_wemall"
REMOTE_DIR="/opt/wemall-hk"
SSH_CMD="ssh -i $SSH_KEY -o StrictHostKeyChecking=no $SERVER"
RSYNC_SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"

FULL_BUILD=false
if [ "$1" = "--full" ]; then
    FULL_BUILD=true
fi

BUILD_NUM=$(git rev-list --count HEAD)
COMMIT_SHA=$(git rev-parse --short HEAD)

echo "🚀 开始部署 微盟香港对账系统"
echo "   版本: #$BUILD_NUM ($COMMIT_SHA)"
echo "   模式: $([ "$FULL_BUILD" = true ] && echo '完整部署(rebuild镜像)' || echo '快速部署(仅restart)')"
echo ""

# 1. Build 前端
echo "📦 构建前端..."
cd frontend && npm run build --silent 2>&1 | tail -3
cd ..
echo ""

# 2. 同步后端代码
echo "📤 同步后端代码..."
rsync -avz --delete \
    --exclude='.env' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    -e "$RSYNC_SSH" \
    backend/ $SERVER:$REMOTE_DIR/backend/

# 3. 同步前端 dist
echo "📤 同步前端 dist..."
rsync -avz --delete \
    -e "$RSYNC_SSH" \
    frontend/dist/ $SERVER:$REMOTE_DIR/frontend/dist/

# 4. 同步 nginx 配置
echo "📤 同步 nginx 配置..."
rsync -avz \
    -e "$RSYNC_SSH" \
    nginx/ $SERVER:$REMOTE_DIR/nginx/

# 5. 同步 static 资源
echo "📤 同步 static 资源..."
rsync -avz \
    -e "$RSYNC_SSH" \
    static/ $SERVER:$REMOTE_DIR/static/

# 6. 写入版本号 + 重启服务
echo ""
echo "🔄 重启服务..."
if [ "$FULL_BUILD" = true ]; then
    $SSH_CMD "cd $REMOTE_DIR && \
        echo '$BUILD_NUM' > backend/app/BUILD_NUMBER && \
        echo '$COMMIT_SHA' > backend/app/COMMIT_SHA && \
        docker compose up -d --build --no-deps backend && \
        docker compose restart frontend nginx"
else
    $SSH_CMD "cd $REMOTE_DIR && \
        echo '$BUILD_NUM' > backend/app/BUILD_NUMBER && \
        echo '$COMMIT_SHA' > backend/app/COMMIT_SHA && \
        docker compose restart backend frontend nginx"
fi

# 7. 等待服务启动，验证健康状态
echo ""
echo "⏳ 等待服务启动..."
sleep 8

HEALTH=$(curl -s --max-time 10 https://weimob.blue-medicine.com/health 2>/dev/null || echo "FAILED")

if echo "$HEALTH" | grep -q '"status":"ok"'; then
    VERSION=$(echo "$HEALTH" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)
    echo ""
    echo "✅ 部署成功！版本: $VERSION"
else
    echo ""
    echo "⚠️  健康检查未通过，可能还在启动中。响应: $HEALTH"
    echo "    请稍后手动检查: curl https://weimob.blue-medicine.com/health"
fi
