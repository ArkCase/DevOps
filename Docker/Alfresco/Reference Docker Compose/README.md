Alfresco reference docker-compose file
======================================

This is a reference file to deploy Alfresco in the way it is
integrated with ArkCase.

You will need to set the `HOSTNAME` environment variable before
running `docker-compose up`; it should be a DNS domain name that
resolves to this service. If you run it on an EC2 instance, you can do
this:

    $ HOSTNAME=$(curl -sSL http://169.254.169.254/latest/meta-data/public-hostname) docker-compose up

