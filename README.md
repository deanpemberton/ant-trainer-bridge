# ANT+ Trainer Bridge

Home Assistant App that listens passively to an ANT+ FE-C smart trainer and publishes live trainer telemetry to Home Assistant through MQTT Discovery.

Initial target hardware:

- Home Assistant Green (aarch64)
- Garmin/Dynastream ANTUSB2 or ANTUSB-m USB stick
- JetBlack Victory smart trainer
- MyWhoosh remains the trainer controller over Wi-Fi
- Home Assistant Mosquitto broker

## Current status

Early development, but the full non-hardware path is implemented:

- Home Assistant App packaging
- raw USB and udev access
- OpenANT 1.3.4
- passive ANT+ FE-C listener
- automatic Home Assistant Supervisor MQTT service discovery
- MQTT Discovery
- simulation mode
- 3 s / 10 s / 30 s power smoothing
- live session elapsed / average / max metrics
- trainer and HR packet-age / connectivity diagnostics
- Training Cockpit Lovelace dashboard template
- multi-architecture GHCR build workflow

Simulation mode is enabled by default so the MQTT and Home Assistant side can be tested before the ANT+ dongle arrives.

## Home Assistant entities

The bridge creates one MQTT device named **ANT+ Trainer** with:

- Trainer Power
- Power 3s / Power 10s / Power 30s
- Trainer Cadence
- Trainer Speed
- Trainer Active
- Heart Rate (ANT+ HR profile; tested target is Garmin HRM 600)
- Session Elapsed
- Session Average / Max Power
- Session Average / Max Heart Rate
- Trainer Packet Age / Trainer Signal
- HR Packet Age / HR Signal
- Trainer ANT Device ID
- HR ANT Device ID
- Bridge Source

## MQTT

The App declares `mqtt:need` and asks Home Assistant Supervisor for the active MQTT service configuration. In the normal Home Assistant OS + Mosquitto setup there is no need to create or paste separate MQTT credentials.

Manual host/username/password options remain available as a fallback.

## ANT+ hardware

OpenANT supports the expected Garmin/Dynastream USB devices:

- ANTUSB2: `0fcf:1008`
- ANTUSB-m: `0fcf:1009`

The App enables:

```yaml
usb: true
udev: true
```

so Home Assistant Supervisor maps raw USB access and the host udev database into the App container.

## Simulation

With `simulation: true`, the bridge emits a repeating one-second power/cadence/heart-rate stream. This lets us validate:

`App -> Mosquitto -> MQTT Discovery -> Home Assistant entities -> training-zone automation`

before the trainer receiver is connected.

## Container images

GitHub Actions builds both:

- `linux/amd64`
- `linux/arm64`

and publishes a multi-architecture image to:

`ghcr.io/deanpemberton/ant-trainer-bridge`

Tags currently include:

- `0.3.0`
- `latest` on the default branch
- Git tag names for `v*` releases

The Home Assistant App references the generic multi-arch image.

### Private repository note

If this repository remains private, the GHCR package may also be private. Home Assistant Supervisor needs to be able to pull the image without interactive GitHub authentication, so the simplest deployment path is to make the **container package public** after the first successful build. The source repository can remain private.

## Install in Home Assistant

Once the GHCR package is pullable:

1. Home Assistant -> Settings -> Apps -> App store.
2. Add this repository:
   `https://github.com/deanpemberton/ant-trainer-bridge`
3. Install **ANT+ Trainer Bridge**.
4. Leave `simulation: true` initially.
5. Start the App and check its logs.
6. Confirm the **ANT+ Trainer** MQTT device/entities appear.
7. When the ANT stick arrives, plug it into the Green, confirm USB detection, then set `simulation: false`.

## Training Cockpit

A ready-to-use sections dashboard template lives at `dashboards/training-cockpit.yaml`. It includes live power, HR, cadence, 3/10/30-second smoothing, session metrics, ANT+ health, Training Mode and the opt-in Zone Lighting switch.

The template assumes the helper entities currently used on the target Home Assistant instance (`sensor.trainer_power_zone`, `input_number.cycling_ftp`, `input_boolean.downstairs_training_mode`, `input_boolean.trainer_zone_lighting`, and `climate.office`).

## Roadmap

1. Prove simulation and MQTT Discovery on the real Home Assistant Green.
2. Verify Garmin ANT stick USB VID/PID.
3. Discover the JetBlack Victory FE-C broadcast.
4. Compare power/cadence against MyWhoosh.
5. Validate smoothing and signal-health metrics against real ANT+ traffic.
6. Drive Training Mode automatically from trainer activity.
7. Drive office Hue colour from sustained training zone when explicitly enabled.

## License

MIT
