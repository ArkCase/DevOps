#!/bin/bash

set -eu -o pipefail

echo "Setting up MariaDB databases"

i=0
while [ $i -lt 100 ]; do
    varname=MARIADB_DATABASE_$i
    [ ! -v $varname ] && break
    dbname=${!varname}
    echo "Creating database $dbname"

    echo "CREATE DATABASE IF NOT EXISTS $dbname;" \
        | mysql -u root -p$MYSQL_ROOT_PASSWORD

    varname=MARIADB_USERNAME_$i
    if [ -v $varname ]; then
        username=${!varname}
        echo "CREATE USER IF NOT EXISTS '$username'@'%';" \
            | mysql -u root -p$MYSQL_ROOT_PASSWORD

        echo "GRANT ALL PRIVILEGES ON $dbname.* to '$username'@'%';" \
            | mysql -u root -p$MYSQL_ROOT_PASSWORD
    
        varname=MARIADB_PASSWORD_$i
        password=${!varname}
        echo "ALTER USER '$username'@'%' IDENTIFIED BY '$password';" \
            | mysql -u root -p$MYSQL_ROOT_PASSWORD
    fi

    i=$[ $i + 1 ]
done

echo "FLUSH PRIVILEGES;" \
    | mysql -u root -p$MYSQL_ROOT_PASSWORD
