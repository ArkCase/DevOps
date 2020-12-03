#!/bin/bash

set -eu -o pipefail

echo "Building certificate bundle for HAProxy"
mkdir -p /app/cert
chown root:root /app/cert
chmod 700 /app/cert
mycrt="/etc/minipki/issued/ark-haproxy.crt"
mykey="/etc/minipki/private/ark-haproxy.key"
cacrt=/etc/minipki/ca.crt
cat "$mycrt" "$cacrt" "$mykey" > /app/cert/bundle.pem
chmod 600 /app/cert/bundle.pem

echo "Creating an X.509 self-signed certificate"
mkdir /etc/certs /etc/keys
chmod 755 /etc/certs
chmod 700 /etc/keys
openssl req -x509 -nodes -days 9000 -newkey rsa:2048 -keyout /etc/keys/key.pem -out /etc/certs/cert.pem -subj "/CN=haproxy"
chmod 700 /etc/keys/key.pem

cd /app
cat haproxy.cfg.tmpl \
    | envsubst '${ACM_HAPROXY_DOMAIN_NAME} ${ACM_HAPROXY_ACS_REPO_HOST} ${ACM_HAPROXY_ACS_REPO_HTTPS_PORT} ${ACM_HAPROXY_ACS_SHARE_HOST} ${ACM_HAPROXY_ACS_SHARE_HTTPS_PORT}' \
    > /usr/local/etc/haproxy/haproxy.cfg

exec haproxy -f /usr/local/etc/haproxy/haproxy.cfg
