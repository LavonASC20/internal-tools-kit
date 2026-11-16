"""G2: for every route and every role, the response is 403 exactly when the role lacks the
declared action. The request is the same for every role and carries a malformed body, so a
role without the action must be refused before validation."""

import httpx
import pytest
from fastapi.testclient import TestClient

from tests import discover
from tests.conftest import ClientFor

MALFORMED = b'{"not valid json'

CASES = [(e, role) for e in discover.endpoints() for role in discover.roles()]


def _call(client: TestClient, endpoint: discover.Endpoint) -> httpx.Response:
    path = discover.sample_path(endpoint.route)
    if endpoint.method in discover.BODY_METHODS:
        return client.request(
            endpoint.method, path, content=MALFORMED, headers={"content-type": "application/json"}
        )
    return client.request(endpoint.method, path)


@pytest.mark.parametrize(("endpoint", "role"), CASES, ids=[f"{e.id} as {r}" for e, r in CASES])
def test_403_exactly_when_the_role_lacks_the_action(
    endpoint: discover.Endpoint, role: str, client_with_roles: ClientFor
) -> None:
    response = _call(client_with_roles(discover.role_set(role)), endpoint)
    action = endpoint.action
    if action is not None and not discover.holds(role, action):
        assert (
            response.status_code == 403
        ), f"{role} lacks {action} but got {response.status_code}: {response.text}"
        assert response.json()["error"]["code"] == "forbidden"
    else:
        assert (
            response.status_code != 403
        ), f"{role} holds {action or 'no action needed'} but got 403: {response.text}"


GUARDED = [e for e in discover.endpoints() if e.action is not None]


@pytest.mark.parametrize("endpoint", GUARDED, ids=[e.id for e in GUARDED])
def test_anonymous_callers_get_401(endpoint: discover.Endpoint, client: TestClient) -> None:
    response = _call(client, endpoint)
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthenticated"
