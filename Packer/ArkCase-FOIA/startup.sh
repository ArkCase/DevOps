#!/bin/bash

set -eu -o pipefail

rootdir=/opt/app/arkcase

sleep 10  # Sometimes, the metadata is not available immediately at boot...
instance_id=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
foia_analytical_reports_version=$(find ${rootdir}/install/pentaho/ -type d -name "foia*" -exec basename {} \;)

# Restore ArkCase admin user if this is the first time this EC2 instances is
# booted up

if [ ! -e /var/lib/admin-password-changed ]; then
    pentaho_prop="${rootdir}/app/pentaho/pentaho-server/pentaho-solutions/system/applicationContext-security-ldap.properties"
    arkcase_admin_user=$(grep ^adminUser "$pentaho_prop" | sed 's/^adminUser=//')

    ldap_prop="${rootdir}/app/alfresco/shared/classes/alfresco/extension/subsystems/Authentication/ldap-ad/ldap2/ldap-ad.properties"
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
    sed -i "19s/@rKc@3e/$clear_password/g" "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"

    # Update the password in the foia analytical reports configuration
    sed -i "s/ARKCASE_PASS=.*/ARKCASE_PASS=$clear_password/g" "${rootdir}/install/pentaho/foia-reports-dw-2021.01/config/arkcase_config.properties"
    touch /var/lib/kitchen-job

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
ref "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"

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
sed -i "s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "3s/$DnsName/arkcase-ce.local/g"     "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "19s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "22s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "58s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "60s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "62s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "66s/$DnsName/arkcase-ce.local/g"    "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "103s/$DnsName/arkcase-ce.local/g"   "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "105s/$DnsName/arkcase-ce.local/g"   "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-server.yaml"
sed -i "10s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
sed -i "11s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
sed -i "13s/arkcase-ce.local/$DnsName/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-server.yaml"
sed -i "s/arkcase-ce.local\/foia/$DnsName\/foia/g"      "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-FOIA_server.yaml"

rm -f "${rootdir}/data/arkcase-home/.arkcase/acm/acm-config-server-repo/arkcase-portal-runtime.yaml"

# Start services now

systemctl start pentaho
systemctl start solr
systemctl start snowbound
systemctl start alfresco
systemctl start config-server
systemctl start arkcase
systemctl start haproxy

## Wait for ArkCase to fully start
timeout_min=60  # Timeout: 1h
timer_min=0
echo "Wait for ArkCase to fully start..."
while true; do
    sleep 60  # Wait for 1'
    if sudo grep 'org.apache.catalina.startup.Catalina.start Server startup in \[.*\] milliseconds' ${rootdir}/log/arkcase/catalina.out > /dev/null 2>&1; then
        break
    else
        timer_min=$[ $timer_min + 1 ]
        if [ "$timer_min" -gt "$timeout_min" ]; then
            echo "ERROR: ArkCase didn't start within $timeout_min minutes"
            exit 1
        fi
        echo -n .
    fi
done
echo
echo "ArkCase fully started"

# Run kitchen scipt for foia analytical reports
if [ -e /var/lib/kitchen-job ]; then
    cd ${rootdir}/app/pentaho-pdi/data-integration
    sudo su -s /bin/bash pentaho-pdi
    ./kitchen.sh -file://${rootdir}/install/pentaho/${foia_analytical_reports_version}/foia-dw1.kjb
    rm -rf /var/lib/kitchen-job
fi
