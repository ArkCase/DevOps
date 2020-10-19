#!/bin/bash

set -eux -o pipefail
umask 022


# Install dependencies #

sleep 30  # Let cloud-init finish its stuff

sudo yum -y update
sudo yum -y install \
        curl \
        jq \
        python3 \
        python3-boto \
        python3-pip
sudo pip3 install --upgrade awscli


function move()
{
    sudo cp "/tmp/$1" "$2/$1"
    rm "/tmp/$1"
}


# Install app

# TODO

# Install the metering scripts

move aws-marketplace-product-code /
move report-metering.sh /usr/local/bin
move setup-metering.sh /usr/local/bin
move setup-metering.service /etc/systemd/system

sudo systemctl daemon-reload
sudo systemctl enable setup-metering.service

# Secure the AMI

rm -f ~/.ssh/authorized_keys
sudo rm -f /root/.ssh/authorized_keys
