#!/bin/bash

set -eu -o pipefail

mkdir -p /etc/certs /etc/keys
chown root:root /etc/certs /etc/keys
chmod 755 /etc/certs
chmod 700 /etc/keys

if [ -v ACM_NGINX_KEY ]; then
    echo "I am being run on ECS"
    echo "$ACM_NGINX_KEY" > /etc/keys/key.pem
    echo "$ACM_NGINX_CERT" > /etc/certs/cert.pem
    echo "$ACM_NGINX_INTERMEDIATE_CA_CERT" >> /etc/certs/cert.pem

    echo "XXX DEBUG: curl $ECS_CONTAINER_METADATA_URI"
    curl "$ECS_CONTAINER_METADATA_URI"
else
    echo "Creating an X.509 self-signed certificate"
    openssl req -x509 -nodes -days 9000 -newkey rsa:2048 -keyout /etc/keys/key.pem -out /etc/certs/cert.pem -subj "/CN=proxy"
fi

chown root:root /etc/certs/cert.pem /etc/keys/key.pem
chmod 755 /etc/certs/cert.pem
chmod 700 /etc/keys/key.pem

cd /app
cat default.conf.tmpl \
    | envsubst '${ACM_NGINX_DOMAIN_NAME} ${ACM_NGINX_ACS_REPO_HOST} ${ACM_NGINX_ACS_REPO_PORT} ${ACM_NGINX_ACS_SHARE_HOST} ${ACM_NGINX_ACS_SHARE_PORT}' \
    > /etc/nginx/conf.d/default.conf

exec nginx
