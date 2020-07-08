FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y install \
        curl \
        python3 \
        python3-flask \
        python3-requests

WORKDIR /app
COPY backend.py .

USER www-data
EXPOSE 8080
CMD [ "/app/backend.py" ]
