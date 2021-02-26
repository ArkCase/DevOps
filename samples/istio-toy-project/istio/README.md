How to run the demo on minikube
===============================

Create a minikube environment:

    $ minikube delete
    $ minikube start --memory 4096

Install Istio:

    $ istioctl install --set profile=demo
    $ kubectl get pods -n istio-system

Install the tools:

    $ kubectl apply -f kiali-crd.yml
    $ kubectl apply -f istio-addons.yml
    $ kubectl get pods -n istio-system

Install the toymesh app:

    $ kubectl label namespace default istio-injection=enabled
    $ kubectl apply -f toy-app.yml
    $ kubectl apply -f gateway.yml

Get the IP address of the minikube cluster:

    $ minikube ip

The following tools are available at the minikube IP address:
  - Port 31001: Kiali
  - Port 31002: Jaeger
  - Port 31003: Grafana

To access the toy app, check the exported port for the Istio ingress
gateway:

    $ kubectl get services -n istio-system

You can then access the toy app on the minikube IP address at the port
number you found above.
