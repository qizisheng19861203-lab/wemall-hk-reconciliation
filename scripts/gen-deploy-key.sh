#!/bin/bash
# 在你的本地电脑运行此脚本，生成部署用SSH密钥对
# 然后按提示配置到GitHub和服务器

echo "=== 生成部署专用SSH密钥 ==="
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/wemall_deploy -N ""

echo ""
echo "========================================"
echo "  第1步：将公钥添加到服务器"
echo "========================================"
echo "运行以下命令（替换YOUR_SERVER_IP）："
echo ""
echo "  ssh-copy-id -i ~/.ssh/wemall_deploy.pub root@YOUR_SERVER_IP"
echo ""
echo "或手动将以下内容追加到服务器的 ~/.ssh/authorized_keys："
cat ~/.ssh/wemall_deploy.pub

echo ""
echo "========================================"
echo "  第2步：将私钥添加到GitHub Secrets"
echo "========================================"
echo "打开：GitHub仓库 → Settings → Secrets → Actions → New repository secret"
echo ""
echo "添加以下3个Secret："
echo "  名称: SERVER_HOST    值: 你的服务器公网IP"
echo "  名称: SERVER_USER    值: root"
echo "  名称: SERVER_SSH_KEY 值（私钥内容如下）："
echo ""
cat ~/.ssh/wemall_deploy
echo ""
echo "========================================"
echo "  完成后，推送代码到main分支即可自动部署！"
echo "========================================"
