#!/bin/bash

set -eu -o pipefail

MINIKUBE_MEMORY_MiB=8192
ISTIO_PROFILE=demo

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
echo "*** Installing Istio ***"
istioctl install -y --set profile=$ISTIO_PROFILE
sleep 10

echo
echo
echo "*** Installing Calico ***"
kubectl apply -f calico.yaml
while true; do
    tmp=$(kubectl get pods -n kube-system | grep calico-node | awk '{ print }')
    if [ "$tmp" = "1/1" ]; then
        break
    else
        sleep 1
        echo -n .
    fi
done
echo
sleep 10

echo
echo
echo "*** Minikube succesfully set up ***"
