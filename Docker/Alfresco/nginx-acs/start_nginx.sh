#!/bin/bash

set -eu -o pipefail

mkdir -p /etc/certs /etc/keys
chown root:root /etc/certs /etc/keys
chmod 755 /etc/certs
chmod 700 /etc/keys

if [ -v ARK_KEY_PARAMETER_NAME ]; then
    echo "I am being run on ECS"
    echo "Fetching the TLS private key and certificate"
    aws ssm get-parameter --name "${ARK_CERT_PARAMETER_NAME}" --with-decryption \
            | jq -r .Parameter.Value > /etc/certs/cert.pem
    aws ssm get-parameter --name "${ARK_INTERMEDIATE_CERT_PARAMETER_NAME}" --with-decryption \
            | jq -r .Parameter.Value >> /etc/certs/cert.pem
    aws ssm get-parameter --name "${ARK_KEY_PARAMETER_NAME}" --with-decryption \
            | jq -r .Parameter.Value > /etc/keys/key.pem
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
