#!/bin/bash

set -eu -o pipefail

HELM_VERSION="3.5.3"
ISTIO_VERSION="1.8.4"

function myinstall()
{
    chmod 755 "$1"
    case "$PATH" in
        *"$HOME"/.local/bin*)
            mv -f "$1" "$HOME/.local/bin/$1"
            chmod 755 "$HOME/.local/bin/$1"
            ;;
        *"$HOME"/bin*)
            mv -f "$1" "$HOME/bin/$1"
            chmod 755 "$HOME/bin/$1"
            ;;
        *)
            sudo chown root:root "$1"
            sudo mv "$1" "/usr/local/bin/$1"
            sudo chmod 755 "/usr/local/bin/$1"
            ;;
    esac
}

echo
echo
echo "*** Installing VirtualBox ***"
if [ -e /etc/debian_version ]; then
    sudo apt-get -y update
    sudo apt-get -y install virtualbox virtualbox-ext-pack pwgen curl
else
    echo "OS not supported yet; please implement me"
    exit 1
fi

echo
echo
echo "*** Installing kubectl ***"
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
myinstall kubectl

echo
echo
echo "*** Installing Helm ***"
curl -LO "https://get.helm.sh/helm-v${HELM_VERSION}-linux-amd64.tar.gz"
tar xf "helm-v${HELM_VERSION}-linux-amd64.tar.gz"
mv linux-amd64/helm helm
rm -r "helm-v${HELM_VERSION}-linux-amd64.tar.gz" linux-amd64
myinstall helm

echo
echo
echo "*** Installing minikube ***"
curl -LO "https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64"
mv minikube-linux-amd64 minikube
myinstall minikube
minikube config set driver virtualbox

echo
echo
echo "*** Installing istioctl ***"
curl -LO "https://github.com/istio/istio/releases/download/${ISTIO_VERSION}/istioctl-${ISTIO_VERSION}-linux-amd64.tar.gz"
tar xf "istioctl-${ISTIO_VERSION}-linux-amd64.tar.gz"
rm "istioctl-${ISTIO_VERSION}-linux-amd64.tar.gz"
myinstall istioctl

echo
echo
echo "*** Installation complete ***"
