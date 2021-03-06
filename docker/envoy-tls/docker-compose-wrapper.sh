#!/bin/bash

export account_id=300674751221
export region=us-west-1
export test_backend_tag=2
export envoy_tls_tag=3

usage() {
    echo "Usage: $0 [-h] [-i ACC] [-r REG] [-b TAG] [-e TAG] -- OPTS"
    echo "  -h      Print this usage message"
    echo "  -i ACC  AWS account id (default: $account_id)"
    echo "  -r REG  AWS region (default: $region)"
    echo "  -b TAG  Tag to use for the test-backend Docker image (default: $test_backend_tag)"
    echo "  -e TAG  Tag to use for the Envoy proxy Docker image (default: $envoy_tls_tag)"
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
        -i)
            shift
            account_id="$1"
            shift
            ;;
        -r)
            shift
            region="$1"
            shift
            ;;
        -b)
            shift
            test_backend_tag="$1"
            shift
            ;;
        -e)
            shift
            envoy_tls_tag="$1"
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
