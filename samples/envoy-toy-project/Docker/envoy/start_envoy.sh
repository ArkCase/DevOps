#!/bin/bash

set -eu -o pipefail

echo "Creating an X.509 self-signed certificate for $DOMAIN_NAME"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/ssl/private/envoy.key -out /etc/ssl/certs/envoy.crt -subj "/CN=$DOMAIN_NAME"

cd /envoy
cat envoy-config.yaml.tmpl | envsubst > envoy-config.yaml

exec /usr/local/bin/envoy -c /envoy/envoy-config.yaml
