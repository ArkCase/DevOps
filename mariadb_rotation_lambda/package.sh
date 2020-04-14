#!/bin/bash

# Preliminaries

usage() {
    echo "Usage: $0"
    echo
    echo "Create a package for the MariaDB Lambda rotation function"
    echo "in the form of a zip file."
    exit 1
}

set -eu -o pipefail

tmp=$(realpath "$0")
dir=$(dirname "$tmp")
cd "$dir"

tmpdir=$(mktemp -d ./pkg-XXXXXXXX)
pip3 install --system --target "$tmpdir" -r requirements.txt
cd "$tmpdir"
zip -r9 ../mariadb_rotation_lambda.zip .
cd ..
rm -rf "$tmpdir"
zip -g mariadb_rotation_lambda.zip mariadb_rotation_lambda.py
