FROM 300674751221.dkr.ecr.us-west-1.amazonaws.com/nginx-tls:7

RUN apk --no-cache add \
        curl \
        jq \
        python3 \
    && python3 -m ensurepip \
    && pip3 install --no-cache-dir awscli

COPY default.conf.tmpl .
COPY start_nginx.sh .

CMD ["/app/start_nginx.sh"]

EXPOSE 9443
