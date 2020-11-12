#!/bin/bash

set -eux -o pipefail
umask 022

# Install dependencies #

sleep 30  # Let cloud-init finish its stuff

sudo yum -y update
sudo yum -y install epel-release
sudo yum -y install \
        ansible \
        curl \
        git \
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

# Install ArkCase

git clone https://github.com/ArkCase/arkcase-ce.git
cd arkcase-ce/vagrant/provisioning
move facts.yml .
# XXX git checkout develop
git checkout fabrice-packer
echo 'localhost ansible_connection=local' > inventory.ini
ansible-playbook -i inventory.ini -e @facts.yml arkcase-ee-foia-AWS.yml
cd
rm -rf arkcase-ce

# Post-installation steps

## Wait 15' for services to start
sleep 900

## Disable services and firewall
sudo systemctl stop pentaho solr snowbound alfresco config-server arkcase firewalld
sudo systemctl disable pentaho solr snowbound alfresco config-server arkcase firewalld

## Setup ArkCase startup script
move startup.sh /usr/local/bin
move startup.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable startup.service

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
