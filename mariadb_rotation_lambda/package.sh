#!/bin/bash

# Preliminaries

usage() {
    echo "Usage: AWS_PROFILE=profile $0"
    echo
    echo "Make sure you set the AWS_PROFILE environment variable"
    echo "prior to calling this script."
    echo
    echo "Eg: AWS_PROFILE=armedia $0"
    exit 1
}

[ -z "$AWS_PROFILE" ] && usage

set -eu -o pipefail

tmp=$(realpath "$0")
dir=$(dirname "$tmp")
cd "$dir"

# Build the package

tmpdir=$(mktemp -d ./pkg-XXXXXXXX)
pip3 install --system --target "$tmpdir" -r requirements.txt
cd "$tmpdir"
zip -r9 ../mariadb_rotation_lambda.zip .
cd ..
rm -rf "$tmpdir"
zip -g mariadb_rotation_lambda.zip mariadb_rotation_lambda.py

# Upload to S3

buckets="armedia-demo-public"

for bucket in $buckets; do
    aws s3 cp mariadb_rotation_lambda.zip "s3://$bucket/DevOps/mariadb_rotation_lambda.zip"
done

# Clean up

rm -f mariadb_rotation_lambda.zip
