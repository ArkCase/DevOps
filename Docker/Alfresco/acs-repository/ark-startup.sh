#!/bin/bash

set -eu -o pipefail

echo "Installing RDS certificate"

cd /etc/pki/ca-trust/source/anchors
wget https://s3.amazonaws.com/rds-downloads/rds-ca-2019-root.pem
update-ca-trust extract

echo "Customizing environment for ArkCase"

[ -v JAVA_OPTS ] || JAVA_OPTS=

# Fetch the DB credentials and stick them in JAVA_OPTS
if [ -v ARK_DB_SECRET_ARN ]; then
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
    # We are being run locally using docker-compose
    JAVA_OPTS="$JAVA_OPTS -Ddb.url=\"$DC_DB_URL\" -Ddb.username=$DC_DB_USERNAME -Ddb.password=$DC_DB_PASSWORD"
    echo "MariaDB URL: DC_DB_URL"
    echo "MariaDB username: $DC_DB_USERNAME"
    echo 'Added `-Ddb.url`, `-Ddb.username` and `-Ddb.password` to `JAVA_OPTS`'
fi

# Fetch the ActiveMQ credentials and stick them in JAVA_OPTS
if [ -v ARK_ACTIVEMQ_SECRET_ARN ]; then
    response=$(aws secretsmanager get-secret-value --secret-id "$ARK_ACTIVEMQ_SECRET_ARN")
    secret=$(echo "$response" | jq -r .SecretString)
    username=$(echo "$secret" | jq -r .username)
    password=$(echo "$secret" | jq -r .password)
    JAVA_OPTS="$JAVA_OPTS -Dmessaging.broker.username=$username -Dmessaging.broker.password=$password"
    echo "ActiveMQ username: $username"
    echo 'Added `-Dmessaging.broker.username` and `-Dmessaging.broker.password` to `JAVA_OPTS`'
else
    # We are being run locally using docker-compose, and the local ActiveMQ
    # doesn't have any authentication mechanisms
    true  # no-op
fi

export JAVA_OPTS
exec /usr/local/tomcat/bin/catalina.sh run -security
