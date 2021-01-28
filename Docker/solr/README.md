IMPORTANT NOTE
==============

This docker-compose file is for reference only and should only be used
by maintainers. 

Alfresco reference docker-compose file
======================================

This is a reference docker-compose file to deploy Alfresco in a
similar way it is integrated with ArkCase (including SSL).

To run it on your computer, just run the following:

    $ ./docker-compose-wrapper.sh up --build

Wait until the logs show that Repository has started, and then point
your browser to:

    http://${domain_name}:9080/alfreso

You will need to accept the warnings about the self-signed SSL
certificates.

Block diagram
=============

                                 +------+
                        HTTP     |      |
                    +-- 8080 --> | Repo |
                    |            |      |
                    |            +------+
       HTTP     +-------+
    -- 9080 --> |       |
                | NIGNX |
    -- 9443 --> |       |
       HTTPS    +-------+
                    |            +-------+
                    |   HTTP     |       |
                    +-- 8080 --> | Share |
                                 |       |
                                 +-------+

Note: The NGINX container is a proxy. It must run on the same host as
      both Repository and Share containers, as the traffic between
      NGINX and the Repository (resp. Share) container is unencrypted.
