# ANT+ Trainer Bridge

Home Assistant App that passively listens to ANT+ FE-C smart-trainer telemetry and ANT+ heart-rate data, then publishes it to Home Assistant through MQTT Discovery.

Initial target hardware:

- Home Assistant Green (aarch64)
- Garmin/Dynastream ANTUSB2 or ANTUSB-m USB stick
- JetBlack Victory smart trainer
- Garmin HRM 600
- MyWhoosh remains the trainer controller over Wi-Fi
- Home Assistant Mosquitto broker supplied through Supervisor

## Current status

Version **0.3.1** includes:

- Home Assistant App packaging
- raw USB/udev access
- OpenANT 1.3.4
- passive ANT+ FE-C and HR listeners
- mandatory Home Assistant Supervisor MQTT service discovery
- MQTT Discovery
- simulation mode
- 3 s / 10 s / 30 s power smoothing
- live session elapsed / average / max metrics
- trainer and HR packet-age / connectivity diagnostics
- Training Cockpit Lovelace dashboard template
- pytest coverage gate
- OWASP-aligned SAST, dependency, secret, misconfiguration and image scans
- non-root runtime container
- immutable GitHub Actions pins
- pinned multi-arch Python base-image digest
- SBOM and build provenance generation

Simulation mode is enabled by default so the MQTT/Home Assistant path can be tested before ANT+ hardware is connected.

## Home Assistant entities

The MQTT device **ANT+ Training Telemetry** exposes:

- Trainer Power
- Power 3s / Power 10s / Power 30s
- Trainer Cadence
- Trainer Speed
- Trainer Active
- Heart Rate
- Session Elapsed
- Session Average / Max Power
- Session Average / Max Heart Rate
- Trainer Packet Age / Trainer Signal
- HR Packet Age / HR Signal
- Trainer ANT Device ID
- HR ANT Device ID
- Bridge Source

## MQTT security model

The App declares:

```yaml
services:
  - mqtt:need
```

and requires Home Assistant Supervisor to provide the active MQTT service configuration.

Manual MQTT host/user/password fallback was removed in 0.3.1. If the Supervisor MQTT service is unavailable, the bridge fails closed rather than sending credentials to an arbitrary plaintext broker.

## ANT+ hardware and container privileges

OpenANT supports:

- ANTUSB2: `0fcf:1008`
- ANTUSB-m: `0fcf:1009`

The App enables:

```yaml
usb: true
udev: true
```

The application process itself runs as unprivileged UID/GID **10001**. OpenANT's recommended udev rules use `MODE=0666` for supported Dynastream/Garmin ANT USB sticks, allowing libusb access without keeping the bridge process root.

Actual USB access will be validated on the Home Assistant Green when the Garmin stick is connected.

## Reproducible and secure build

The runtime image is based on a pinned multi-architecture digest of `python:3.12-slim-trixie`.

Runtime Python dependencies are exact-pinned:

- `openant==1.3.4`
- `pyusb==1.3.1`
- `paho-mqtt==2.1.0`

GitHub Actions dependencies are pinned to full upstream commit SHAs. The image workflow also emits SBOM and provenance attestations.

Security scanning runs on pushes, pull requests and weekly:

- Bandit
- pip-audit
- Trivy filesystem/secret/misconfiguration scan
- Trivy built-container vulnerability scan

## Simulation

With `simulation: true`, the bridge emits a one-second power/cadence/heart-rate stream so the full path can be exercised:

`App -> Supervisor MQTT -> MQTT Discovery -> Home Assistant entities -> zone/dashboard logic`

before an ANT receiver is connected.

## Container images

GitHub Actions builds:

- `linux/amd64`
- `linux/arm64`

and publishes:

`ghcr.io/deanpemberton/ant-trainer-bridge`

including:

- `0.3.1`
- `latest`
- `sha-<full-git-sha>`
- release tag names for `v*`

## Install in Home Assistant

1. Home Assistant -> Settings -> Apps -> App store.
2. Add repository:
   `https://github.com/deanpemberton/ant-trainer-bridge`
3. Install **ANT+ Trainer Bridge**.
4. Leave `simulation: true` initially.
5. Start the App and inspect logs.
6. Confirm MQTT entities appear.
7. When the ANT stick is available, connect it to the Green and confirm USB visibility before switching simulation off.

## Training Cockpit

A sections-dashboard template lives at:

`dashboards/training-cockpit.yaml`

It includes live power, HR, cadence, smoothed power, session metrics, ANT health, Training Mode and the opt-in Zone Lighting switch.

## Roadmap

1. Validate Garmin ANT stick permissions as non-root on Home Assistant Green.
2. Discover and lock the JetBlack Victory and HRM 600 ANT device IDs.
3. Compare power/cadence with MyWhoosh and HR with Garmin.
4. Validate smoothing and packet-health behavior on real ANT traffic.
5. Automate Training Mode only after the real telemetry path is proven stable.
6. Enable zone lighting only when explicitly opted in.

## License

MIT
