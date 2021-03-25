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

# Add the `istio-injection=enabled` label to the `default` namespace, so that
# Istio will automatically inject side-car proxies to any pod created in this
# namespace.
kubectl label namespace default istio-injection=enabled

echo
echo
echo "*** Installing Calico ***"
kubectl apply -f calico.yaml
sleep 10  # Give some time to the controller to create pods
while true; do
    tmp=$(kubectl -n kube-system get pods | grep calico-node | awk '{ print $2 }')
    have=$(echo "$tmp" | cut -d/ -f1)
    want=$(echo "$tmp" | cut -d/ -f2)
    if [ "$have" = "$want" ]; then
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
echo "*** Installing Loki ***"
kubectl create namespace loki
kubectl label namespace loki istio-injection=enabled
helm -n loki install -f loki-values.yaml loki grafana/loki
sleep 10  # Give some time to the controller to create pods
while true; do
    tmp=$(kubectl -n loki get pods | grep loki-0 | awk '{ print $2 }')
    have=$(echo "$tmp" | cut -d/ -f1)
    want=$(echo "$tmp" | cut -d/ -f2)
    if [ "$have" = "$want" ]; then
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
echo "*** Installing Promtail ***"
helm -n loki install -f promtail-values.yaml promtail grafana/promtail
sleep 10  # Give some time to the controller to create pods
while true; do
    tmp=$(kubectl -n loki get pods | grep promtail | tail -1 | awk '{ print $2 }')
    have=$(echo "$tmp" | cut -d/ -f1)
    want=$(echo "$tmp" | cut -d/ -f2)
    if [ "$have" = "$want" ]; then
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
