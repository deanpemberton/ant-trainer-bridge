# Changelog

## 0.3.8
- Add ANT+ FE-C resistance telemetry from General Settings pages.
- Normalize OpenANT's `resistence` field spelling to `resistance` in MQTT state and Home Assistant.
- Add a Trainer Resistance (%) MQTT-discovered sensor and simulator coverage.
- Add regression tests for resistance discovery, valid values, and range rejection.

## 0.3.7
- Keep packet-age diagnostics at 0 while ANT streams are healthy to avoid Home Assistant recorder churn.
- Report packet age in whole seconds only after a stream becomes stale.
- Add regression coverage for healthy/stale packet-age behavior.

## 0.3.6
- Route the actual run_ant teardown path through the safe USB cleanup helper.
- Add regression coverage that checks the production cleanup path, not just the helper in isolation.

## 0.3.5
- Fix clean ANTUSB-m shutdown after privilege drop by releasing libusb resources without attempting privileged kernel-driver reattach.
- Add TDD regression coverage for shutdown cleanup.

## 0.3.4
- Fix ANTUSB-m access on Home Assistant Green by claiming the USB device before permanently dropping privileges.
- Keep simulation mode non-root from process start.
- Add TDD regression coverage for the ANT USB privilege boundary and claim/drop ordering.

## 0.3.3
- Make simulation traverse Z1-Z6 slowly, then recover back down, for real-time cockpit testing.
- Add a regression test requiring full-zone coverage and minimum dwell time per simulated zone.

## 0.3.2
- Fix Home Assistant startup when `/data/options.json` is root-only.
- Entrypoint now copies options into a private file owned by the unprivileged app user, then drops privileges before starting Python.

## 0.3.1
- Require Home Assistant Supervisor-provided MQTT and remove manual broker credential fallback.
- Run the long-lived bridge as unprivileged UID/GID 10001.
- Move runtime base to Python 3.12 slim Trixie and pin its multi-arch digest.
- Exact-pin OpenANT, PyUSB and paho-mqtt runtime dependencies.
- Pin every GitHub Action to an immutable upstream commit SHA.
- Generate image SBOM and provenance.
- Keep OWASP-aligned tests/security scanning in CI.

## 0.3.0
- Add 3 s, 10 s and 30 s power smoothing sensors.
- Add live session elapsed time, average/max power and average/max heart rate.
- Add trainer/HR packet-age sensors and connectivity diagnostics.
- Improve simulation cadence to one sample per second so smoothing and signal-health paths can be tested properly.
- Add a ready-to-use Training Cockpit Lovelace dashboard template.

## 0.2.1
- Fix Home Assistant MQTT discovery schema for heart-rate and speed sensors.

## 0.2.0
- Add simultaneous ANT+ heart-rate reception for Garmin HR straps.
- Publish heart rate and HR ANT device ID through MQTT Discovery.
- Extend simulation mode with heart-rate data.
- Use Home Assistant Supervisor MQTT service discovery.

## 0.1.0
- Initial Home Assistant App packaging.
- MQTT Discovery and simulated trainer telemetry.
- Passive OpenANT FE-C listener.
- USB/udev access for Garmin/Dynastream ANT sticks.
