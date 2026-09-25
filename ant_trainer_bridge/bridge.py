#!/usr/bin/env python3
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt

OPTIONS_PATH = Path("/data/options.json")
LOG = logging.getLogger("ant-trainer-bridge")


def load_options():
    defaults = {
        "simulation": True,
        "mqtt_host": "core-mosquitto",
        "mqtt_port": 1883,
        "mqtt_username": "",
        "mqtt_password": "",
        "mqtt_base_topic": "home/trainer",
        "ant_device_id": 0,
        "active_power_threshold": 20,
        "active_timeout_seconds": 15,
    }
    if OPTIONS_PATH.exists():
        defaults.update(json.loads(OPTIONS_PATH.read_text()))
    return defaults


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
            "active": False,
            "ant_device_id": None,
            "source": "simulation" if self.o["simulation"] else "ant",
        }

        self.mqtt = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="ant-trainer-bridge",
        )
        if self.o["mqtt_username"]:
            self.mqtt.username_pw_set(
                self.o["mqtt_username"],
                self.o["mqtt_password"],
            )
        self.mqtt.will_set(f"{self.base}/availability", "offline", retain=True)

    def connect(self):
        LOG.info("Connecting to MQTT at %s:%s", self.o["mqtt_host"], self.o["mqtt_port"])
        self.mqtt.connect(self.o["mqtt_host"], int(self.o["mqtt_port"]), 60)
        self.mqtt.loop_start()
        self.mqtt.publish(f"{self.base}/availability", "online", retain=True)
        self.publish_discovery()
        self.publish_state()

    def publish_discovery(self):
        device = {
            "identifiers": ["ant_trainer_bridge"],
            "name": "ANT+ Trainer",
            "manufacturer": "ANT+",
            "model": "FE-C Bridge",
            "sw_version": "0.1.0",
        }
        availability = [{"topic": f"{self.base}/availability"}]
        entities = {
            "power": {
                "component": "sensor",
                "name": "Trainer Power",
                "device_class": "power",
                "unit_of_measurement": "W",
                "state_class": "measurement",
                "value_template": "{{ value_json.power }}",
            },
            "cadence": {
                "component": "sensor",
                "name": "Trainer Cadence",
                "unit_of_measurement": "rpm",
                "state_class": "measurement",
                "icon": "mdi:rotate-360",
                "value_template": "{{ value_json.cadence }}",
            },
            "speed": {
                "component": "sensor",
                "name": "Trainer Speed",
                "unit_of_measurement": "km/h",
                "state_class": "measurement",
                "device_class": "speed",
                "value_template": "{{ value_json.speed if value_json.speed is not none else 'unknown' }}",
            },
            "active": {
                "component": "binary_sensor",
                "name": "Trainer Active",
                "device_class": "running",
                "value_template": "{{ 'ON' if value_json.active else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
            },
            "ant_device_id": {
                "component": "sensor",
                "name": "ANT Device ID",
                "icon": "mdi:identifier",
                "value_template": "{{ value_json.ant_device_id if value_json.ant_device_id is not none else 'unknown' }}",
                "entity_category": "diagnostic",
            },
            "source": {
                "component": "sensor",
                "name": "Bridge Source",
                "icon": "mdi:source-branch",
                "value_template": "{{ value_json.source }}",
                "entity_category": "diagnostic",
            },
        }
        for object_id, cfg in entities.items():
            component = cfg.pop("component")
            payload = {
                **cfg,
                "unique_id": f"ant_trainer_bridge_{object_id}",
                "state_topic": f"{self.base}/state",
                "availability": availability,
                "device": device,
            }
            topic = f"homeassistant/{component}/ant_trainer_bridge/{object_id}/config"
            self.mqtt.publish(topic, json.dumps(payload), retain=True)

    def publish_state(self):
        now = time.monotonic()
        self.latest["active"] = (now - self.last_active) <= int(
            self.o["active_timeout_seconds"]
        )
        self.mqtt.publish(
            f"{self.base}/state",
            json.dumps(self.latest, separators=(",", ":")),
            retain=False,
        )

    def update(self, power=None, cadence=None, speed=None, ant_device_id=None):
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
                    # ANT+ Fitness Equipment speed is decoded by OpenANT in m/s.
                    self.latest["speed"] = round(speed * 3.6, 1)
            except (TypeError, ValueError):
                pass
        if ant_device_id is not None:
            self.latest["ant_device_id"] = ant_device_id
        self.publish_state()

    def run_simulation(self):
        LOG.info("Simulation mode enabled")
        steps = [
            (0, 0), (85, 78), (125, 84), (165, 88),
            (205, 91), (245, 94), (310, 98), (155, 86)
        ]
        self.latest["ant_device_id"] = 99999
        while not self.stop.is_set():
            for power, cadence in steps:
                if self.stop.is_set():
                    break
                LOG.info("SIM power=%s W cadence=%s rpm", power, cadence)
                self.update(power=power, cadence=cadence)
                self.stop.wait(8)

    def run_ant(self):
        from openant.easy.node import Node
        from openant.devices import ANTPLUS_NETWORK_KEY
        from openant.devices.fitness_equipment import FitnessEquipment

        LOG.info("Starting passive ANT+ FE-C listener; requested device id=%s", self.o["ant_device_id"])
        node = Node()
        node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
        device = FitnessEquipment(node, device_id=int(self.o["ant_device_id"]))

        def on_found():
            LOG.info("ANT+ fitness equipment found: device_id=%s", device.device_id)
            self.latest["ant_device_id"] = device.device_id
            self.publish_state()

        def on_data(page, page_name, data):
            try:
                fields = data.to_influx_json({}).get("fields", {})
                self.update(
                    power=fields.get("instantaneous_power"),
                    cadence=fields.get("cadence"),
                    speed=fields.get("speed"),
                    ant_device_id=device.device_id,
                )
            except Exception:
                LOG.exception("Failed to decode FE-C data page %s (%s)", page, page_name)

        device.on_found = on_found
        device.on_device_data = on_data

        try:
            node.start()
        finally:
            try:
                device.close_channel()
            finally:
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
