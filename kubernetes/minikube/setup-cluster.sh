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


function wait_for_pod()
{
    if [ $# -gt 1 ]; then
        namespace=$2
    else
        namespace=default
    fi

    sleep 10  # Give some time to the controller to create pods
    while true; do
        tmp=$(kubectl -n $namespace get pods | grep $1 | tail -1 | awk '{ print $2 }')
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

echo
echo
echo "*** Installing Calico ***"
kubectl apply -f files/calico.yaml
wait_for_pod calico-node kube-system
kubectl apply -f files/default-network-policy.yaml

echo
echo
echo "*** Installing Loki ***"
kubectl apply -f files/loki-network-policy.yaml
helm install -f files/loki-values.yaml loki grafana/loki
wait_for_pod loki

echo
echo
echo "*** Installing Promtail ***"
kubectl apply -f files/promtail-network-policy.yaml
helm install -f files/promtail-values.yaml promtail grafana/promtail
wait_for_pod promtail

#echo
#echo
#echo "*** Installing Prometheus ***"
#kubectl apply -f files/prometheus-network-policy.yaml
#helm install -f files/prometheus-values.yaml prometheus prometheus-community/prometheus
#wait_for_pod prometheus-server
#
#echo
#echo
#echo "*** Installing Grafana ***"
#kubectl apply -f files/grafana-network-policy.yaml
#helm install -f files/grafana-values.yaml grafana grafana/grafana
#wait_for_pod grafana

echo
echo
echo "*** Minikube succesfully set up ***"
