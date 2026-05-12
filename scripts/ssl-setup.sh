#!/bin/bash
# SSL证书申请 + Nginx HTTPS配置
# 使用方式：./scripts/ssl-setup.sh your-domain.com
set -e

DOMAIN=${1:-""}
if [ -z "$DOMAIN" ]; then
    echo "用法: $0 your-domain.com"
    exit 1
fi

echo "========================================"
echo "  申请 Let's Encrypt 证书: $DOMAIN"
echo "========================================"

# 1. 先临时用HTTP-only Nginx让Certbot验证域名
# （容器已经在80端口监听，先停掉nginx容器）
cd /opt/wemall-hk
docker compose stop nginx 2>/dev/null || true

# 2. 申请证书（standalone模式）
certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email admin@${DOMAIN} \
    -d ${DOMAIN} \
    -d www.${DOMAIN} 2>/dev/null || \
certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email admin@${DOMAIN} \
    -d ${DOMAIN}

echo "✅ 证书申请成功！"
echo "   证书路径: /etc/letsencrypt/live/${DOMAIN}/"

# 3. 生成HTTPS版Nginx配置
cat > /opt/wemall-hk/nginx/nginx.conf << EOF
upstream backend {
    server backend:8000;
}
upstream frontend {
    server frontend:80;
}

# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name ${DOMAIN} www.${DOMAIN};
    return 301 https://\$host\$request_uri;
}

# HTTPS主服务
server {
    listen 443 ssl;
    server_name ${DOMAIN} www.${DOMAIN};
    client_max_body_size 20M;

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 10m;

    # API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 120s;
    }

    location /health {
        proxy_pass http://backend;
    }

    # 前端
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host \$host;
    }
}
EOF

# 4. 更新docker-compose挂载Let's Encrypt证书
# 在docker-compose.yml的nginx服务加上证书卷
if ! grep -q "letsencrypt" /opt/wemall-hk/docker-compose.yml; then
    sed -i "s|      - ./nginx/ssl:/etc/nginx/ssl|      - /etc/letsencrypt:/etc/letsencrypt:ro|" \
        /opt/wemall-hk/docker-compose.yml
fi

# 5. 重启Nginx容器
docker compose up -d nginx

# 6. 设置自动续期（Let's Encrypt证书90天有效，每2个月自动续期）
# 注意：续期时需要暂停nginx容器
cat > /etc/cron.d/certbot-renew << 'CRON'
0 3 1 */2 * root \
  cd /opt/wemall-hk && \
  docker compose stop nginx && \
  certbot renew --standalone --quiet && \
  docker compose start nginx
CRON

echo ""
echo "========================================"
echo "  ✅ HTTPS配置完成！"
echo "========================================"
echo "  访问: https://${DOMAIN}"
echo "  证书自动续期: 每2个月1号凌晨3点自动运行"
echo ""
