#!/bin/bash

# Preliminaries

set -eu -o pipefail

lambda="$1"

tmp=$(realpath "$0")
dir=$(dirname "$tmp")
cd "$dir/$lambda"

if [ -e requirements.txt ]; then
    if [ -e /etc/debian_version ]; then
        extra_pip_args=--system
    else
        extra_pip_args=
    fi
    tmpdir=$(mktemp -d ./pkg-XXXXXXXX)
    pip3 install $extra_pip_args --target "$tmpdir" -r requirements.txt
    cd "$tmpdir"
    zip -r9 "../${lambda}.zip" .
    cd ..
    rm -rf "$tmpdir"
    zip -g "${lambda}.zip" "${lambda}.py"
else
    zip -r9 "${lambda}.zip" "${lambda}.py"
fi
