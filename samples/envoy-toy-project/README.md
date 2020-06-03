Envoy toy project
=================

This sample project shows how Envoy can be used to provide
"end-to-end" traffic encryption between a client in the internet and
containers running an application (in practice, the encryption is not
really end-to-end, in the sense that the load balancer decrypts the
traffic from the client, and then re-encrypt it to communicate with
the containers).

Envoy is a proxy software, akin to NGINX and HAProxy, but more modern
and with the ability to received dynamic configuration.

This example is two-fold. The [Docker](Docker) folder is used to build
the Docker images (which then must be manually pushed to ECR), and
optionally to run Envoy and the app (here just a plain web page served
by NGINX) locally.

The [CloudFormation](CloudFormation) folder contains a CloudFormation
template (which depends on the Docker images being built and pushed to
ECR in the previous step) which demonstrate a working example of this
"end-to-end" encryption.

Interesting notes
=================

The load balancer uses a certificate managed by ACM. The traffic
between the load balancer and the Envoy container is encrypted using a
self-signed certificate located on the Envoy container. Each Envoy
container creates such a self-signed certificate whenever it is
started. The AWS load balancer does not validate the certificate, so a
self-signed certificate works fine.

Both the Envoy and the app containers are part of the same ECS task.
The Envoy container acts as a proxy and as such is usually referred to
as a "side-car" proxy. All containers that are part of an ECS task run
on the same host and all traffic between them is local to the host.
