#!/bin/bash

set -eu -o pipefail

echo "Creating an X.509 self-signed certificate for $ACM_HAPROXY_DOMAIN_NAME"
mkdir /etc/certs /etc/keys
chmod 755 /etc/certs
chmod 700 /etc/keys
openssl req -x509 -nodes -days 9000 -newkey rsa:2048 -keyout /etc/keys/key.pem -out /etc/certs/cert.pem -subj "/CN=$ACM_HAPROXY_DOMAIN_NAME"
chmod 700 /etc/keys/key.pem

cd /app
cat haproxy.cfg.tmpl \
    | envsubst '${ACM_HAPROXY_DOMAIN_NAME} ${ACM_HAPROXY_HTTP_PORT} ${ACM_HAPROXY_HTTPS_PORT} ${ACM_HAPROXY_ACS_REPO_HOST} ${ACM_HAPROXY_ACS_REPO_PORT} ${ACM_HAPROXY_ACS_SHARE_HOST} ${ACM_HAPROXY_ACS_SHARE_PORT}' \
    > /usr/local/etc/haproxy/haproxy.cfg

exec haproxy -f /usr/local/etc/haproxy/haproxy.cfg
