import pytest

from core import policy

GRANTS = {"probe.item.read": {"reader"}, "probe.pii.read": {"reader"}}


def test_namespace_grants_register_once() -> None:
    policy.register_permissions("tools.probe", "probe", GRANTS)
    policy.register_permissions("tools.probe", "probe", GRANTS)
    with pytest.raises(RuntimeError, match="already registered"):
        policy.register_permissions("tools.probe", "probe", {"probe.pii.read": {"intruder"}})
    assert policy.declared_roles_for("probe.pii.read") == {"reader"}


def test_another_owner_cannot_claim_a_namespace() -> None:
    policy.register_permissions("tools.probe", "probe", GRANTS)
    with pytest.raises(RuntimeError, match="belongs to tools.probe"):
        policy.register_permissions("tools.other", "probe", GRANTS)


def test_grants_outside_the_namespace_are_refused() -> None:
    with pytest.raises(RuntimeError, match="may only grant other"):
        policy.register_permissions("tools.other", "other", {"probe.pii.read": {"x"}})
    assert (
        policy.namespace_owner("other") is None
        or policy.declared_roles_for("probe.pii.read") == set()
    )


@pytest.mark.parametrize("namespace", ["audit", "approvals"])
def test_core_namespaces_belong_to_core(namespace: str) -> None:
    with pytest.raises(RuntimeError, match="belongs to core"):
        policy.register_permissions("tools.probe", namespace, {f"{namespace}.x": {"r"}})


def test_frozen_policy_refuses_new_grants_but_allows_identical_repeats() -> None:
    policy.register_permissions("tools.probe", "probe", GRANTS)
    policy.freeze()
    policy.register_permissions("tools.probe", "probe", GRANTS)
    with pytest.raises(RuntimeError, match="frozen"):
        policy.register_permissions("tools.late", "late", {"late.x": {"r"}})
    with pytest.raises(RuntimeError, match="frozen"):
        policy.claim_namespace("tools.late", "late")
