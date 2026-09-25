#!/bin/sh
set -eu

OPTIONS_SOURCE="/data/options.json"
OPTIONS_COPY="/tmp/ant-trainer-options.json"

if [ -f "$OPTIONS_SOURCE" ]; then
  install -m 0400 -o antbridge -g antbridge "$OPTIONS_SOURCE" "$OPTIONS_COPY"
else
  printf '{}\n' > "$OPTIONS_COPY"
  chown antbridge:antbridge "$OPTIONS_COPY"
  chmod 0400 "$OPTIONS_COPY"
fi

exec gosu antbridge:antbridge env ANT_OPTIONS_PATH="$OPTIONS_COPY" python3 /app/bridge.py
