#!/bin/bash

set -eu -o pipefail

echo "Creating an X.509 self-signed certificate for $ENVOY_TLS_DOMAIN_NAME"
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /app/envoy.key -out /app/envoy.crt -subj "/CN=$ENVOY_TLS_DOMAIN_NAME"

cd /app
cat envoy-config.yaml.tmpl | envsubst > envoy-config.yaml

useradd envoy-tls -U -s /bin/bash  # Create custom user and group
chown envoy-tls.envoy-tls /app/envoy.key /app/envoy.crt

chmod o+w /dev/stdout  # Ensure Envoy Proxy can write to /dev/stdout
exec execas -u envoy-tls -g envoy-tls -- /usr/local/bin/envoy -c /app/envoy-config.yaml
