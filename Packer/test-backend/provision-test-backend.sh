#!/bin/bash

set -eux -o pipefail
umask 022


# Install dependencies #

sleep 30  # Let cloud-init finish its stuff

export DEBIAN_FRONTEND=noninteractive
sudo --preserve-env=DEBIAN_FRONTEND apt-get -y update
sudo --preserve-env=DEBIAN_FRONTEND apt-get -y install \
        curl \
        jq \
        python3 \
        python3-boto \
        python3-pip
sudo pip3 install --upgrade awscli flask


function move()
{
    sudo cp "/tmp/$1" "$2/$1"
    rm "/tmp/$1"
}


# Install app

sudo mkdir /app
move test-backend.py /app
move test-backend.service /etc/systemd/system

sudo systemctl daemon-reload
sudo systemctl enable test-backend.service

sudo useradd -M -s /usr/sbin/nologin -U app

sudo mkdir /app/data
sudo chown app.app /app/data

# Install the metering scripts

move aws-marketplace-product-code /app
move report-metering.sh /app
move setup-metering.sh /app
move setup-metering.service /etc/systemd/system

sudo systemctl daemon-reload
sudo systemctl enable setup-metering.service

# Secure the AMI

rm -f ~/.ssh/authorized_keys
sudo rm -f /root/.ssh/authorized_keys
