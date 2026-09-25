import importlib
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def bridge_module(monkeypatch):
    module = importlib.import_module("ant_trainer_bridge.bridge")

    class FakeMqttClient:
        def __init__(self, *args, **kwargs):
            self.published = []
            self.connected = None
            self.credentials = None
            self.will = None
            self.loop_started = False

        def username_pw_set(self, username, password):
            self.credentials = (username, password)

        def tls_set(self):
            self.tls = True

        def will_set(self, topic, payload, retain=False):
            self.will = (topic, payload, retain)

        def connect(self, host, port, keepalive):
            self.connected = (host, port, keepalive)

        def loop_start(self):
            self.loop_started = True

        def loop_stop(self):
            self.loop_started = False

        def publish(self, topic, payload, retain=False):
            self.published.append((topic, payload, retain))

        def disconnect(self):
            pass

    monkeypatch.setattr(module.mqtt, "Client", FakeMqttClient)
    monkeypatch.setattr(
        module,
        "supervisor_mqtt_service",
        lambda: {
            "host": "mqtt.test",
            "port": 1883,
            "username": "user",
            "password": "pass",
            "ssl": False,
        },
    )
    return module
