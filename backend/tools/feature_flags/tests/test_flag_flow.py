"""Feature-flag-specific behavior. Generic guardrails (G1 to G7) live in backend/tests/."""

from collections.abc import Callable

from fastapi.testclient import TestClient

Login = Callable[[str], TestClient]


def _flag(client: TestClient, key: str, environment: str) -> dict:
    flags = client.get("/api/flags", params={"environment": environment}).json()
    return next(f for f in flags if f["key"] == key)


def _propose(client: TestClient, flag: dict, reason: str = "Rolling out to all users.") -> dict:
    response = client.post(
        f"/api/flags/{flag['id']}/propose",
        json={"enabled": not flag["enabled"], "reason": reason},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _trail(audrey: TestClient, flag: dict) -> list[tuple[str, str]]:
    events = audrey.get("/api/audit", params={"entity": f"feature_flag:{flag['id']}"}).json()
    return [(e["actor"], e["action"]) for e in reversed(events)]


def test_seed_has_six_flags_per_environment(client_for: Login) -> None:
    flags = client_for("audrey").get("/api/flags").json()
    for environment in ("dev", "staging", "prod"):
        keys = [f["key"] for f in flags if f["environment"] == environment]
        assert len(keys) == 6
        assert all(k.startswith("demo_") for k in keys)
    assert all(f["pending_request_id"] is None for f in flags)


def test_engineer_toggles_dev_and_staging_directly_and_it_is_audited(client_for: Login) -> None:
    eli, audrey = client_for("eli"), client_for("audrey")
    for environment in ("dev", "staging"):
        flag = _flag(eli, "demo_dark_mode", environment)
        response = eli.post(
            f"/api/flags/{flag['id']}/toggle", json={"enabled": not flag["enabled"]}
        )
        assert response.status_code == 200, response.text
        assert response.json()["enabled"] is not flag["enabled"]
        assert response.json()["updated_by"] == "eli"

        [event] = audrey.get("/api/audit", params={"entity": f"feature_flag:{flag['id']}"}).json()
        assert (event["actor"], event["role"], event["action"]) == (
            "eli",
            "engineer",
            "flags.flag.toggle",
        )
        assert event["detail"] == {
            "key": "demo_dark_mode",
            "environment": environment,
            "from": flag["enabled"],
            "to": not flag["enabled"],
        }


def test_toggling_to_the_current_value_is_refused(client_for: Login) -> None:
    eli = client_for("eli")
    flag = _flag(eli, "demo_search_v2", "dev")
    response = eli.post(f"/api/flags/{flag['id']}/toggle", json={"enabled": flag["enabled"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_prod_cannot_be_toggled_directly_even_by_a_lead(client_for: Login) -> None:
    lee, audrey = client_for("lee"), client_for("audrey")
    flag = _flag(lee, "demo_new_checkout", "prod")
    response = lee.post(f"/api/flags/{flag['id']}/toggle", json={"enabled": not flag["enabled"]})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"
    assert _flag(lee, "demo_new_checkout", "prod") == flag
    assert _trail(audrey, flag) == []


def test_only_prod_flags_take_a_proposal(client_for: Login) -> None:
    eli = client_for("eli")
    flag = _flag(eli, "demo_new_checkout", "staging")
    response = eli.post(
        f"/api/flags/{flag['id']}/propose", json={"enabled": not flag["enabled"], "reason": "x"}
    )
    assert response.status_code == 409


def test_prod_toggle_waits_for_a_different_lead_and_is_audited(client_for: Login) -> None:
    """The request: Eli asks, Lee (eng lead, not the asker) approves, Audrey sees the trail."""
    eli, lee, audrey = client_for("eli"), client_for("lee"), client_for("audrey")
    flag = _flag(eli, "demo_beta_banner", "prod")
    proposal = _propose(eli, flag)
    request_id = proposal["approval_request_id"]
    assert proposal["flag"]["enabled"] == flag["enabled"]
    assert proposal["flag"]["pending_request_id"] == request_id

    request = next(r for r in lee.get("/api/approvals").json() if r["id"] == request_id)
    assert (request["tool"], request["action"], request["proposed_by"]) == (
        "feature_flags",
        "flags.prod.approve",
        "eli",
    )
    assert request["payload"]["enabled"] is not flag["enabled"]
    assert request["can_decide"] is True

    approved = lee.post(f"/api/approvals/{request_id}/approve", json={"comment": "ok"})
    assert approved.status_code == 200, approved.text
    after = _flag(eli, "demo_beta_banner", "prod")
    assert after["enabled"] is not flag["enabled"]
    assert (after["pending_request_id"], after["updated_by"]) == (None, "lee")

    assert _trail(audrey, flag) == [
        ("eli", "flags.prod.propose"),
        ("lee", "approvals.approve"),
        ("lee", "flags.prod.apply"),
    ]
    roles = {e["action"]: e["role"] for e in audrey.get("/api/audit").json()}
    assert roles["flags.prod.apply"] == "eng_lead"


def test_a_lead_cannot_approve_their_own_prod_toggle(client_for: Login) -> None:
    lee = client_for("lee")
    flag = _flag(lee, "demo_fast_export", "prod")
    request_id = _propose(lee, flag)["approval_request_id"]
    refused = lee.post(f"/api/approvals/{request_id}/approve")
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "self_approval"
    assert _flag(lee, "demo_fast_export", "prod")["enabled"] == flag["enabled"]


def test_rejecting_releases_the_flag_unchanged(client_for: Login) -> None:
    eli, lee, audrey = client_for("eli"), client_for("lee"), client_for("audrey")
    flag = _flag(eli, "demo_sample_widget", "prod")
    request_id = _propose(eli, flag)["approval_request_id"]
    rejected = lee.post(f"/api/approvals/{request_id}/reject", json={"comment": "Not this week."})
    assert rejected.status_code == 200, rejected.text
    assert _flag(eli, "demo_sample_widget", "prod") == flag
    assert _trail(audrey, flag)[-1] == ("lee", "flags.prod.return")
    _propose(eli, flag)  # can be proposed again


def test_one_pending_request_per_prod_flag(client_for: Login) -> None:
    eli = client_for("eli")
    flag = _flag(eli, "demo_dark_mode", "prod")
    _propose(eli, flag)
    again = eli.post(
        f"/api/flags/{flag['id']}/propose", json={"enabled": not flag["enabled"], "reason": "x"}
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "invalid_state"


def test_proposal_needs_a_reason(client_for: Login) -> None:
    eli = client_for("eli")
    flag = _flag(eli, "demo_search_v2", "prod")
    response = eli.post(f"/api/flags/{flag['id']}/propose", json={"enabled": True, "reason": " "})
    assert response.status_code == 422
    assert _flag(eli, "demo_search_v2", "prod") == flag


def test_unknown_flag_is_404(client_for: Login) -> None:
    eli = client_for("eli")
    assert eli.get("/api/flags/999").status_code == 404
    assert eli.post("/api/flags/999/toggle", json={"enabled": True}).status_code == 404
