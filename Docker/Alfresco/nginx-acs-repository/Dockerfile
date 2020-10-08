FROM 300674751221.dkr.ecr.us-west-1.amazonaws.com/nginx-tls:6

COPY default.conf.tmpl .
COPY start_nginx.sh .

CMD ["/app/start_nginx.sh"]

EXPOSE 8180 8443
