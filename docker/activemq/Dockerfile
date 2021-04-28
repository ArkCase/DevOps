FROM alfresco/alfresco-activemq:5.16.1-java-11-openjdk-centos-8

COPY jmx-prometheus-config.yaml jmx_prometheus_javaagent-0.15.0.jar init.sh .
COPY activemq /opt/activemq/bin/activemq
