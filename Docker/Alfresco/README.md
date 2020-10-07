IMPORTANT NOTE
==============

This docker-compose file is for reference only and should only be used
by maintainers. 

Alfresco reference docker-compose file
======================================

This is a reference docker-compose file to deploy Alfresco in the way
it is integrated with ArkCase (including SSL).

    $ domain_name=$(curl -sSL http://169.254.169.254/latest/meta-data/public-hostname)
    $ ./docker-compose-wrapper.sh -d $domain_name up --build

