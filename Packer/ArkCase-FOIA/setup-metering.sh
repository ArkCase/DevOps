#!/bin/bash

set -eu -o pipefail

cronfile=/etc/cron.d/report-metering
if [ -e "$cronfile" ]; then
    echo "SETUP-METERING: Cronjob to run \`report-metering.sh\` already exists; nothing to do"
    exit 0
fi

# Select next next minute to allow cron to run the script ASAP
minute=$(date +'%M')
minute=$(echo $minute | sed -s s/^0//)  # Trim any leading zero
minute=$(( $minute + 2 ))
if [ $minute -ge 60 ]; then
    minute=$(( $minute - 60 ))
fi

echo "SETUP-METERING: Setting up cronjob to run \`report-metering.sh\` each hour on minute: $minute"

umask 022
echo "SHELL=/bin/bash" > "$cronfile"
echo "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin" >> "$cronfile"
echo "$minute * * * *  root  /usr/local/bin/report-metering.sh" >> "$cronfile"

systemctl restart cron
