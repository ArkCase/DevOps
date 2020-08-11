#!/bin/bash

set -eux -o pipefail
umask 022


# Install dependencies #

sleep 30  # Let cloud-init finish its stuff

export DEBIAN_FRONTEND=noninteractive
sudo --preserve-env=DEBIAN_FRONTEND apt-get -y update
sudo --preserve-env=DEBIAN_FRONTEND apt-get -y install \
        python3 \
        python3-boto \
        python3-pip
sudo pip3 install --upgrade awscli flask


# Install app

sudo mkdir /app
sudo cp /tmp/test-backend.py /app/test-backend.py
rm /tmp/test-backend.py

sudo cp /tmp/test-backend.service /etc/systemd/system/test-backend.service
rm /tmp/test-backend.service

sudo systemctl daemon-reload
sudo systemctl enable test-backend.service

sudo useradd -M -s /usr/sbin/nologin -U app

# Secure the AMI

rm -f ~/.ssh/authorized_keys
sudo rm -f /root/.ssh/authorized_keys
