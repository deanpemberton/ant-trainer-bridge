#!/usr/bin/env python3
import json
import logging
import os
import signal
import sys
import threading
import time
import http.client
from collections import deque
from pathlib import Path

import paho.mqtt.client as mqtt

OPTIONS_PATH = Path(os.environ.get("ANT_OPTIONS_PATH", "/data/options.json"))
LOG = logging.getLogger("ant-trainer-bridge")


def load_options():
    defaults = {
        "simulation": True,
        "mqtt_base_topic": "home/trainer",
        "ant_device_id": 0,
        "hr_device_id": 0,
        "active_power_threshold": 20,
        "active_timeout_seconds": 15,
        "packet_stale_seconds": 5,
    }
    if OPTIONS_PATH.exists():
        defaults.update(json.loads(OPTIONS_PATH.read_text()))
    return defaults


def supervisor_mqtt_service():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None

    connection = http.client.HTTPConnection("supervisor", timeout=5)
    try:
        connection.request(
            "GET",
            "/services/mqtt",
            headers={"Authorization": f"Bearer {token}"},
        )
        response = connection.getresponse()
        if response.status != 200:
            LOG.warning("Supervisor MQTT service returned HTTP %s", response.status)
            return None
        payload = json.load(response)
        if payload.get("result") == "ok":
            return payload.get("data")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        LOG.warning("Unable to read Supervisor MQTT service: %s", exc)
    finally:
        connection.close()
    return None


def resolve_mqtt(options):
    service = supervisor_mqtt_service()
    if not service:
        raise RuntimeError(
            "Home Assistant Supervisor MQTT service is required; "
            "manual broker credentials are intentionally unsupported"
        )

    LOG.info("Using MQTT service supplied by Home Assistant Supervisor")
    return {
        "host": service["host"],
        "port": int(service["port"]),
        "username": service.get("username", ""),
        "password": service.get("password", ""),
        "ssl": bool(service.get("ssl", False)),
    }


