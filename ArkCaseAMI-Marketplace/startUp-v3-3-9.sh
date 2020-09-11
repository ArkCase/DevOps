#!/bin/bash

set -eu -o pipefail

# Restore ArkCase admin user if this is the first time this EC2 instances is
# booted up

if [ ! -e /var/lib/admin-password-changed ]; then
    instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

    pentaho_prop=/opt/arkcase/app/pentaho/pentaho-server/pentaho-solutions/system/applicationContext-security-ldap.properties
    arkcase_admin_user=$(grep ^adminUser "$pentaho_prop" | sed 's/^adminUser=//')

    alfresco_prop=/opt/arkcase/app/alfresco/shared/classes/alfresco-global.properties
    ldap_url=$(grep ldap.authentication.java.naming.provider.url "$alfresco_prop" | sed 's/^.*=//')
    ldap_bind_user=$(grep ldap.synchronization.java.naming.security.principal "$alfresco_prop" | sed 's/^.*=//')
    ldap_bind_password=$(grep ldap.synchronization.java.naming.security.credentials "$alfresco_prop" | sed 's/^.*=//')

    echo "Set password of admin user to the EC2 instance id"
    password=$(echo -n "$instance_id" | iconv -f utf8 -t utf16le | base64 -w 0)
    tmpfile=$(mktemp /tmp/XXXXXX.ldif)
    echo "dn: CN=${arkcase_admin_user}" > "$tmpfile"
    echo "changetype: modify" >> "$tmpfile"
    echo "replace: unicodePwd" >> "$tmpfile"
    echo "unicodePwd:: ${password}" >> "$tmpfile"
    LDAPTLS_REQCERT=never ldapmodify -H "$ldap_url" -D "$ldap_bind_user" -w "$ldap_bind_password" -x -f "$tmpfile"
    rm "$tmpfile"

    echo "Enable the admin user"
    tmpfile=$(mktemp /tmp/XXXXXX.ldif)
    echo "dn: CN=${arkcase_admin_user},${ldap_user_base}" > "$tmpfile"
    echo "changetype: modify" >> "$tmpfile"
    echo "replace: userAccountControl" >> "$tmpfile"
    echo "userAccountControl:: 512" >> "$tmpfile"
    LDAPTLS_REQCERT=never ldapmodify -H "$ldap_url" -D "$ldap_bind_user" -w "$ldap_bind_password" -x -f "$tmpfile"
    rm "$tmpfile"

    touch /var/lib/admin-password-changed
fi

# Create references of config files that we will modify later in this script

function ref()
{
    if [ ! -e "$1.orig" ]; then
        cp "$1" "$1.orig"
    fi
    cp -f "$1.orig" "$1"
}

ref /opt/arkcase/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml
ref /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase.yaml
ref /opt/arkcase/app/pentaho/pentaho-server/tomcat/conf/server.xml
ref /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml

# Modify config files

PublicDNS="$(curl -s http://169.254.169.254/latest/meta-data/public-hostname)"
pentaho_url1="PENTAHO_SERVER_URL:\ \"https://acm-arkcase\""
pentaho_url2="PENTAHO_SERVER_URL:\ \"https://$PublicDNS\""
echo "127.0.0.1 $PublicDNS" >> /etc/hosts

sed -i "s/arkcase-ce.local/$PublicDNS/g" /opt/arkcase/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml
sed -i "s/$PublicDNS:7070/arkcase-ce.local/g" /opt/arkcase/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml
sed -i "s~$pentaho_url1~$pentaho_url2~g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase.yaml
sed -i "s/arkcase-ce.local/$PublicDNS/g" /opt/arkcase/app/pentaho/pentaho-server/tomcat/conf/server.xml
sed -i "s/arkcase-ce.local/$PublicDNS/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "3s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "19s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "22s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "58s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "60s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "64s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "101s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml
sed -i "103s/$PublicDNS/arkcase-ce.local/g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml

# Enable and start services

systemctl enable pentaho
systemctl enable solr
systemctl enable snowbound
systemctl enable alfresco
systemctl enable config-server
systemctl enable arkcase

systemctl start pentaho
systemctl start solr
systemctl start snowbound
systemctl start alfresco
systemctl start config-server
systemctl start arkcase
