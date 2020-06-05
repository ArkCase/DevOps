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

Instructions
============

In these instructions, I will assume that you have [installed the AWS
command line
interface](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html))
and [set up an AWS
profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html)
with the name "arkcase".

Also, all AWS operations should be performed in the same region.

Step 1: docker-compose
----------------------

Edit the [Docker/docker-compose.yml](Docker/docker-compose.yml) file
and modify the image names to match your AWS account and region.

Make sure you [install](https://docs.docker.com/compose/install/)
docker-compose.

Then run the following on your favourite terminal software:

    $ cd Docker
    $ docker-compose build
    $ docker-compose up

Then fire up your browser and enter the following URL:
[http://localhost:8443/](http://localhost:8443). You will get a
warning that the SSL certificate is not valid, which is expected
because the SSL certificate on the Envoy container is self-signed.

The next step is to upload both images that have been built in the
previous step to your ECR. Point your web browser to your AWS console.
Select the "Elastic Container Registry" service. Create two Docker
repositories named "nginx-unprivileged" (this will be the app) and
"test-envoy" (this will be the Envoy proxy container).

Then run the following on your favourite terminal software (replace
the Docker image names with your owns):

    $ cd Docker
    $ eval $(aws --profile arkcase ecr get-login --no-include-email)
    $ docker push 300674751221.dkr.ecr.us-west-1.amazonaws.com/nginx-unprivileged:alpine-2
    $ docker push 300674751221.dkr.ecr.us-west-1.amazonaws.com/test-envoy:ssl-4

Step 2: CloudFormation
----------------------

You will need to have a Hosted Zone available in Route53 for this
test, and a real domain name.

Assuming you have those, the next step is for you to create a
certificate using ACM (AWS Certificate Manager) for the test domain
name you want to play with. Point your browser to the AWS console and
select the "Certificate Manager" service. Create a new certificate for
your chosen test subdomain (eg: "test.mycompany.com"). It must be a
subdomain of the Hosted Zone mentioned at the beginning of this
section. I recommend you choose the DNS validation method and allow
ACM to create the necessary DNS record set in Route53; just wait a few
minutes and your certificate should be ready. Expand the row showing
your certificate and make a copy of its ARN.

Then select the "CloudFormation" service and create a new stack.
Upload the
[CloudFormation/test-envoy.yml](CloudFormation/test-envoy.yml)
CloudFormation template. Its parameters are:

 - `VpcCidr`: this should have a reasonable default value
 - `Route53HostedZoneId`: select the ID of the Hosted Zone ID
   mentioned earlier
 - `DomainName`: enter your chosen test subdomain (eg:
   "test.mycompany.com")
 - `CertificateArn`: paste the ARN of the certificate you created in
   the previous step
 - `AppImage`: copy/paste the NGINX Docker image name
 - `EnvoyImage`: copy/paste the Envoy Docker image name

Then go ahead and create the stack. The creation process takes a few
minutes.

Once the CloudFormation stack has been created, you should be able to
point your browser to your chosen subdomain (eg:
http://test.mycompany.com). You will be automatically redirected to
HTTPS and you should be able to see the NGINX web page.

Congratulations! You have successfully setup a workload with
end-to-end encryption. The traffic between your browser and the load
balancer is encrypted using the ACM certificate, and the traffic
between the load balancer and the Envoy proxy container is encrypted
using the self-signed certificate present on the Envoy proxy
container.

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
