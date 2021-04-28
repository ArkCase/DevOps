#!/bin/bash

set -eu -o pipefail

MINIKUBE_MEMORY_MiB=8192

tmp=$(realpath "$0")
here=$(dirname "$tmp")
cd "$here"

echo
echo
echo "*** Deleting old minikube ***"
minikube delete

echo
echo
echo "*** Creating new minikube ***"
minikube start --memory $MINIKUBE_MEMORY_MiB --network-plugin cni
sleep 10

echo
echo
echo "*** Minikube succesfully created ***"
