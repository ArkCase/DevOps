#!/bin/bash

set -eu -o pipefail

function usage() {
    echo "Usage: AWS_PROFILE=armedia $0"
    echo
    echo "Make sure you set either the AWS_PROFILE or AWS_DEFAULT_REGION"
    echo "environment variable prior to calling this script."
    exit 1
}

[[ -v AWS_PROFILE || -v AWS_DEFAULT_REGION ]] || usage

if [[ $# > 0 ]]; then
    if [[ $1 == "-h" || $1 == "--help" ]]; then
        usage
    fi
fi

tmp=$(realpath "$0")
dir=$(dirname "$tmp")
cd "$dir"

timestamp=$(date '+%Y%m%d-%H%M')

if [[ -v AWS_PROFILE ]]; then
    profile="$AWS_PROFILE"
else
    profile=""
fi

packer build \
    -color=false \
    -var timestamp="$timestamp" \
    test-backend.json
