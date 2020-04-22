#!/bin/bash

# Preliminaries

set -eu -o pipefail

tmp=$(realpath "$0")
dir=$(dirname "$tmp")
cd "$dir"

if [ -e /etc/debian_version ]; then
    extra_pip_args=--system
else
    extra_pip_args=
fi

tmpdir=$(mktemp -d ./pkg-XXXXXXXX)
pip3 install $extra_pip_args --target "$tmpdir" -r requirements.txt
cd "$tmpdir"
zip -r9 ../mariadb_rotation_lambda.zip .
cd ..
rm -rf "$tmpdir"
zip -g mariadb_rotation_lambda.zip mariadb_rotation_lambda.py
