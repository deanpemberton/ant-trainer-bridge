import json


def make_bridge(module, **overrides):
    options = {
        "simulation": True,
        "mqtt_base_topic": "home/trainer",
        "ant_device_id": 0,
        "hr_device_id": 0,
        "active_power_threshold": 20,
        "active_timeout_seconds": 15,
        "packet_stale_seconds": 5,
    }
    options.update(overrides)
    return module.Bridge(options)


def test_load_options_merges_file(tmp_path, monkeypatch, bridge_module):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"simulation": False, "ant_device_id": 123}))
    monkeypatch.setattr(bridge_module, "OPTIONS_PATH", path)

    result = bridge_module.load_options()

    assert result["simulation"] is False
    assert result["ant_device_id"] == 123


def test_resolve_mqtt_prefers_supervisor(monkeypatch, bridge_module):
    monkeypatch.setattr(
        bridge_module,
        "supervisor_mqtt_service",
        lambda: {
            "host": "broker",
            "port": 1884,
            "username": "sup-user",
            "password": "sup-pass",
            "ssl": True,
        },
    )

    result = bridge_module.resolve_mqtt({})

    assert result == {
        "host": "broker",
        "port": 1884,
        "username": "sup-user",
        "password": "sup-pass",
        "ssl": True,
    }


def test_resolve_mqtt_requires_supervisor(monkeypatch, bridge_module):
    monkeypatch.setattr(bridge_module, "supervisor_mqtt_service", lambda: None)

    try:
        bridge_module.resolve_mqtt({})
    except RuntimeError as exc:
        assert "Supervisor MQTT service is required" in str(exc)
    else:
        raise AssertionError("resolve_mqtt should fail closed without Supervisor MQTT")


def test_discovery_contains_smoothing_session_and_health_entities(bridge_module):
    bridge = make_bridge(bridge_module)
    bridge.publish_discovery()

    topics = {topic for topic, _, _ in bridge.mqtt.published}

    expected_suffixes = {
        "power_3s",
        "power_10s",
        "power_30s",
        "heart_rate",
        "session_elapsed",
        "session_avg_power",
        "session_max_power",
        "session_avg_hr",
        "session_max_hr",
        "trainer_packet_age",
        "hr_packet_age",
        "trainer_signal_ok",
        "hr_signal_ok",
    }
    for suffix in expected_suffixes:
        assert any(f"/{suffix}/config" in topic for topic in topics)


def test_power_windows_and_session_stats(monkeypatch, bridge_module):
    clock = {"now": 100.0}
    monkeypatch.setattr(bridge_module.time, "monotonic", lambda: clock["now"])
    bridge = make_bridge(bridge_module)

    bridge.update(power=100, cadence=80, heart_rate=120, trainer_packet=True, hr_packet=True)
    clock["now"] = 102.0
    bridge.update(power=200, cadence=85, heart_rate=130, trainer_packet=True, hr_packet=True)
    clock["now"] = 106.0
    bridge.update(power=300, cadence=90, heart_rate=140, trainer_packet=True, hr_packet=True)

    assert bridge.latest["power_3s"] == 300
    assert bridge.latest["power_10s"] == 200
    assert bridge.latest["power_30s"] == 200
    assert bridge.latest["session_avg_power"] == 200
    assert bridge.latest["session_max_power"] == 300
    assert bridge.latest["session_avg_hr"] == 130
    assert bridge.latest["session_max_hr"] == 140
    assert bridge.latest["active"] is True


def test_signal_health_goes_stale(monkeypatch, bridge_module):
    clock = {"now": 100.0}
    monkeypatch.setattr(bridge_module.time, "monotonic", lambda: clock["now"])
    bridge = make_bridge(bridge_module, packet_stale_seconds=5)

    bridge.update(power=100, heart_rate=120, trainer_packet=True, hr_packet=True)
    assert bridge.latest["trainer_signal_ok"] is True
    assert bridge.latest["hr_signal_ok"] is True

    clock["now"] = 106.0
    bridge.publish_state()

    assert bridge.latest["trainer_signal_ok"] is False
    assert bridge.latest["hr_signal_ok"] is False
    assert bridge.latest["trainer_packet_age"] == 6.0
    assert bridge.latest["hr_packet_age"] == 6.0


def test_session_ends_after_inactivity(monkeypatch, bridge_module):
    clock = {"now": 100.0}
    monkeypatch.setattr(bridge_module.time, "monotonic", lambda: clock["now"])
    bridge = make_bridge(bridge_module, active_timeout_seconds=15)

    bridge.update(power=100, trainer_packet=True)
    assert bridge.latest["active"] is True
    assert bridge.session_started is not None

    clock["now"] = 116.0
    bridge.publish_state()

    assert bridge.latest["active"] is False
    assert bridge.latest["session_elapsed"] == 0
    assert bridge.session_started is None


def test_invalid_hr_and_cadence_are_ignored(bridge_module):
    bridge = make_bridge(bridge_module)
    bridge.latest["heart_rate"] = 120
    bridge.latest["cadence"] = 80

    bridge.update(heart_rate=300, cadence=255)

    assert bridge.latest["heart_rate"] == 120
    assert bridge.latest["cadence"] == 80


def test_speed_is_converted_from_mps_to_kph(bridge_module):
    bridge = make_bridge(bridge_module)

    bridge.update(speed=10)

    assert bridge.latest["speed"] == 36.0


def test_connect_publishes_availability_discovery_and_state(bridge_module):
    bridge = make_bridge(bridge_module)

    bridge.connect()

    assert bridge.mqtt.connected == ("mqtt.test", 1883, 60)
    assert bridge.mqtt.credentials == ("user", "pass")
    assert ("home/trainer/availability", "online", True) in bridge.mqtt.published
    assert any(topic.endswith("/config") for topic, _, _ in bridge.mqtt.published)
    assert any(topic == "home/trainer/state" for topic, _, _ in bridge.mqtt.published)
