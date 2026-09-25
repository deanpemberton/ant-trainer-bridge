#!/bin/sh
set -eu

IMAGE="ant-trainer-bridge:permission-test"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

cat > "$TMPDIR/options.json" <<'JSON'
{
  "simulation": true,
  "mqtt_base_topic": "test/trainer",
  "ant_device_id": 0,
  "hr_device_id": 0,
  "active_power_threshold": 20,
  "active_timeout_seconds": 15,
  "packet_stale_seconds": 5
}
JSON

# Model Home Assistant Supervisor's root-owned app data.
chmod 600 "$TMPDIR/options.json"

docker build -t "$IMAGE" ./ant_trainer_bridge >/dev/null

set +e
OUTPUT="$(docker run --rm   -e SUPERVISOR_TOKEN=dummy   -v "$TMPDIR/options.json:/data/options.json:ro"   "$IMAGE" 2>&1)"
STATUS=$?
set -e

echo "$OUTPUT"

# The container must get past configuration loading. The dummy Supervisor
# endpoint can fail afterwards; a PermissionError reading options is the
# regression this test protects against.
if echo "$OUTPUT" | grep -q "PermissionError.*options.json"; then
  echo "FAIL: non-root bridge cannot read Supervisor-managed options.json" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -Eq "Supervisor MQTT service|Home Assistant Supervisor MQTT service is required"; then
  echo "FAIL: bridge did not get past options loading" >&2
  exit 1
fi

# Ensure the production process remains non-root after bootstrap.
USER_ID="$(docker run --rm "$IMAGE" id -u)"
if [ "$USER_ID" = "0" ]; then
  echo "FAIL: final container runtime user is root" >&2
  exit 1
fi
