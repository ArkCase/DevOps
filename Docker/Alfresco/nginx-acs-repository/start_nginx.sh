#!/bin/bash

set -eu -o pipefail

echo "Creating an X.509 self-signed certificate for $ACM_NGINX_DOMAIN_NAME"
mkdir /etc/certs /etc/keys
chmod 755 /etc/certs
chmod 700 /etc/keys
openssl req -x509 -nodes -days 9000 -newkey rsa:2048 -keyout /etc/keys/key.pem -out /etc/certs/cert.pem -subj "/CN=$ACM_NGINX_DOMAIN_NAME"
chmod 700 /etc/keys/key.pem

cd /app
cat default.conf.tmpl \
    | envsubst '${ACM_NGINX_ACS_REPO_HOST} ${ACM_NGINX_ACS_REPO_PORT}' \
    > /etc/nginx/conf.d/default.conf

exec nginx
