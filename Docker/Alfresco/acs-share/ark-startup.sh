#!/bin/bash

set -eu -o pipefail

[ -v JAVA_OPTS ] || JAVA_OPTS=

if [ -v ARK_DB_SECRET_ARN ]; then
    echo "I am being run on ECS"

    echo "Fetching the DB credentials and adding them to JAVA_OPTS"
    response=$(aws secretsmanager get-secret-value --secret-id "$ARK_DB_SECRET_ARN")
    secret=$(echo "$response" | jq -r .SecretString)
    host=$(echo "$secret" | jq -r .host)
    port=$(echo "$secret" | jq -r .port)
    dbname=$(echo "$secret" | jq -r .dbname)
    username=$(echo "$secret" | jq -r .username)
    password=$(echo "$secret" | jq -r .password)
    JAVA_OPTS="$JAVA_OPTS -Ddb.url=\"jdbc:mariadb://$host:$port/$dbname?autoReconnect=true&useUnicode=true&characterEncoding=UTF-8&useSSL=true&requireSsl=true&enabledSslProtocolSuites=TLSv1.2&trustServerCertificate=false&serverSslCert=/etc/pki/ca-trust/source/anchors/rds-ca-2019-root.pem\""
    JAVA_OPTS="$JAVA_OPTS -Ddb.username=$username -Ddb.password=$password"
    echo "MariaDB host: $host"
    echo "MariaDB port: $port"
    echo "MariaDB dbname: $dbname"
    echo "MariaDB username: $username"
    echo 'Added `-Ddb.url`, `-Ddb.username` and `-Ddb.password` to `JAVA_OPTS`'
else
    echo "I am being run locally using docker-compose"
    JAVA_OPTS="$JAVA_OPTS -Ddb.url=\"$DC_DB_URL\" -Ddb.username=$DC_DB_USERNAME -Ddb.password=$DC_DB_PASSWORD"
    echo "MariaDB URL: DC_DB_URL"
    echo "MariaDB username: $DC_DB_USERNAME"
    echo 'Added `-Ddb.url`, `-Ddb.username` and `-Ddb.password` to `JAVA_OPTS`'
fi

if [ -v ARK_ACTIVEMQ_SECRET_ARN ]; then
    echo "Fetching the ActiveMQ credentials and adding them to JAVA_OPTS"
    response=$(aws secretsmanager get-secret-value --secret-id "$ARK_ACTIVEMQ_SECRET_ARN")
    secret=$(echo "$response" | jq -r .SecretString)
    username=$(echo "$secret" | jq -r .username)
    password=$(echo "$secret" | jq -r .password)
    JAVA_OPTS="$JAVA_OPTS -Dmessaging.broker.username=$username -Dmessaging.broker.password=$password"
    echo "ActiveMQ username: $username"
    echo 'Added `-Dmessaging.broker.username` and `-Dmessaging.broker.password` to `JAVA_OPTS`'
else
    echo "ARK_ACTIVEMQ_SECRET_ARN not defined => Don't set up ActiveMQ credentials for Alfresco"
fi

export JAVA_OPTS
exec /usr/local/tomcat/bin/catalina.sh run -security
