#!/bin/bash

exec 1> >(logger -t REPORT-METERING) 2>&1

set -eu -o pipefail

nusers=0
users_file="/app/data/users.json"
if [ -e "$users_file" ]; then
    nusers=$(cat "$users_file" | jq '. | length')
fi
echo "Number of users: $nusers"

token=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
region=$(curl -s -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/placement/availability-zone | sed -e 's/[a-z]$//')
product_code=$(cat /app/aws-marketplace-product-code)
timestamp=$(date -u +'%Y-%m-%dT%H:%M:%S')
dimension=UserCount

echo "Region: $region"
echo "Product code: $product_code"
echo "Timestamp: $timestamp"
echo "Dimension: $dimension"

aws meteringmarketplace --region "$region" meter-usage \
        --product-code "$product_code" \
        --timestamp "$timestamp" \
        --usage-dimension "$dimension" \
        --usage-quantity "$nusers"