class Bridge:
    def __init__(self, options):
        self.o = options
        self.base = self.o["mqtt_base_topic"].rstrip("/")
        self.stop = threading.Event()
        self.lock = threading.Lock()

        self.last_active = 0.0
        self.last_trainer_packet = None
        self.last_hr_packet = None
        self.session_started = None
        self.session_power_sum = 0.0
        self.session_power_count = 0
        self.session_power_max = 0
        self.session_hr_sum = 0.0
        self.session_hr_count = 0
        self.session_hr_max = 0
        self.power_samples = deque()

        self.latest = {
            "power": 0,
            "power_3s": 0,
            "power_10s": 0,
            "power_30s": 0,
            "cadence": 0,
            "speed": None,
            "heart_rate": None,
            "active": False,
            "session_elapsed": 0,
            "session_avg_power": 0,
            "session_max_power": 0,
            "session_avg_hr": 0,
            "session_max_hr": 0,
            "trainer_packet_age": None,
            "hr_packet_age": None,
            "trainer_signal_ok": False,
            "hr_signal_ok": False,
            "ant_device_id": None,
            "hr_device_id": None,
            "source": "simulation" if self.o["simulation"] else "ant",
        }

        self.mqtt_config = resolve_mqtt(options)
        self.mqtt = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="ant-trainer-bridge",
        )
        if self.mqtt_config["username"]:
            self.mqtt.username_pw_set(
                self.mqtt_config["username"],
                self.mqtt_config["password"],
            )
        if self.mqtt_config["ssl"]:
            self.mqtt.tls_set()
        self.mqtt.will_set(f"{self.base}/availability", "offline", retain=True)

    def connect(self):
        LOG.info(
            "Connecting to MQTT at %s:%s",
            self.mqtt_config["host"],
            self.mqtt_config["port"],
        )
        self.mqtt.connect(
            self.mqtt_config["host"],
            self.mqtt_config["port"],
            60,
        )
        self.mqtt.loop_start()
        self.mqtt.publish(f"{self.base}/availability", "online", retain=True)
        self.publish_discovery()
        self.publish_state()

    def publish_discovery(self):
        device = {
            "identifiers": ["ant_trainer_bridge"],
            "name": "ANT+ Training Telemetry",
            "manufacturer": "ANT+",
            "model": "FE-C + HR Bridge",
            "sw_version": "0.3.2",
        }
        availability = [{"topic": f"{self.base}/availability"}]
        entities = {
            "power": {"component":"sensor","name":"Trainer Power","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.power }}"},
            "power_3s": {"component":"sensor","name":"Power 3s","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.power_3s }}"},
            "power_10s": {"component":"sensor","name":"Power 10s","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.power_10s }}"},
            "power_30s": {"component":"sensor","name":"Power 30s","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.power_30s }}"},
            "cadence": {"component":"sensor","name":"Trainer Cadence","unit_of_measurement":"rpm","state_class":"measurement","icon":"mdi:rotate-360","value_template":"{{ value_json.cadence }}"},
            "speed": {"component":"sensor","name":"Trainer Speed","unit_of_measurement":"km/h","state_class":"measurement","device_class":"speed","value_template":"{{ value_json.speed if value_json.speed is not none else 0 }}"},
            "heart_rate": {"component":"sensor","name":"Heart Rate","unit_of_measurement":"bpm","state_class":"measurement","icon":"mdi:heart-pulse","value_template":"{{ value_json.heart_rate if value_json.heart_rate is not none else 0 }}"},
            "active": {"component":"binary_sensor","name":"Trainer Active","device_class":"running","value_template":"{{ 'ON' if value_json.active else 'OFF' }}","payload_on":"ON","payload_off":"OFF"},
            "session_elapsed": {"component":"sensor","name":"Session Elapsed","device_class":"duration","unit_of_measurement":"s","state_class":"measurement","value_template":"{{ value_json.session_elapsed }}"},
            "session_avg_power": {"component":"sensor","name":"Session Average Power","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.session_avg_power }}"},
            "session_max_power": {"component":"sensor","name":"Session Max Power","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.session_max_power }}"},
            "session_avg_hr": {"component":"sensor","name":"Session Average Heart Rate","unit_of_measurement":"bpm","state_class":"measurement","icon":"mdi:heart-pulse","value_template":"{{ value_json.session_avg_hr }}"},
            "session_max_hr": {"component":"sensor","name":"Session Max Heart Rate","unit_of_measurement":"bpm","state_class":"measurement","icon":"mdi:heart-pulse","value_template":"{{ value_json.session_max_hr }}"},
            "trainer_packet_age": {"component":"sensor","name":"Trainer Packet Age","device_class":"duration","unit_of_measurement":"s","state_class":"measurement","entity_category":"diagnostic","value_template":"{{ value_json.trainer_packet_age if value_json.trainer_packet_age is not none else 999 }}"},
            "hr_packet_age": {"component":"sensor","name":"HR Packet Age","device_class":"duration","unit_of_measurement":"s","state_class":"measurement","entity_category":"diagnostic","value_template":"{{ value_json.hr_packet_age if value_json.hr_packet_age is not none else 999 }}"},
            "trainer_signal_ok": {"component":"binary_sensor","name":"Trainer Signal","device_class":"connectivity","entity_category":"diagnostic","value_template":"{{ 'ON' if value_json.trainer_signal_ok else 'OFF' }}","payload_on":"ON","payload_off":"OFF"},
            "hr_signal_ok": {"component":"binary_sensor","name":"HR Signal","device_class":"connectivity","entity_category":"diagnostic","value_template":"{{ 'ON' if value_json.hr_signal_ok else 'OFF' }}","payload_on":"ON","payload_off":"OFF"},
            "ant_device_id": {"component":"sensor","name":"Trainer ANT Device ID","icon":"mdi:identifier","value_template":"{{ value_json.ant_device_id if value_json.ant_device_id is not none else 'unknown' }}","entity_category":"diagnostic"},
            "hr_device_id": {"component":"sensor","name":"HR ANT Device ID","icon":"mdi:identifier","value_template":"{{ value_json.hr_device_id if value_json.hr_device_id is not none else 'unknown' }}","entity_category":"diagnostic"},
            "source": {"component":"sensor","name":"Bridge Source","icon":"mdi:source-branch","value_template":"{{ value_json.source }}","entity_category":"diagnostic"},
        }
        for object_id, config in entities.items():
            config = dict(config)
            component = config.pop("component")
            payload = {
                **config,
                "unique_id": f"ant_trainer_bridge_{object_id}",
                "state_topic": f"{self.base}/state",
                "availability": availability,
                "device": device,
            }
            topic = f"homeassistant/{component}/ant_trainer_bridge/{object_id}/config"
            self.mqtt.publish(topic, json.dumps(payload), retain=True)

    def _window_average(self, seconds, now):
        values = [value for ts, value in self.power_samples if now - ts <= seconds]
        return int(round(sum(values) / len(values))) if values else 0

    def _reset_session(self, now):
        self.session_started = now
        self.session_power_sum = 0.0
        self.session_power_count = 0
        self.session_power_max = 0
        self.session_hr_sum = 0.0
        self.session_hr_count = 0
        self.session_hr_max = 0

    def _refresh_derived(self, now):
        while self.power_samples and now - self.power_samples[0][0] > 30:
            self.power_samples.popleft()

        active = (now - self.last_active) <= int(self.o["active_timeout_seconds"])
        if active and self.session_started is None:
            self._reset_session(now)
        elif not active and self.session_started is not None:
            self.session_started = None

        self.latest["active"] = active
        self.latest["power_3s"] = self._window_average(3, now)
        self.latest["power_10s"] = self._window_average(10, now)
        self.latest["power_30s"] = self._window_average(30, now)
        self.latest["session_elapsed"] = (
            int(now - self.session_started) if self.session_started is not None else 0
        )
        self.latest["session_avg_power"] = (
            int(round(self.session_power_sum / self.session_power_count))
            if self.session_power_count else 0
        )
        self.latest["session_max_power"] = self.session_power_max
        self.latest["session_avg_hr"] = (
            int(round(self.session_hr_sum / self.session_hr_count))
            if self.session_hr_count else 0
        )
        self.latest["session_max_hr"] = self.session_hr_max

        stale = float(self.o["packet_stale_seconds"])
        self.latest["trainer_packet_age"] = (
            round(now - self.last_trainer_packet, 1)
            if self.last_trainer_packet is not None else None
        )
        self.latest["hr_packet_age"] = (
            round(now - self.last_hr_packet, 1)
            if self.last_hr_packet is not None else None
        )
        self.latest["trainer_signal_ok"] = (
            self.last_trainer_packet is not None
            and now - self.last_trainer_packet <= stale
        )
        self.latest["hr_signal_ok"] = (
            self.last_hr_packet is not None
            and now - self.last_hr_packet <= stale
        )

    def publish_state(self):
        with self.lock:
            now = time.monotonic()
            self._refresh_derived(now)
            payload = json.dumps(self.latest, separators=(",", ":"))
        self.mqtt.publish(f"{self.base}/state", payload, retain=False)

    def status_loop(self):
        while not self.stop.wait(1):
            self.publish_state()

    def update(self, power=None, cadence=None, speed=None, heart_rate=None,
               ant_device_id=None, hr_device_id=None, trainer_packet=False,
               hr_packet=False):
        with self.lock:
            now = time.monotonic()

            if trainer_packet:
                self.last_trainer_packet = now
            if hr_packet:
                self.last_hr_packet = now

            if power is not None:
                try:
                    power = max(0, int(round(float(power))))
                    self.latest["power"] = power
                    self.power_samples.append((now, power))
                    if power >= int(self.o["active_power_threshold"]):
                        if (now - self.last_active) > int(self.o["active_timeout_seconds"]):
                            self._reset_session(now)
                        self.last_active = now
                    if self.session_started is not None or power >= int(self.o["active_power_threshold"]):
                        self.session_power_sum += power
                        self.session_power_count += 1
                        self.session_power_max = max(self.session_power_max, power)
                except (TypeError, ValueError):
                    pass

            if cadence is not None:
                try:
                    cadence = int(round(float(cadence)))
                    if 0 <= cadence < 255:
                        self.latest["cadence"] = cadence
                except (TypeError, ValueError):
                    pass

            if speed is not None:
                try:
                    speed = float(speed)
                    if 0 <= speed < 65.535:
                        self.latest["speed"] = round(speed * 3.6, 1)
                except (TypeError, ValueError):
                    pass

            if heart_rate is not None:
                try:
                    heart_rate = int(round(float(heart_rate)))
                    if 20 <= heart_rate <= 250:
                        self.latest["heart_rate"] = heart_rate
                        if self.session_started is not None:
                            self.session_hr_sum += heart_rate
                            self.session_hr_count += 1
                            self.session_hr_max = max(self.session_hr_max, heart_rate)
                except (TypeError, ValueError):
                    pass

            if ant_device_id is not None:
                self.latest["ant_device_id"] = ant_device_id
            if hr_device_id is not None:
                self.latest["hr_device_id"] = hr_device_id

            self._refresh_derived(now)
            payload = json.dumps(self.latest, separators=(",", ":"))

        self.mqtt.publish(f"{self.base}/state", payload, retain=False)

    def run_simulation(self):
        LOG.info("Simulation mode enabled")
        steps = [
            (0, 0, 82, 5), (85, 78, 98, 8), (125, 84, 110, 8),
            (165, 88, 124, 8), (205, 91, 138, 8), (245, 94, 151, 8),
            (310, 98, 165, 8), (155, 86, 128, 8),
        ]
        self.latest["ant_device_id"] = 99999
        self.latest["hr_device_id"] = 88888

        while not self.stop.is_set():
            for power, cadence, hr, duration in steps:
                for _ in range(duration):
                    if self.stop.is_set():
                        return
                    LOG.info(
                        "SIM power=%s W cadence=%s rpm hr=%s bpm",
                        power, cadence, hr,
                    )
                    self.update(
                        power=power,
                        cadence=cadence,
                        heart_rate=hr,
                        trainer_packet=True,
                        hr_packet=True,
                    )
                    self.stop.wait(1)

    def run_ant(self):
        from openant.easy.node import Node
        from openant.devices import ANTPLUS_NETWORK_KEY
        from openant.devices.fitness_equipment import FitnessEquipment
        from openant.devices.heart_rate import HeartRate, HeartRateData

        LOG.info(
            "Starting passive ANT+ listeners; trainer id=%s hr id=%s",
            self.o["ant_device_id"],
            self.o["hr_device_id"],
        )
        node = Node()
        node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
        trainer = FitnessEquipment(node, device_id=int(self.o["ant_device_id"]))
        hr = HeartRate(node, device_id=int(self.o["hr_device_id"]))

        def on_trainer_found():
            LOG.info("ANT+ fitness equipment found: device_id=%s", trainer.device_id)
            self.update(ant_device_id=trainer.device_id, trainer_packet=True)

        def on_trainer_data(page, page_name, data):
            try:
                fields = data.to_influx_json({}).get("fields", {})
                self.update(
                    power=fields.get("instantaneous_power"),
                    cadence=fields.get("cadence"),
                    speed=fields.get("speed"),
                    ant_device_id=trainer.device_id,
                    trainer_packet=True,
                )
            except Exception:
                LOG.exception(
                    "Failed to decode FE-C data page %s (%s)",
                    page, page_name,
                )

        def on_hr_found():
            LOG.info("ANT+ heart-rate monitor found: device_id=%s", hr.device_id)
            self.update(hr_device_id=hr.device_id, hr_packet=True)

        def on_hr_data(page, page_name, data):
            if isinstance(data, HeartRateData):
                self.update(
                    heart_rate=data.heart_rate,
                    hr_device_id=hr.device_id,
                    hr_packet=True,
                )

        trainer.on_found = on_trainer_found
        trainer.on_device_data = on_trainer_data
        hr.on_found = on_hr_found
        hr.on_device_data = on_hr_data

        try:
            node.start()
        finally:
            for device in (trainer, hr):
                try:
                    device.close_channel()
                except Exception:
                    LOG.exception("Error closing ANT+ channel")
            node.stop()

    def close(self):
        self.stop.set()
        try:
            self.mqtt.publish(f"{self.base}/availability", "offline", retain=True)
            self.mqtt.disconnect()
            self.mqtt.loop_stop()
        except Exception:
            LOG.exception("Error while shutting down MQTT")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    options = load_options()
    bridge = Bridge(options)

    def shutdown(signum, frame):
        LOG.info("Signal %s received; shutting down", signum)
        bridge.close()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        bridge.connect()
        threading.Thread(
            target=bridge.status_loop,
            name="status-publisher",
            daemon=True,
        ).start()
        if options["simulation"]:
            bridge.run_simulation()
        else:
            bridge.run_ant()
    except Exception:
        LOG.exception("Bridge terminated with an error")
        bridge.close()
        raise


if __name__ == "__main__":
    main()
