FROM gcc AS BUILDER

WORKDIR /build

RUN git clone https://github.com/fabricetriboix/execas.git && \
    cd execas && \
    make execas


FROM envoyproxy/envoy:v1.14.1

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install \
        curl \
        gettext-base \
        openssl

COPY --from=BUILDER /build/execas/execas /usr/local/bin/execas

WORKDIR /app
COPY envoy-config.yaml.tmpl .
COPY start_envoy.sh .

CMD ["/app/start_envoy.sh"]

EXPOSE 8443 9901
