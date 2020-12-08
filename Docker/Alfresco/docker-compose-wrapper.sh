#!/bin/bash

set -eu -o pipefail

s=$(realpath "$0")
here=$(dirname "$s")
cd "$here"

export domain_name=localhost
export account_id=300674751221
export region=us-west-1
export acs_repository_tag=dev2
export acs_share_tag=dev2
export nginx_acs_tag=dev3

usage() {
    echo "Usage: $0 [-h] [-d DOM] [-i ACC] [-l REG] [-r TAG] [-s TAG] [-p TAG] [--] OPTS"
    echo "  -h      Print this usage message"
    echo "  -d DOM  DNS name pointing to the NGINX proxy (default: $domain_name)"
    echo "  -i ACC  AWS account id (default: $account_id)"
    echo "  -l REG  AWS region (default: $region)"
    echo "  -r TAG  Tag to use for the acs-repository Docker image (default: $acs_repository_tag)"
    echo "  -s TAG  Tag to use for the acs-share Docker image (default: $acs_share_tag)"
    echo "  -p TAG  Tag to use for the nginx-acs Docker image (default: $nginx_acs_tag)"
    echo "  --      Stop parsing options; necessary only if you have pre-command options"
    echo "  OPTS    Docker-compose options"
    echo
    echo "Example: $0 up --build"
}

finished_parsing=no
while [ $finished_parsing == no ]; do
    case "$1" in
        -h)
            usage
            exit 0
            ;;
        -d)
            shift
            domain_name="$1"
            shift
            ;;
        -i)
            shift
            account_id="$1"
            shift
            ;;
        -l)
            shift
            region="$1"
            shift
            ;;
        -r)
            shift
            acs_repository_tag="$1"
            shift
            ;;
        -s)
            shift
            acs_share_tag="$1"
            shift
            ;;
        -p)
            shift
            nginx_proxy_tag="$1"
            shift
            ;;
        --)
            shift
            finished_parsing=yes
            ;;
        *)
            finished_parsing=yes
            ;;
    esac
done

docker-compose $@
success=yes
