#!/bin/bash

set -eu -o pipefail

rootdir=/opt/app/arkcase

sleep 10  # Sometimes, the metadata is not available immediately at boot...
instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)

# Restore ArkCase admin user if this is the first time this EC2 instances is
# booted up

if [ ! -e /var/lib/admin-password-changed ]; then
    pentaho_prop="${rootdir}/app/pentaho/pentaho-server/pentaho-solutions/system/applicationContext-security-ldap.properties"
    arkcase_admin_user=$(grep ^adminUser "$pentaho_prop" | sed 's/^adminUser=//')

    if [ ! -e ${rootdir}/app/alfresco/shared/classes/alfresco/extension/subsystems/Authentication/ldap-ad/ldap2/ldap-ad.properties ]; then
        ldap_prop="${rootdir}/app/alfresco/shared/classes/alfresco/extension/subsystems/Authentication/ldap-ad/ldap1/ldap-ad.properties"
    else
        ldap_prop="${rootdir}/app/alfresco/shared/classes/alfresco/extension/subsystems/Authentication/ldap-ad/ldap2/ldap-ad.properties"
    fi
    ldap_url=$(grep ldap.authentication.java.naming.provider.url "$ldap_prop" | sed 's/^[^=]*=//')
    ldap_bind_user=$(grep ldap.synchronization.java.naming.security.principal "$ldap_prop" | sed 's/^[^=]*=//')
    ldap_bind_password=$(grep ldap.synchronization.java.naming.security.credentials "$ldap_prop" | sed 's/^[^=]*=//')

    echo "Set password of admin user to: \"A$instance_id\""
    sleep 30  # Wait for Samba to be up and running
    clear_password="A$instance_id"
    password=$(echo -n \"$clear_password\" | iconv -f utf8 -t utf16le | base64 -w 0)
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

    # Update the password in the portal configuration
    if [ -f ${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml ]; then
        sed -i "19s/@rKc@3e/$clear_password/g" "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
    fi
    touch /var/lib/admin-password-changed
fi

# Re-enable the solr user by using the instance ID as the password

echo "solr:$instance_id" | chpasswd

# Create references of config files that we will modify later in this script

origroot=/var/orig
mkdir -p "$origroot"

function ref()
{
    filename=$(basename "$1")
    reldir=$(dirname "$1" | sed -e "s|^$rootdir/||")
    origpath="${origroot}/${reldir}/${filename}.orig"
    if [ ! -e "$origpath" ]; then
        mkdir -p "$origroot/$reldir"
        cp "$1" "$origpath"
    fi
    cp -f "$origpath" "$1"
}

ref "${rootdir}/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml"
ref "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase.yaml"
ref "${rootdir}/app/pentaho/pentaho-server/tomcat/conf/server.xml"
ref "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"

# Modify config files

DnsName="$(curl -sf http://169.254.169.254/latest/meta-data/public-hostname || curl -sf http://169.254.169.254/latest/meta-data/local-hostname)"
pentaho_url1="PENTAHO_SERVER_URL:\ \"https://acm-arkcase\""
pentaho_url2="PENTAHO_SERVER_URL:\ \"https://$DnsName\""

echo "127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4" > /etc/hosts
echo "::1         localhost6 localhost6.localdomain6" >> /etc/hosts
echo "127.0.0.1   $DnsName" >> /etc/hosts
echo "127.0.0.1   arkcase-ce.local" >> /etc/hosts

sed -i "s/arkcase-ce.local/$DnsName/g"      "${rootdir}/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml"
sed -i "s/$DnsName:7070/arkcase-ce.local/g" "${rootdir}/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml"
sed -i "s~$pentaho_url1~$pentaho_url2~g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase.yaml"
sed -i "s/arkcase-ce.local/$DnsName/g"      "${rootdir}/app/pentaho/pentaho-server/tomcat/conf/server.xml"
sed -i "/PENTAHO_SERVER_PASSWORD:/d"        "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "/^    PENTAHO_SERVER_USER.*/a\ \ \ \ \PENTAHO_SERVER_PASSWORD: \"A$instance_id\"" "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "3s/$DnsName/arkcase-ce.local/g"     "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "19s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "22s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "43s/$DnsName:9092/arkcase-ce.local:9092/g" "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "57s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "61s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "67s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "102s/$DnsName/arkcase-ce.local/g"   "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "104s/$DnsName/arkcase-ce.local/g"   "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
if [ -e ${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml ]; then
    ref "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
    sed -i "10s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
    sed -i "11s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
    sed -i "13s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
    
    rm -f "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-runtime.yaml"
fi
# Start services now

systemctl start pentaho
systemctl start solr
systemctl start snowbound
systemctl start alfresco
systemctl start config-server
systemctl start arkcase
systemctl start haproxy
