# Changelog

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
