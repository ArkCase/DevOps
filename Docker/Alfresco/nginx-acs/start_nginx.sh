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

    myip=$(curl -sSLf "$ECS_CONTAINER_METADATA_URI" | jq -r ".Networks[0].IPv4Addresses[0]")
    echo "Adding a Route53 A record $ACM_NGINX_DOMAIN_NAME -> $myip"

    template='{
      "Changes": [
        {
          "Action": "UPSERT",
          "ResourceRecordSet": {
            "Name": $name,
            "Type": "A",
            "ResourceRecords": [
              {
                "Value": $ipaddr
              }
            ],
            "TTL": 60
          }
        }
      ]
    }'
    rrchange=$(jq -n --arg name "$ACM_NGINX_DOMAIN_NAME" --arg ipaddr "$myip" "$template")

    aws route53 change-resource-record-sets \
            --hosted-zone-id "$ACM_NGINX_ROUTE53_ZONE_ID" \
            --change-batch "$rrchange"
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
