#!/bin/bash

set -eu -o pipefail

function usage() {
    echo "Usage: AWS_PROFILE=marketplace $0"
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

if [[ -v AWS_DEFAULT_REGION ]]; then
    aws_region="$AWS_DEFAULT_REGION"
else
    aws_region=$(aws configure get region --profile "$AWS_PROFILE")
fi

if [[ -t 1 ]]; then
    # Allow colors if the terminal is a TTY (i.e. run by a human)
    no_color_opt=
else
    # Don't output control characters for colors if running as CD
    no_color_opt="-color=false"
fi

timestamp=$(date -u '+%Y%m%d-%H%M')

packer build $no_color_opt \
    -var region="$aws_region" \
    -var timestamp="$timestamp" \
    packer.json | tee packer-build.log
