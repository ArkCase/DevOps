#!/bin/bash

set -eu -o pipefail

ISTIO_VERSION="1.8.4"

function myinstall()
{
    chmod 755 "$1"
    case "$PATH" in
        *"$HOME"/.local/bin*)
            mv -f "$1" "$HOME/.local/bin/$1"
            ;;
        *"$HOME"/bin*)
            mv -f "$1" "$HOME/bin/$1"
            ;;
        *)
            sudo chown root:root "$1"
            sudo mv "$1" "/usr/local/bin/$1"
            ;;
    esac
}

if ! which brew > /dev/null 2>&1; then
    echo "You need homebrew. Please visit https://brew.sh/ and install manually, then run the script again."
    exit 1
fi

echo
echo
echo "*** Installing system utilities ***"
brew install coreutils pwgen

echo
echo
echo "*** Installing VirtualBox ***"
brew install virtualbox virtualbox-extension-pack

echo
echo
echo "*** Install kubectl ***"
brew install kubectl

echo
echo
echo "*** Installing Helm ***"
brew install helm

echo
echo
echo "*** Installing minikube ***"
brew install minikube

echo
echo
echo "*** Installing istioctl ***"
curl -LO "https://github.com/istio/istio/releases/download/${ISTIO_VERSION}/istioctl-${ISTIO_VERSION}-osx.tar.gz"
tar xf "istioctl-${ISTIO_VERSION}-osx.tar.gz"
rm "istioctl-${ISTIO_VERSION}-osx.tar.gz"

echo
echo
echo "*** Installation complete; please reboot your computer ***"
myinstall istioctl
