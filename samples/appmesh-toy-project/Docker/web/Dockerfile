FROM ubuntu:18.04

RUN apt-get -y update && \
    apt-get -y install \
        curl \
        python3 \
        python3-flask \
        python3-requests

WORKDIR /app
COPY web.py .

USER www-data
EXPOSE 8081
CMD [ "/app/web.py" ]
