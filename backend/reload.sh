#!/bin/bash
# 在容器内执行，强制 Python 重新加载模块

# 删除所有 .pyc 文件和 __pycache__ 目录
find /app -type f -name "*.pyc" -delete
find /app -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# 重启 uvicorn 进程
pkill -HUP uvicorn || true

echo "Python 模块已清理，uvicorn 已重启"
