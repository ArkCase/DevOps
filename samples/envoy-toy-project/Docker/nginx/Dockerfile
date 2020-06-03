FROM nginxinc/nginx-unprivileged:alpine

USER root

RUN apk add curl
COPY index.html /usr/share/nginx/html/index.html

USER 101
