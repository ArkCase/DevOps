# XXX FROM alfresco/alfresco-governance-repository-community:V3.3.1.x-latest
FROM alfresco/alfresco-content-repository-community:latest

# NB: Alfresco CE 2018-06 does not work with higher versions of
#     MariaDB JDBC; specifically, it does not work with 2.4.2.
ARG MARIADB_JDBC_VERSION=2.2.5

USER root

RUN yum -y install \
        curl \
        wget \
    && cd /usr/local/tomcat/lib \
    && wget https://downloads.mariadb.com/Connectors/java/connector-java-${MARIADB_JDBC_VERSION}/mariadb-java-client-${MARIADB_JDBC_VERSION}.jar \
    && chmod 644 mariadb-java-client-${MARIADB_JDBC_VERSION}.jar

USER alfresco
