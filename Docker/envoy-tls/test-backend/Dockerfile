FROM ubuntu:18.04

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    DEBIAN_FRONTEND=noninteractive apt-get -y install \
        curl \
        python3 \
        python3-flask

WORKDIR /app
COPY test-backend.py .

USER www-data
EXPOSE 8080
CMD [ "/app/test-backend.py" ]
