FROM haproxy:2.2.4

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && \
    apt-get -y install \
        curl \
        gettext-base \
        openssl

WORKDIR /app
COPY start_haproxy.sh .
COPY haproxy.cfg.tmpl .

CMD [ "/app/start_haproxy.sh" ]

EXPOSE 9080 9443
