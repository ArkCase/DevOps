# XXX FROM alfresco/alfresco-governance-repository-community:V3.3.1.x-latest
FROM alfresco/alfresco-content-repository-community:latest

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
    && chmod 644 mariadb-java-client-${MARIADB_JDBC_VERSION}.jar

# XXX
#RUN wget https://dev.mysql.com/get/mysql80-community-release-el7-3.noarch.rpm \
#    && rpm -ivh mysql80-community-release-el7-3.noarch.rpm \
#    && yum -y install mysql

COPY ark-startup.sh /usr/local/tomcat/bin/ark-startup.sh

CMD ["/usr/local/tomcat/bin/ark-startup.sh"]

# XXX USER alfresco
