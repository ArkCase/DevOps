#!/bin/bash
PublicDNS="$(curl -s http://169.254.169.254/latest/meta-data/public-hostname)"
pentaho_var1="PENTAHO_SERVER_URL=https://arkcase-ce.local"
pentaho_var2="PENTAHO_SERVER_URL=https://$PublicDNS"
opencmis_var1="opencmis.server.value=https://arkcase-ce.local/alfresco/api"
opencmis_var2="opencmis.server.value=https://$PublicDNS/alfresco/api"
echo "127.0.0.1 $PublicDNS" >> /etc/hosts

sed -i "s/arkcase-ce.local/$PublicDNS/g" /opt/arkcase/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml
sed -i "s/$PublicDNS:7070/arkcase-ce.local/g" /opt/arkcase/app/alfresco/shared/classes/alfresco/web-extension/share-config-custom.xml
sed -i "s~$pentaho_var1~$pentaho_var2~g" /opt/arkcase/data/arkcase-home/.arkcase/acm/acm-reports-server-config.properties
sed -i "s~$opencmis_var1~$opencmis_var2~g" /opt/arkcase/app/alfresco/shared/classes/alfresco-global.properties
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

systemctl start pentaho
systemctl start solr
systemctl start snowbound
systemctl start alfresco
systemctl start config-server
systemctl start arkcase
