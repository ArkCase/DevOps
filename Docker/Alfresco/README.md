IMPORTANT NOTE
==============

This docker-compose file is for reference only and should only be used
by maintainers. 

Alfresco reference docker-compose file
======================================

This is a reference docker-compose file to deploy Alfresco in the way
it is integrated with ArkCase (including SSL).

In order to run it, you will need to edit your `/etc/hosts` file and
point the `ark-haproxy` name to your own computer. You can edit the
file as root, or run the following:

    $ echo "127.1.2.3 ark-haproxy" | sudo tee -a /etc/hosts

To start everything, run the following (you will need to have
docker-ce and docker-compose installed on your machine):

    $ ./docker-compose-wrapper.sh up --build

Wait until the logs show that Repository has started, and then point
your browser to:

    http://ark-haproxy:9080/alfreso

Block diagram
=============

                                     +-------+             +------+
                            HTTPS    |       |    HTTP     |      |
                        +-- 5443 --> | NGINX | -- 8080 --> | Repo |
                        |            |       |             |      |
                        |            +-------+             +------+
       HTTP     +---------+
    -- 9080 --> |         |
                | HAProxy |
    -- 9443 --> |         |
       HTTPS    +---------+
                        |            +-------+             +-------+
                        |   HTTPS    |       |    HTTP     |       |
                        +-- 6443 --> | NGINX | -- 8080 --> | Share |
                                     |       |             |       |
                                     +-------+             +-------+

Note: The NGINX containers are actually side-car proxies. They must
      run on the same host as the Repository (resp. Share) container,
      as the traffic between NGINX and the Repository (resp. Share)
      container is unencrypted.

Notes on TLS
============

Repository and Share must be able to talk to each other in an
encrypted manner. The difficult with Java is that when connecting to a
server over TLS, the certificate presented by the server **must**
match the domain name of the server being connected to. This presents
two difficulties:
  1. The DNS must be set up so that an actual domain name points to
     the Repository/Share service as appropriate. It's OK for Alfresco
     CE because we can have only one container of each. But with
     Alfresco EE, we can have clusters and thus we need a load
     balancer in front.
  2. The Repository and Share containers must be able to validate the
     certificate they receive when connecting to the other service,
     both the domain name and the CA chain.

The first point is solved by using the load balancer for all
communications. For example, when Repository wants to connect to
Share, it actually connects to HAProxy, which will handle the request
properly as any other request.

The second point is solved by using an internal PKI, and having the
Repository and Share containers integrating a copy of the root CA
certificate. In this way, Java will be able to validate the
certificate chain.
