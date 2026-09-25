import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = ROOT / "ant_trainer_bridge" / "bridge.py"


@pytest.fixture
def bridge_module(monkeypatch):
    spec = importlib.util.spec_from_file_location("bridge_under_test", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["bridge_under_test"] = module
    spec.loader.exec_module(module)

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
        "resolve_mqtt",
        lambda options: {
            "host": "mqtt.test",
            "port": 1883,
            "username": "user",
            "password": "pass",
            "ssl": False,
        },
    )
    return module
