"""Core tests run against core only: no tool is imported, and registries are restored after each
test so tests can register throwaway namespaces."""

import copy
from collections.abc import Iterator

import pytest

from core import approvals, policy


@pytest.fixture(autouse=True)
def isolated_registries() -> Iterator[None]:
    saved = (
        copy.deepcopy(policy._grants),
        dict(policy._namespace_owners),
        dict(policy._registered),
        policy._frozen,
        dict(approvals._kinds),
    )
    policy._frozen = False
    yield
    grants, owners, registered, frozen, kinds = saved
    policy._grants.clear()
    policy._grants.update(grants)
    policy._namespace_owners.clear()
    policy._namespace_owners.update(owners)
    policy._registered.clear()
    policy._registered.update(registered)
    policy._frozen = frozen
    approvals._kinds.clear()
    approvals._kinds.update(kinds)
