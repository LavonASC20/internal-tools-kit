"""G6: a caller without the PII action never receives raw PII values.

PII fields are discovered from the response models of every route. Raw values are collected by
a caller holding every role. Then, for each role, every route is called (writes first, so the
approvals and audit trails have content) and no raw value of a PII action the role lacks may
appear anywhere in any response.
"""

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import policy
from tests import discover
from tests.conftest import add_user, login

PII_ACTIONS = discover.pii_actions()
ROLES = [r for r in discover.roles() if any(not discover.holds(r, a) for a in PII_ACTIONS)]

READS = [
    e
    for e in discover.endpoints()
    if e.method == "GET" and (e.action is not None or discover.may_omit_action(e.route))
]
WRITES = [e for e in discover.endpoints() if e.method != "GET" and e.action is not None]

# Shorter values are only matched exactly, so they cannot collide with unrelated text.
MIN_SUBSTRING = 6


def _call(client: TestClient, endpoint: discover.Endpoint) -> httpx.Response:
    path = discover.sample_path(endpoint.route)
    body = discover.sample_body(endpoint.route)
    if endpoint.method in discover.BODY_METHODS and body is not None:
        return client.request(endpoint.method, path, json=body)
    return client.request(endpoint.method, path)


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


def _raw_values(app: FastAPI) -> dict[str, set[str]]:
    everyone = login(app, add_user(policy.all_roles(), "g6_reader_all"))
    found: dict[str, set[str]] = {}
    for endpoint in READS:
        response = _call(everyone, endpoint)
        if response.status_code == 200:
            discover.collect_pii(endpoint.route.response_model, response.json(), found)
    return found


def _leaks(body: Any, raw: dict[str, set[str]], lacking: set[str]) -> list[str]:
    leaks = []
    for value in discover.string_leaves(body):
        for action in lacking:
            for secret in raw.get(action, ()):
                if value == secret or (len(secret) >= MIN_SUBSTRING and secret in value):
                    leaks.append(f"{action} value {secret!r}")
    return leaks


@pytest.mark.parametrize("role", ROLES)
def test_callers_without_the_pii_action_never_see_raw_pii(role: str, app: FastAPI) -> None:
    lacking = {a for a in PII_ACTIONS if not discover.holds(role, a)}
    caller = login(app, add_user(discover.role_set(role), "g6_caller"))
    responses: list[tuple[str, httpx.Response]] = []

    responses += [(f"{e.id} as {role}", _call(caller, e)) for e in WRITES]
    for actor in ("g6_writer_a", "g6_writer_b"):
        writer = login(app, add_user(policy.all_roles(), actor))
        for endpoint in WRITES:
            _call(writer, endpoint)
    responses += [(f"{e.id} as {role}", _call(caller, e)) for e in READS]

    raw = _raw_values(app)
    missing = lacking - {a for a, values in raw.items() if values}
    assert not missing, f"no PII values could be read for {sorted(missing)}; seed some data"

    leaks = [
        f"{where}: {leak}"
        for where, response in responses
        for leak in _leaks(_json(response), raw, lacking)
    ]
    assert not leaks, "\n".join(leaks)


def test_pii_fields_are_discovered() -> None:
    """Guards against a vacuous G6: some route returns a model with PII fields."""
    assert discover.pii_models(), "no route returns a PiiModel with pii_field()s"
    assert ROLES, "every role holds every PII action, so G6 checks nothing"
