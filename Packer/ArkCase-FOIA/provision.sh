#!/bin/bash

set -eu -o pipefail
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
git checkout develop
echo 'localhost ansible_connection=local' > inventory.ini
ansible-playbook -i inventory.ini -e @facts.yml arkcase-ee-foia-AWS.yml
cd
rm -rf arkcase-ce

# Post-installation steps

## Wait for ArkCase to fully start
timeout_min=60  # Timeout: 1h
timer_min=0
echo "Wait for ArkCase to fully start..."
while true; do
    sleep 60  # Wait for 1'
    if sudo grep 'org.apache.catalina.startup.Catalina.start Server startup in \[.*\] milliseconds' /opt/app/arkcase/log/arkcase/catalina.out > /dev/null 2>&1; then
        break
    else
        timer_min=$[ $timer_min + 1 ]
        if [ "$timer_min" -gt "$timeout_min" ]; then
            echo "ERROR: ArkCase didn't start within $timeout_min minutes"
            exit 1
        fi
        echo -n .
    fi
done
echo
echo "ArkCase fully started"

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
