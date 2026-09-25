#!/bin/sh
set -eu

IMAGE="ant-trainer-bridge:ant-privilege-test"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT
mkdir -p "$TMPDIR/fakebin"

cat > "$TMPDIR/options.json" <<'JSON'
{
  "simulation": false,
  "mqtt_base_topic": "test/trainer",
  "ant_device_id": 0,
  "hr_device_id": 0,
  "active_power_threshold": 20,
  "active_timeout_seconds": 15,
  "packet_stale_seconds": 5
}
JSON
chmod 600 "$TMPDIR/options.json"

cat > "$TMPDIR/fakebin/python3" <<'SH'
#!/bin/sh
set -eu
echo "ANT_START_UID=$(id -u)"
echo "ANT_OPTIONS_PATH=$ANT_OPTIONS_PATH"
SH
chmod 755 "$TMPDIR/fakebin/python3"

docker build -t "$IMAGE" ./ant_trainer_bridge >/dev/null

OUTPUT="$(docker run --rm   -e PATH="/testbin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"   -v "$TMPDIR/options.json:/data/options.json:ro"   -v "$TMPDIR/fakebin:/testbin:ro"   "$IMAGE" 2>&1)"

echo "$OUTPUT"

if ! echo "$OUTPUT" | grep -q "ANT_START_UID=0"; then
  echo "FAIL: real ANT mode must start with USB-claim privilege" >&2
  exit 1
fi

if ! echo "$OUTPUT" | grep -q "ANT_OPTIONS_PATH=/tmp/ant-trainer-options.json"; then
  echo "FAIL: options bootstrap path was not preserved" >&2
  exit 1
fi
