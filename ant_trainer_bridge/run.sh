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

SIMULATION="$(/usr/local/bin/python3 -c 'import json,sys; print("true" if json.load(open(sys.argv[1])).get("simulation", True) else "false")' "$OPTIONS_COPY")"

if [ "$SIMULATION" = "true" ]; then
  exec gosu antbridge:antbridge env ANT_OPTIONS_PATH="$OPTIONS_COPY" python3 /app/bridge.py
fi

# Real ANT mode starts privileged only so OpenANT/libusb can claim and detach
# the USB device. bridge.py permanently drops to UID/GID 10001 immediately
# after Node() successfully opens the ANT handle.
exec env ANT_OPTIONS_PATH="$OPTIONS_COPY" python3 /app/bridge.py
