FROM nginx:alpine

RUN apk add \
        curl \
        openssl

WORKDIR /app
COPY nginx.conf /etc/nginx/nginx.conf
COPY default.conf.tmpl .
COPY start_nginx.sh .

CMD ["/app/start_nginx.sh"]

EXPOSE 8443
