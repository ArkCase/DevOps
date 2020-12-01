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
export nginx_acs_repository_tag=dev2
export nginx_acs_share_tag=dev2
export ark_haproxy_tag=dev2

usage() {
    echo "Usage: $0 [-h] [-d NAM] [-i ACC] [-l REG] [-r TAG] [-R TAG] [-S TAG] [--] OPTS"
    echo "  -h      Print this usage message"
    echo "  -d NAM  DNS name pointing to the Alfresco service (default: $domain_name)"
    echo "            More precisely, it's the name pointing to the NGINX side-car proxy"
    echo "  -i ACC  AWS account id (default: $account_id)"
    echo "  -l REG  AWS region (default: $region)"
    echo "  -r TAG  Tag to use for the acs-repository Docker image (default: $acs_repository_tag)"
    echo "  -R TAG  Tag to use for the nginx-acs-repository Docker image (default: $nginx_acs_repository_tag)"
    echo "  -S TAG  Tag to use for the nginx-acs-share Docker image (default: $nginx_acs_share_tag)"
    echo "  -H TAG  Tag to use for the ark-haproxy Docker image (default: $ark_haproxy_tag)"
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
        -R)
            shift
            nginx_acs_repository_tag="$1"
            shift
            ;;
        -S)
            shift
            nginx_acs_share_tag="$1"
            shift
            ;;
        -H)
            shift
            ark_haproxy_tag="$1"
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

####################
# Build a mini-PKI #
####################

if [ ! -e easyrsa ]; then
    # The mini-PKI doesn't exist, build it now
    echo "Building the mini-PKI"

    success=no

    function cleanup_pki()
    {
        if [ "$success" != yes ]; then
            echo "Failed to build mini-PKI, deleting half-baked files"
            cd ..
            rm -rf easyrsa EasyRSA-3.0.8
            exit 1
        fi
    }

    trap cleanup_pki EXIT

    # Download and install easyrsa
    wget https://github.com/OpenVPN/easy-rsa/releases/download/v3.0.8/EasyRSA-3.0.8.tgz
    tar xf EasyRSA-3.0.8.tgz
    rm EasyRSA-3.0.8.tgz
    ln -s EasyRSA-3.0.8 easyrsa
    cd easyrsa

    # Make all certificates valid for the next 9,000 days
    export EASYRSA_CERT_EXPIRE=9000

    # Make all private keys RSA 2048 bits with SHA256 hash
    export EASYRSA_KEY_SIZE=2048
    export EASYRSA_DIGEST=sha256

    # Initialize the mini-PKI
    ./easyrsa init-pki
    echo 'Local Alfresco CA' | ./easyrsa build-ca nopass || true
    # About the `|| true`: `easyrsa` expects the input to be a tty and generates an
    # error if it isn't. However, that error occurs after the private key and
    # certificate have been generated, so we can safely ignore it.

    # Create the key and certificate for HAProxy
    # NB: We use `ark-haproxy` as the CN, because that's the domain name
    #     Repository and Share will connect to and it needs to match what's on
    #     the certificate. The browser will throw a warning even if this
    #     matches because it can't verify the certificate anyway.
    ./easyrsa build-server-full ark-haproxy nopass
    cd ..
else
    echo 'Using existing mini-PKI; if you run into strange problems, run `$ rm -rf easyrsa EasyRSA*` and try again'
fi

docker-compose $@
success=yes
