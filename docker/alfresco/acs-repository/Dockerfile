FROM alfresco/alfresco-governance-repository-community:V3.4-latest

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

CMD ["/usr/local/tomcat/bin/ark-startup.sh"]

EXPOSE 8081

# Fabrice 20200930: For some reason, running catalina as user `alfresco` fails:
#                   `https://HOST/` works, but not `https://HOST/alfresco/`. I
#                   can't figure out why...
# USER alfresco
