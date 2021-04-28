#!/bin/bash

set -eu -o pipefail

echo "Setting up MariaDB databases"

if [ -v OLD_MYSQL_ROOT_PASSWORD ]; then
    # NB: If the root user already has a password, the init scripts in the
    # official MariaDB Docker image won't change it, even if
    # `MYSQL_ROOT_PASSWORD` is different. So we need to do it ourselves.
    echo "Change old root password"
    echo "ALTER USER 'root'@'%' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD'; ALTER USER 'root'@'localhost' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD';" \
        | mysql -u root "-p$OLD_MYSQL_ROOT_PASSWORD"
fi

i=0
while true; do
    varname=MARIADB_DATABASE_$i
    [ ! -v $varname ] && break
    dbname=${!varname}
    echo "Creating database $dbname"

    echo "CREATE DATABASE IF NOT EXISTS $dbname;" \
        | mysql -u root "-p$MYSQL_ROOT_PASSWORD"

    varname=MARIADB_USERNAME_$i
    if [ -v $varname ]; then
        username=${!varname}
        echo "CREATE USER IF NOT EXISTS '$username'@'%';" \
            | mysql -u root "-p$MYSQL_ROOT_PASSWORD"

        echo "GRANT ALL PRIVILEGES ON $dbname.* to '$username'@'%';" \
            | mysql -u root "-p$MYSQL_ROOT_PASSWORD"
    
        varname=MARIADB_PASSWORD_$i
        password=${!varname}
        echo "ALTER USER '$username'@'%' IDENTIFIED BY '$password';" \
            | mysql -u root "-p$MYSQL_ROOT_PASSWORD"
    fi

    i=$[ $i + 1 ]
done
