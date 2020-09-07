#!/bin/bash

exec 1> >(logger -t REPORT-METERING) 2>&1

set -eu -o pipefail

nusers=0
users_file="/app/data/users.json"
if [ -e "$users_file" ]; then
    nusers=$(cat "$users_file" | jq '. | length')
fi
echo "Number of users: $nusers"

product_code=$(cat /app/aws-marketplace-product-code)
timestamp=$(date -u +'%Y-%m-%dT%H:%M:%S')
dimension=UserCount

echo "Product code: $product_code"
echo "Timestamp: $timestamp"
echo "Dimension: $dimension"

aws meteringmarketplace meter-usage \
        --product-code "$product_code" \
        --timestamp "$timestamp" \
        --usage-dimension "$dimension" \
        --usage-quantity "$nusers"
