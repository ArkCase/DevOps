#!/usr/bin/env python3

import argparse
import yaml
import subprocess
import sys


def run(args):
    if isinstance(args, str):
        args = args.split()
    try:
        output = subprocess.check_output(args)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to run command: {args}: {str(e)}",
              file=sys.stderr,
              flush=True)
        sys.exit(1)
    return output.decode("utf-8")


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


def dbg(msg):
    if args.verbose:
        print(f"DEBUG: {msg}", flush=True)


def info(msg):
    print(f"INFO: {msg}", flush=True)


def err(msg):
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)


info("")
info("*** Adding Helm repositories ***")

def add_helm_repo(name: str, url: str):
    output = run("helm repo list")
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

info("")
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
