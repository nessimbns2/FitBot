"""
tests/test_macro_units.py
The stored profile weight is always in kg: switching the profile to imperial
must not change the calculated targets. Only a weight sent in the request
itself can be in pounds.
"""

from __future__ import annotations

CALC = "/api/nutrition/calculate-macros"
PROFILE = "/api/user/profile"


def _set_profile(client, **extra):
    body = {"weight_kg": 80, "height_cm": 180, "age": 30, "sex": "male"}
    body.update(extra)
    assert client.put(PROFILE, json=body).status_code == 200


def test_imperial_profile_gives_same_targets_as_metric(client):
    _set_profile(client, unit_system="metric")
    metric = client.post(CALC, json={}).json()

    client.put(PROFILE, json={"unit_system": "imperial"})
    imperial = client.post(CALC, json={}).json()

    assert imperial["bmr"] == metric["bmr"]
    assert imperial["target_kcal"] == metric["target_kcal"]
    assert imperial["protein_g"] == metric["protein_g"]


def test_request_weight_in_pounds_is_converted(client):
    _set_profile(client)
    in_kg = client.post(CALC, json={"weight_kg": 80}).json()
    in_lb = client.post(CALC, json={"weight_kg": 176.37, "weight_unit": "lb"}).json()
    assert in_lb["bmr"] == in_kg["bmr"]
    assert in_lb["target_kcal"] == in_kg["target_kcal"]


def test_request_weight_without_unit_is_kg(client):
    _set_profile(client)
    explicit = client.post(CALC, json={"weight_kg": 90, "weight_unit": "kg"}).json()
    plain = client.post(CALC, json={"weight_kg": 90}).json()
    assert plain["bmr"] == explicit["bmr"]


def test_weight_unit_lb_without_a_weight_does_not_convert_profile(client):
    _set_profile(client)
    base = client.post(CALC, json={}).json()
    flagged = client.post(CALC, json={"weight_unit": "lb"}).json()
    assert flagged["bmr"] == base["bmr"]
