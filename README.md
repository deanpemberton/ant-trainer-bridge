# ANT+ Trainer Bridge

Home Assistant App that listens passively to an ANT+ FE-C smart trainer and publishes live trainer telemetry to Home Assistant through MQTT Discovery.

Initial target hardware:

- Home Assistant Green (aarch64)
- Garmin/Dynastream ANTUSB2 or ANTUSB-m USB stick
- JetBlack Victory smart trainer
- MyWhoosh remains the trainer controller (Wi-Fi); this bridge only listens to ANT+ FE-C
- Home Assistant Mosquitto broker

## Status

Early development. The MQTT and Home Assistant Discovery path can be exercised now using **simulation mode** before an ANT+ USB stick is connected.

The real ANT+ backend uses [OpenANT](https://github.com/Tigge/openant) and attaches passively to the first ANT+ Fitness Equipment device it sees (or an explicitly configured ANT device ID).

## Repository layout

- `ant_trainer_bridge/` - Home Assistant App
- `.github/workflows/build.yml` - multi-architecture GHCR build
- `repository.yaml` - Home Assistant custom App repository metadata

## Home Assistant App

The app has raw USB and udev access so OpenANT can claim a Dynastream/Garmin ANT stick.

Default options are deliberately safe:

- `simulation: true`
- MQTT host defaults to `core-mosquitto`
- MQTT credentials are supplied in the App configuration
- real ANT+ mode is not enabled until `simulation` is turned off

### Simulated telemetry

Simulation publishes a repeating workout-like pattern so the full path can be tested:

`bridge -> Mosquitto -> MQTT Discovery -> Home Assistant sensors`

The Home Assistant MQTT device exposes:

- Trainer Power (W)
- Trainer Cadence (rpm)
- Trainer Speed (km/h, when available)
- Trainer Active
- ANT Device ID
- Bridge Status

## Container images

GitHub Actions builds Linux/amd64 and Linux/arm64 images and publishes a multi-arch image:

`ghcr.io/deanpemberton/ant-trainer-bridge:<version>`

The Home Assistant App points at the generic multi-arch image.

> If this repository remains private, GHCR packages normally inherit private visibility. Home Assistant Supervisor cannot anonymously pull a private package. For direct App installation, make the GHCR package public or use a registry authentication approach. For initial development, the App can also be built locally from this repository.

## Development roadmap

1. Prove MQTT Discovery with simulation mode.
2. Plug Garmin ANT stick into Home Assistant Green and verify USB VID/PID (expected `0fcf:1008` or `0fcf:1009`).
3. Disable simulation and discover the JetBlack Victory FE-C broadcast.
4. Validate power/cadence against MyWhoosh.
5. Add smoothed power and training-zone entities.
6. Use trainer activity to drive Home Assistant Training Mode and office Hue zone colours.

## License

MIT
