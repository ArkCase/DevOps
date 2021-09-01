#!/bin/bash

set -eu -o pipefail

# Set default for environment variables that are parameters to this container
[ ! -v JVM_INITIAL_RAM ] && export JVM_INITIAL_RAM=64M
[ ! -v JVM_MAX_RAM ] && export JVM_MAX_RAM=1G

# Setup `env` file
# NB: More details can be found [here](https://activemq.apache.org/unix-shell-script.html#configuration-file-of-the-init-script).
cat /app/templates/env.tmpl \
    | envsubst '${JVM_INITIAL_RAM} ${JVM_MAX_RAM}' \
    > "$HOME/.activemqrc"

# Remove template directory, we don't need it anymore
rm -rf /app/templates/*

cd /app/activemq/bin
exec ./activemq console
