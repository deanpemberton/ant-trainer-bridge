#!/bin/sh
set -eu

IMAGE="ant-trainer-bridge:permission-test"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

mkdir -p "$TMPDIR/fakebin"

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

# Model Home Assistant Supervisor: root-owned, owner-readable only.
chmod 600 "$TMPDIR/options.json"

# Replace python3 only for this integration test so we can observe the
# effective UID after the bootstrap has copied options and dropped privilege,
# without requiring a real Supervisor MQTT endpoint.
cat > "$TMPDIR/fakebin/python3" <<'SH'
#!/bin/sh
set -eu
echo "EFFECTIVE_UID=$(id -u)"
echo "ANT_OPTIONS_PATH=$ANT_OPTIONS_PATH"
echo "OPTIONS_BEGIN"
cat "$ANT_OPTIONS_PATH"
echo "OPTIONS_END"
SH
chmod 755 "$TMPDIR/fakebin/python3"

docker build -t "$IMAGE" ./ant_trainer_bridge >/dev/null

OUTPUT="$(docker run --rm   -e PATH="/testbin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"   -v "$TMPDIR/options.json:/data/options.json:ro"   -v "$TMPDIR/fakebin:/testbin:ro"   "$IMAGE" 2>&1)"

echo "$OUTPUT"

if echo "$OUTPUT" | grep -q "PermissionError.*options.json"; then
  echo "FAIL: startup could not read Supervisor-managed options.json" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -q "EFFECTIVE_UID=10001"; then
  echo "FAIL: long-running bridge would not execute as UID 10001" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -q "ANT_OPTIONS_PATH=/tmp/ant-trainer-options.json"; then
  echo "FAIL: bridge did not receive the bootstrapped options path" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -q '"mqtt_base_topic": "test/trainer"'; then
  echo "FAIL: bootstrapped options content was not preserved" >&2
  exit 1
fi
