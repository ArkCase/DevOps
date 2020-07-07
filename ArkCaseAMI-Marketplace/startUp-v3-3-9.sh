#!/bin/bash
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

systemctl start pentaho
systemctl start solr
systemctl start snowbound
systemctl start alfresco
systemctl start config-server
systemctl start arkcase
