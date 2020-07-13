FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y install \
        curl \
        python3 \
        python3-flask

WORKDIR /app
COPY test-backend.py .

USER www-data
EXPOSE 8080
CMD [ "/app/test-backend.py" ]
