#!/usr/bin/env python3

import argparse
import yaml
import subprocess
import sys
import os
import time


############################
# Checks and configuration #
############################

ap = argparse.ArgumentParser(
        description="Deploy a full ArkCase stack to a Kubernetes cluster")
ap.add_argument("-v", "--verbose", action="store_true", default=False)
ap.add_argument(
        "CFGFILE",
        help="Configuration file describing the deployment")
args = ap.parse_args()

with open(args.CFGFILE) as f:
    cfg = yaml.safe_load(f)

# Go into the "files" sub-directory
this_file = os.path.abspath(__file__)
this_dir = os.path.dirname(this_file)
os.chdir(os.path.join(this_dir, "files"))


#############
# Functions #
#############


def dbg(msg: str):
    if args.verbose:
        print(f"DEBUG: {msg}", flush=True)


def info(msg: str):
    print(f"INFO: {msg}", flush=True)


def err(msg: str):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)


def run(args, notrace: bool=False):
    """
    Run a command and return the output. The output returned by the command
    must be a human-readable string. If the command fails, exits immediately.

    `args` can be either a string or a list. Examples:
        "kubectl get pods"
        ["kubectl", "get", "pods"]

    `notrace` don't print the command, even if debug is enabled
    """
    if not notrace:
        dbg(f"Running command: {args}")
    if isinstance(args, str):
        args = args.split()
    try:
        output = subprocess.check_output(args)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run command: {args}: {str(e)}")
    return output.decode("utf-8")


def wait_for_pod(start_of_podname: str,
                 namespace: str = "default",
                 timeout_seconds: int = 600,
                 exclude: str=""):
    start_time = int(time.time())

    # Wait for the controller to potentially terminate existing pods
    time.sleep(2)

    printed_dot = False
    while int(time.time()) - start_time <= timeout_seconds:
        output = run(["kubectl", "-n", namespace, "get", "pods"], notrace=True)
        lines = output.splitlines()[1:]  # Remove header line
        for line in lines:
            if exclude and line.startswith(exclude):
                continue  # Do not check this pod
            if line.startswith(start_of_podname):
                # We found the pod. Now check whether all its containers are
                # started.
                tmp = line.split()[1]  # Extract containers number: "2/3"
                tmp = tmp.split("/")
                have = int(tmp[0])
                want = int(tmp[1])
                if have == want:
                    # All containers are started, hooray!
                    if printed_dot:
                        sys.stdout.write("\n")
                        sys.stdout.flush()
                    return
        sys.stdout.write(".")
        sys.stdout.flush()
        printed_dot = True
        time.sleep(2)
    raise RuntimeError(f"Pod {start_of_podname} not started in {timeout_seconds} seconds")


# Helm repos

info("*** Adding Helm repositories ***")

def add_helm_repo(name: str, url: str):
    output = run("helm repo list", notrace=True)
    for line in output.splitlines():
        if line.startswith(name + " ") or line.startswith(name + "\t"):
            dbg(f"Helm repo already there: {name}")
            return
    info(f"Adding Helm repo '{name}': {url}")
    run(["helm", "repo", "add", name, url])

add_helm_repo("grafana", "https://grafana.github.io/helm-charts")
add_helm_repo("prometheus-community",
              "https://prometheus-community.github.io/helm-charts")
add_helm_repo("kube-state-metrics",
              "https://kubernetes.github.io/kube-state-metrics")


# Cluster-wide stuff

info("*** Setting up cluster-wide stuff ***")

output = run("kubectl get namespace")
exists = False
for line in output.splitlines():
    if line.startswith("observability ") or line.startswith("observability\t"):
        exists = True
        break
if not exists:
    run("kubectl create namespace observability")
run("kubectl label namespace default istio-injection=enabled --overwrite")
run("kubectl label namespace observability istio-injection=enabled --overwrite")


# Calico

info("*** Installing/Updating Calico ***")
run("kubectl apply -f calico.yaml")
wait_for_pod("calico-node", "kube-system")
run("kubectl apply -f default-network-policy.yaml")
run("kubectl -n observability apply -f default-network-policy.yaml")


# Jaeger

info("*** Installing/Updating Jaeger ***")
run("kubectl -n observability apply -f jaeger-network-policy.yaml")
run("kubectl -n observability apply -f jaeger-crd.yaml")

info("  Installing/Updating Jaeger operator")
run("kubectl -n observability apply -f jaeger-operator.yaml")
wait_for_pod("jaeger-operator", "observability")

info("  Installing/Updating Jaeger")
run("kubectl -n observability apply -f jaeger.yaml")
wait_for_pod("jaeger", "observability", exclude="jaeger-operator")


# Istio

info("*** Installing/Updating Istio ***")
run([   "istioctl",
        "install",
        "-y",
        "--set",
        f"profile={cfg['istio_profile']}",
        "--set",
        f"meshConfig.defaultConfig.tracing.zipkin.address=jaeger-collector.observability:9411"])
wait_for_pod("istiod", "istio-system")


# Loki

info("*** Installing/Updating Loki ***")
run("kubectl -n observability apply -f loki-network-policy.yaml")
run("helm -n observability upgrade --install -f loki-values.yaml loki grafana/loki")
wait_for_pod("loki", "observability")


# Promtail

info("*** Installing/Updating Promtail ***")
run("kubectl -n observability apply -f promtail-network-policy.yaml")
run("helm -n observability upgrade --install -f promtail-values.yaml promtail grafana/promtail")
wait_for_pod("promtail", "observability")


# Prometheus

info("*** Installing/Updating Prometheus ***")
run("kubectl -n observability apply -f prometheus-network-policy.yaml")
run("helm -n observability upgrade --install -f prometheus-values.yaml prometheus prometheus-community/prometheus")
wait_for_pod("prometheus-server", "observability")


# Grafana

info("*** Installing/Updating Grafana ***")
run("kubectl -n observability apply -f grafana-network-policy.yaml")
run("helm -n observability upgrade --install -f grafana-values.yaml grafana grafana/grafana")
wait_for_pod("grafana", "observability")


# Kiali

# NB: I can't get Kiali to work. The UI always shows "Empty Graph" no matter
#     what I try...
#info("*** Installing/Updating Kiali ***")
#run("kubectl -n observability apply -f kiali-network-policy.yaml")
#run("helm -n observability install -f kiali-values kiali ../helm-charts/kiali-server")
#wait_for_pod("kiali", "observability")
