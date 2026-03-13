#!/bin/bash
# 生成自签名 SSL 证书（开发环境使用）

set -e

echo "生成自签名 SSL 证书..."

mkdir -p nginx/ssl

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/C=CN/ST=State/L=City/O=Organization/CN=localhost"

chmod 600 nginx/ssl/privkey.pem
chmod 644 nginx/ssl/fullchain.pem

echo "SSL 证书已生成："
echo "  - nginx/ssl/fullchain.pem"
echo "  - nginx/ssl/privkey.pem"
echo ""
echo "请在 .env 中设置 NGINX_ENABLE_SSL=true 以启用 HTTPS"
