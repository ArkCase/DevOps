IMPORTANT NOTE
==============

This docker-compose file is for reference only and should only be used
by maintainers. 

Alfresco reference docker-compose file
======================================

This is a reference docker-compose file to deploy Alfresco in the way
it is integrated with ArkCase (except for SSL).

You will need to set the `DNS_NAME` environment variable before
running `docker-compose up`. If you run it on an EC2 instance, you can
do this:

    $ DNS_NAME=$(curl -sSL http://169.254.169.254/latest/meta-data/public-hostname) docker-compose up

