#!/bin/bash

set -eu -o pipefail

rootdir=/opt/app/arkcase

# Restore ArkCase admin user if this is the first time this EC2 instances is
# booted up

if [ ! -e /var/lib/admin-password-changed ]; then
    sleep 10  # Sometimes, the metadata is not available immediately at boot...
    instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

    pentaho_prop="${rootdir}/app/pentaho/pentaho-server/pentaho-solutions/system/applicationContext-security-ldap.properties"
    arkcase_admin_user=$(grep ^adminUser "$pentaho_prop" | sed 's/^adminUser=//')

    ldap_prop="${rootdir}/app/alfresco/shared/classes/alfresco/extension/subsystems/Authentication/ldap-ad/ldap2/ldap-ad.properties"
    ldap_url=$(grep ldap.authentication.java.naming.provider.url "$ldap_prop" | sed 's/^[^=]*=//')
    ldap_bind_user=$(grep ldap.synchronization.java.naming.security.principal "$ldap_prop" | sed 's/^[^=]*=//')
    ldap_bind_password=$(grep ldap.synchronization.java.naming.security.credentials "$ldap_prop" | sed 's/^[^=]*=//')

    echo "Set password of admin user to: \"A$instance_id\""
    sleep 30  # Wait for Samba to be up and running
    password=$(echo -n \"A$instance_id\" | iconv -f utf8 -t utf16le | base64 -w 0)
    tmpfile=$(mktemp /tmp/XXXXXX.ldif)
    echo "dn: ${arkcase_admin_user}" > "$tmpfile"
    echo "changetype: modify" >> "$tmpfile"
    echo "replace: unicodePwd" >> "$tmpfile"
    echo "unicodePwd:: ${password}" >> "$tmpfile"
    LDAPTLS_REQCERT=never ldapmodify -H "$ldap_url" -D "$ldap_bind_user" -w "$ldap_bind_password" -x -f "$tmpfile"
    rm "$tmpfile"

    echo "Enable the admin user"
    tmpfile=$(mktemp /tmp/XXXXXX.ldif)
    echo "dn: ${arkcase_admin_user}" > "$tmpfile"
    echo "changetype: modify" >> "$tmpfile"
    echo "replace: userAccountControl" >> "$tmpfile"
    echo "userAccountControl: 512" >> "$tmpfile"
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

ref "${rootdir}/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml"
ref "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase.yaml"
ref "${rootdir}/app/pentaho/pentaho-server/tomcat/conf/server.xml"
ref "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"

# Modify config files

PublicDNS="$(curl -s http://169.254.169.254/latest/meta-data/public-hostname)"
pentaho_url1="PENTAHO_SERVER_URL:\ \"https://acm-arkcase\""
pentaho_url2="PENTAHO_SERVER_URL:\ \"https://$PublicDNS\""

echo "127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4" > /etc/hosts
echo "::1         localhost6 localhost6.localdomain6" >> /etc/hosts
echo "127.0.0.1   $PublicDNS" >> /etc/hosts
echo "127.0.0.1   arkcase-ce.local" >> /etc/hosts

sed -i "s/arkcase-ce.local/$PublicDNS/g"      "${rootdir}/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml"
sed -i "s/$PublicDNS:7070/arkcase-ce.local/g" "${rootdir}/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml"
sed -i "s~$pentaho_url1~$pentaho_url2~g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase.yaml"
sed -i "s/arkcase-ce.local/$PublicDNS/g"      "${rootdir}/app/pentaho/pentaho-server/tomcat/conf/server.xml"
sed -i "s/arkcase-ce.local/$PublicDNS/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "3s/$PublicDNS/arkcase-ce.local/g"     "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "19s/$PublicDNS/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "22s/$PublicDNS/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "58s/$PublicDNS/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "60s/$PublicDNS/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "62s/$PublicDNS/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "66s/$PublicDNS/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "103s/$PublicDNS/arkcase-ce.local/g"   "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "105s/$PublicDNS/arkcase-ce.local/g"   "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"

# Start services now

systemctl start pentaho
systemctl start solr
systemctl start snowbound
systemctl start alfresco
systemctl start config-server
systemctl start arkcase
systemctl start haproxy
