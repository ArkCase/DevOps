#!/bin/bash

set -eu -o pipefail

MINIKUBE_MEMORY_MiB=8192
ISTIO_PROFILE=demo

tmp=$(realpath "$0")
here=$(dirname "$tmp")
cd "$here"

function add_helm_repo()
{
    if ! helm repo list | grep -wq ^$1; then
        helm repo add $1 $2
    fi
}

echo
echo
echo "*** Adding helm repositories ***"
add_helm_repo grafana https://grafana.github.io/helm-charts
add_helm_repo prometheus-community https://prometheus-community.github.io/helm-charts
add_helm_repo kube-state-metrics https://kubernetes.github.io/kube-state-metrics
helm repo update

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
echo "*** Setting up cluster-wide stuff ***"

# Add the `istio-injection=enabled` label to the `default` namespace, so that
# Istio will automatically inject side-car proxies to any pod created in this
# namespace.
kubectl label namespace default istio-injection=enabled

kubectl apply -f default-network-policy.yaml

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
        sleep 2
        echo -n .
    fi
done
echo
sleep 10

echo
echo
echo "*** Installing Loki ***"
helm install -f loki-values.yaml loki grafana/loki
kubectl apply -f loki-network-policy.yaml
sleep 10  # Give some time to the controller to create pods
while true; do
    tmp=$(kubectl get pods | grep loki-0 | awk '{ print $2 }')
    have=$(echo "$tmp" | cut -d/ -f1)
    want=$(echo "$tmp" | cut -d/ -f2)
    if [ "$have" = "$want" ]; then
        break
    else
        sleep 2
        echo -n .
    fi
done
echo
sleep 10

echo
echo
echo "*** Installing Promtail ***"
helm install -f promtail-values.yaml promtail grafana/promtail
kubectl apply -f promtail-network-policy.yaml
sleep 10  # Give some time to the controller to create pods
while true; do
    tmp=$(kubectl get pods | grep promtail | tail -1 | awk '{ print $2 }')
    have=$(echo "$tmp" | cut -d/ -f1)
    want=$(echo "$tmp" | cut -d/ -f2)
    if [ "$have" = "$want" ]; then
        break
    else
        sleep 2
        echo -n .
    fi
done
echo
sleep 10

#echo
#echo
#echo "*** Installing Grafana ***"
#helm install -f grafana-values.yaml grafana grafana/grafana
#sleep 10  # Give some time to the controller to create pods
#while true; do
#    tmp=$(kubectl get pods | grep grafana | tail -1 | awk '{ print $2 }')
#    have=$(echo "$tmp" | cut -d/ -f1)
#    want=$(echo "$tmp" | cut -d/ -f2)
#    if [ "$have" = "$want" ]; then
#        break
#    else
#        sleep 2
#        echo -n .
#    fi
#done
#echo
#sleep 10

echo
echo
echo "*** Minikube succesfully set up ***"
