ArkCase Kubernetes deployment
=============================

In order to deploy ArkCase to a Kubernetes cluster, you will first
need to have a cluster running. You can use [minikube](minikube) on
your local machine, for example. You will also need to have:
  - kubectl installed and configured to talk to your cluster
  - helm
  - istioctl

Then you will need to create the required secrets in the Kubernetes
cluster. You can have a look at the [example
secrets](example-secrets).

You will then need to create (or re-use) a deployment configuration
file. You can have a look at the [dev deployment configuration
file](dev-deployment.yaml) for reference.

Finally, deploy ArkCase and all its dependencies using the following
command:

    $ ./deploy.py DEPLOYMENT-CONFIGURATION.yaml

