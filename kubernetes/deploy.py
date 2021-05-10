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


def run(args):
    """
    Run a command and return the output. The output returned by the command
    must be a human-readable string. If the command fails, exits immediately.

    `args` can be either a string or a list. Examples:
        "kubectl get pods"
        ["kubectl", "get", "pods"]
    """
    if isinstance(args, str):
        args = args.split()
    try:
        output = subprocess.check_output(args)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to run command: {args}: {str(e)}")
    return output.decode("utf-8")


def wait_for_pod(start_of_podname: str,
                 namespace: str = "default",
                 timeout_seconds: int = 600):
    start_time = int(time.time())
    time.sleep(10)  # Give some time to the controller to create pods
    while int(time.time()) - start_time <= timeout_seconds:
        output = run(["kubectl", "-n", namespace, "get", "pods"])
        lines = output.splitlines()[1:]  # Remove header line
        for line in lines:
            if line.startswith(start_of_podname):
                # We found the pod. Now check whether all its containers are
                # started.
                tmp = line.split()[1]  # Extract containers number: "2/3"
                tmp = tmp.split("/")
                have = int(tmp[0])
                want = int(tmp[1])
                if have == want:
                    # All containers are stared, hooray!
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                    return
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(2)
    raise RuntimeError(f"Pod {start_of_podname} not started in {timeout_seconds} seconds")


# Helm repos

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


# Cluster-wide stuff

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


# Calico

info("")
info("*** Installing/Updating Calico ***")
run("kubectl apply -f calico.yaml")
wait_for_pod("calico-node", "kube-system")
