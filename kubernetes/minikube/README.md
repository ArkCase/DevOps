Scripts to setup a Minikube cluster
===================================

You will need a machine with at least 16 GiB of RAM to run this.

To ensure you have all the necessary tools installed, run the
`install-tools-YOUROS.sh` script (replace `YOUROS` with the name of
your OS).

After that, you can set up a minikube cluster by running the following
commands:

    $ ./create-minikube.sh
    $ cd ..
    $ kubectl create secret ...  # Create the necessary secrets
    $ ./deploy.py dev-deployment.yaml

