#!/bin/bash

# Preliminaries

set -eu -o pipefail

tmp=$(realpath "$0")
dir=$(dirname "$tmp")
cd "$dir"

zip -r9 amazonmq_rotation_lambda.zip amazonmq_rotation_lambda.py
