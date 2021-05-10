FROM alfresco/alfresco-activemq:5.16.1-java-11-openjdk-centos-8

ENV ACTIVEMQ_SUNJMX_START="-javaagent:/opt/activemq/jmx_prometheus_javaagent-0.15.0.jar=5556:/opt/activemq/jmx-prometheus-config.yaml"

COPY jmx-prometheus-config.yaml .
ADD https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.15.0/jmx_prometheus_javaagent-0.15.0.jar /opt/activemq/jmx_prometheus_javaagent-0.15.0.jar

USER root
RUN chown root:Alfresco /opt/activemq/jmx_prometheus_javaagent-0.15.0.jar \
        && chmod 644 /opt/activemq/jmx_prometheus_javaagent-0.15.0.jar
USER amq
