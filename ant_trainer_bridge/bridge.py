#!/usr/bin/env python3
import json
import logging
import os
import signal
import sys
import threading
import time
import urllib.request
from pathlib import Path

import paho.mqtt.client as mqtt

OPTIONS_PATH = Path("/data/options.json")
LOG = logging.getLogger("ant-trainer-bridge")


def load_options():
    defaults = {
        "simulation": True,
        "mqtt_host": "",
        "mqtt_port": 1883,
        "mqtt_username": "",
        "mqtt_password": "",
        "mqtt_base_topic": "home/trainer",
        "ant_device_id": 0,
        "hr_device_id": 0,
        "active_power_threshold": 20,
        "active_timeout_seconds": 15,
    }
    if OPTIONS_PATH.exists():
        defaults.update(json.loads(OPTIONS_PATH.read_text()))
    return defaults


def supervisor_mqtt_service():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    request = urllib.request.Request(
        "http://supervisor/services/mqtt",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.load(response)
        if payload.get("result") == "ok":
            return payload.get("data")
    except Exception as exc:
        LOG.warning("Unable to read Supervisor MQTT service: %s", exc)
    return None


def resolve_mqtt(options):
    service = supervisor_mqtt_service()
    if service:
        LOG.info("Using MQTT service supplied by Home Assistant Supervisor")
        return {
            "host": options["mqtt_host"] or service["host"],
            "port": int(service.get("port") or options["mqtt_port"]),
            "username": options["mqtt_username"] or service.get("username", ""),
            "password": options["mqtt_password"] or service.get("password", ""),
            "ssl": bool(service.get("ssl", False)),
        }
    LOG.warning("Supervisor MQTT service unavailable; using configured MQTT settings")
    return {
        "host": options["mqtt_host"] or "core-mosquitto",
        "port": int(options["mqtt_port"]),
        "username": options["mqtt_username"],
        "password": options["mqtt_password"],
        "ssl": False,
    }


class Bridge:
    def __init__(self, options):
        self.o = options
        self.base = self.o["mqtt_base_topic"].rstrip("/")
        self.stop = threading.Event()
        self.last_active = 0.0
        self.latest = {
            "power": 0,
            "cadence": 0,
            "speed": None,
            "heart_rate": None,
            "active": False,
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
        LOG.info("Connecting to MQTT at %s:%s", self.mqtt_config["host"], self.mqtt_config["port"])
        self.mqtt.connect(self.mqtt_config["host"], self.mqtt_config["port"], 60)
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
            "sw_version": "0.2.0",
        }
        availability = [{"topic": f"{self.base}/availability"}]
        entities = {
            "power": {"component":"sensor","name":"Trainer Power","device_class":"power","unit_of_measurement":"W","state_class":"measurement","value_template":"{{ value_json.power }}"},
            "cadence": {"component":"sensor","name":"Trainer Cadence","unit_of_measurement":"rpm","state_class":"measurement","icon":"mdi:rotate-360","value_template":"{{ value_json.cadence }}"},
            "speed": {"component":"sensor","name":"Trainer Speed","unit_of_measurement":"km/h","state_class":"measurement","device_class":"speed","value_template":"{{ value_json.speed if value_json.speed is not none else 'unknown' }}"},
            "heart_rate": {"component":"sensor","name":"Heart Rate","unit_of_measurement":"bpm","state_class":"measurement","device_class":"heart_rate","value_template":"{{ value_json.heart_rate if value_json.heart_rate is not none else 'unknown' }}"},
            "active": {"component":"binary_sensor","name":"Trainer Active","device_class":"running","value_template":"{{ 'ON' if value_json.active else 'OFF' }}","payload_on":"ON","payload_off":"OFF"},
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

    def publish_state(self):
        now = time.monotonic()
        self.latest["active"] = (now - self.last_active) <= int(self.o["active_timeout_seconds"])
        self.mqtt.publish(
            f"{self.base}/state",
            json.dumps(self.latest, separators=(",", ":")),
            retain=False,
        )

    def update(self, power=None, cadence=None, speed=None, heart_rate=None, ant_device_id=None, hr_device_id=None):
        if power is not None:
            try:
                power = int(round(float(power)))
                self.latest["power"] = max(0, power)
                if power >= int(self.o["active_power_threshold"]):
                    self.last_active = time.monotonic()
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
            except (TypeError, ValueError):
                pass
        if ant_device_id is not None:
            self.latest["ant_device_id"] = ant_device_id
        if hr_device_id is not None:
            self.latest["hr_device_id"] = hr_device_id
        self.publish_state()

    def run_simulation(self):
        LOG.info("Simulation mode enabled")
        steps = [
            (0, 0, 82), (85, 78, 98), (125, 84, 110), (165, 88, 124),
            (205, 91, 138), (245, 94, 151), (310, 98, 165), (155, 86, 128),
        ]
        self.latest["ant_device_id"] = 99999
        self.latest["hr_device_id"] = 88888
        while not self.stop.is_set():
            for power, cadence, hr in steps:
                if self.stop.is_set():
                    break
                LOG.info("SIM power=%s W cadence=%s rpm hr=%s bpm", power, cadence, hr)
                self.update(power=power, cadence=cadence, heart_rate=hr)
                self.stop.wait(8)

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
            self.update(ant_device_id=trainer.device_id)

        def on_trainer_data(page, page_name, data):
            try:
                fields = data.to_influx_json({}).get("fields", {})
                self.update(
                    power=fields.get("instantaneous_power"),
                    cadence=fields.get("cadence"),
                    speed=fields.get("speed"),
                    ant_device_id=trainer.device_id,
                )
            except Exception:
                LOG.exception("Failed to decode FE-C data page %s (%s)", page, page_name)

        def on_hr_found():
            LOG.info("ANT+ heart-rate monitor found: device_id=%s", hr.device_id)
            self.update(hr_device_id=hr.device_id)

        def on_hr_data(page, page_name, data):
            if isinstance(data, HeartRateData):
                self.update(
                    heart_rate=data.heart_rate,
                    hr_device_id=hr.device_id,
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
