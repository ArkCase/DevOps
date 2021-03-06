FROM alfresco/alfresco-governance-share-community:V3.4-latest

# NB: Alfresco CE 2018-06 does not work with higher versions of
#     MariaDB JDBC; specifically, it does not work with 2.4.2.
ARG MARIADB_JDBC_VERSION=2.2.5

USER root

RUN yum -y install https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm \
    && yum -y install \
        curl \
        jq \
        python3 \
        python3-pip \
        wget \
    && pip3 install awscli \
    && cd /usr/local/tomcat/lib \
    && wget https://downloads.mariadb.com/Connectors/java/connector-java-${MARIADB_JDBC_VERSION}/mariadb-java-client-${MARIADB_JDBC_VERSION}.jar \
    && chmod 644 mariadb-java-client-${MARIADB_JDBC_VERSION}.jar \
    && cd /etc/pki/ca-trust/source/anchors \
    && wget https://s3.amazonaws.com/rds-downloads/rds-ca-2019-root.pem \
    && update-ca-trust extract

COPY ark-startup.sh /usr/local/tomcat/bin/ark-startup.sh
COPY share-config-custom.xml /usr/local/tomcat/shared/classes/alfresco/web-extension/share-config-custom.xml
COPY substituter.sh /usr/local/tomcat/shared/classes/alfresco/substituter.sh

CMD ["/usr/local/tomcat/bin/ark-startup.sh"]

# The original image has an entrypoint pointing to `substituter.sh` which
# totally ignores any CMD. So we reset the entrypoint here and call
# `substituter.sh` from `ark-startup.sh`.
ENTRYPOINT []

EXPOSE 8082
