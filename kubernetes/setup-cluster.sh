#!/bin/bash

set -eu -o pipefail

ISTIO_PROFILE=demo
DB_PASSWORD_LENGTH=30

tmp=$(realpath "$0")
here=$(dirname "$tmp")
cd "$here"


function generate_password()
{
    pwgen $DB_PASSWORD_LENGTH 1
}


db_root_password=$(generate_password)
db_names=(activemq)
db_usernames=(activemq)
db_passwords=($(generate_password))


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
echo "*** Setting up cluster-wide stuff ***"

# Add the `istio-injection=enabled` label to the `default` namespace, so that
# Istio will automatically inject side-car proxies to any pod created in this
# namespace.
kubectl label namespace default istio-injection=enabled

kubectl create namespace observability
kubectl label namespace observability istio-injection=enabled

echo
echo
echo "*** Installing Calico ***"
kubectl apply -f files/calico.yaml
wait_for_pod calico-node kube-system
kubectl apply -f files/default-network-policy.yaml
kubectl -n observability apply -f files/default-network-policy.yaml

echo
echo
echo "*** Installing Jaeger ***"
kubectl -n observability apply -f files/jaeger-network-policy.yaml
kubectl -n observability apply -f files/jaeger-crd.yaml
kubectl -n observability apply -f files/jaeger-operator.yaml
wait_for_pod jaeger-operator observability

kubectl -n observability apply -f files/jaeger.yaml

# Wait for Jaeger pod to be available, but ignore the jaeger-operator pod
sleep 10  # Give some time to the controller to create pods
while true; do
    tmp=$(kubectl -n observability get pods | grep jaeger | grep -v operator | tail -1 | awk '{ print $2 }')
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

echo
echo
echo "*** Installing Istio ***"
istioctl install -y --set profile=$ISTIO_PROFILE --set meshConfig.defaultConfig.tracing.zipkin.address=jaeger-collector.observability:9411
sleep 10

echo
echo
echo "*** Installing Loki ***"
kubectl -n observability apply -f files/loki-network-policy.yaml
helm -n observability install -f files/loki-values.yaml loki grafana/loki
wait_for_pod loki observability

echo
echo
echo "*** Installing Promtail ***"
kubectl -n observability apply -f files/promtail-network-policy.yaml
helm -n observability install -f files/promtail-values.yaml promtail grafana/promtail
wait_for_pod promtail observability

echo
echo
echo "*** Installing Prometheus ***"
kubectl -n observability apply -f files/prometheus-network-policy.yaml
helm -n observability install -f files/prometheus-values.yaml prometheus prometheus-community/prometheus
wait_for_pod prometheus-server observability

echo
echo
echo "*** Installing Grafana ***"
kubectl -n observability apply -f files/grafana-network-policy.yaml
helm -n observability install -f files/grafana-values.yaml grafana grafana/grafana
wait_for_pod grafana observability

# NB: I can't get Kiali to work. The UI always shows "Empty Graph" no matter
#     what I try.
# echo
# echo
# echo "*** Installing Kiali ***"
# kubectl -n observability apply -f files/kiali-network-policy.yaml
# helm -n observability install -f files/kiali-values.yaml kiali ../helm-charts/kiali-server
# wait_for_pod kiali observability

echo
echo
echo "*** Installing MariaDB ***"
opts="--set rootPassword=$db_root_password --set metricsPort=15020"
i=0
n=${#db_names[@]}
while [ $i -lt $n ]; do
    opts="$opts --set dbconfig[$i].dbname=${db_names[$i]}"
    opts="$opts --set dbconfig[$i].username=${db_usernames[$i]}"
    opts="$opts --set dbconfig[$i].password=${db_passwords[$i]}"
    i=$(( $i + 1 ))
done
set -x  # XXX
helm install $opts mariadb ../helm-charts/mariadb
set +x  # XXX
wait_for_pod mariadb

echo
echo
echo "*** Cluster succesfully set up ***"
