FROM envoyproxy/envoy:v1.14.1

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install \
        curl \
        gettext-base \
        openssl

WORKDIR /envoy
COPY envoy-config.yaml.tmpl .
COPY start_envoy.sh .
RUN chmod +x start_envoy.sh

CMD ["/envoy/start_envoy.sh"]

EXPOSE 8443 8081
