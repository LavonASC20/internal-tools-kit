"""G7: no tool grants or registers an action outside its own namespace. A foreign action, a
duplicate namespace or a core namespace fails."""

import pytest

import main
from core import approvals, policy
from tests import discover
from tests.conftest import ToolMaker

TOOLS = discover.tool_names()


# The tools as loaded -----------------------------------------------------------------------


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_grants_only_its_own_namespace(tool: str) -> None:
    ns = discover.tool_namespace(tool)
    foreign = sorted(a for a in discover.tool_grants(tool) if discover.namespace(a) != ns)
    assert not foreign, f"tools.{tool} grants actions outside {ns!r}: {foreign}"
    assert policy.namespace_owner(ns) == f"tools.{tool}"


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_namespace_is_not_a_core_namespace(tool: str) -> None:
    assert discover.tool_namespace(tool) not in discover.core_namespaces()


def test_tool_namespaces_are_unique() -> None:
    namespaces = [discover.tool_namespace(t) for t in TOOLS]
    assert len(namespaces) == len(set(namespaces)), namespaces


def test_every_granted_action_comes_from_its_namespace_owner() -> None:
    """The live grants match what each owner declared, so nothing was added out of band."""
    owners = {discover.tool_namespace(t): t for t in TOOLS}
    for action in sorted(policy.all_actions()):
        ns = discover.namespace(action)
        owner = policy.namespace_owner(ns)
        assert owner is not None, f"{action} is granted but its namespace has no owner"
        if owner == policy.CORE:
            continue
        tool = owners.get(ns)
        assert tool is not None and owner == f"tools.{tool}", f"{ns!r} is owned by {owner}"
        declared = discover.tool_grants(tool).get(action, frozenset())
        assert policy.roles_for(action) == declared, (
            f"{action} is granted to {sorted(policy.roles_for(action))}, "
            f"but tools.{tool} declares {sorted(declared)}"
        )


@pytest.mark.parametrize("kind", discover.approval_kinds(), ids=lambda k: k.action)
def test_approval_kinds_stay_in_their_tool_namespace(kind: approvals.ApprovalKind) -> None:
    assert kind.tool in TOOLS, f"approval kind {kind.action} names unknown tool {kind.tool!r}"
    grants = discover.tool_grants(kind.tool)
    for action in (kind.action, kind.propose_action):
        assert action in grants, f"{action} is not declared by tools.{kind.tool}"


@pytest.mark.parametrize("tool", TOOLS)
def test_tool_routes_declare_actions_of_their_own_namespace(tool: str) -> None:
    ns = discover.tool_namespace(tool)
    for route in discover.tool_routes()[tool]:
        action = policy.route_action(route)
        assert (
            action is None or discover.namespace(action) == ns
        ), f"tools.{tool} route {route.path} declares {action}, outside {ns!r}"


# A throwaway tool trying to break the rule ---------------------------------------------------

OWN = 'NAMESPACE = "g7probe"\nPERMISSIONS = {"g7probe.item.read": {"g7_role"}}\n'

TOOL_ACTIONS = sorted(a for t in TOOLS for a in discover.tool_grants(t))
CORE_NAMESPACES = sorted(discover.core_namespaces())


def _refused(throwaway_tool: ToolMaker, **files: str) -> None:
    before_grants, before_kinds = policy.grants(), approvals.kinds()
    throwaway_tool("g7probe", **files)
    with pytest.raises((RuntimeError, TypeError, ValueError)):
        main.create_app()
    after = policy.grants()
    changed = {
        a
        for a in set(before_grants) | set(after)
        if not a.startswith("g7probe.") and before_grants.get(a) != after.get(a)
    }
    assert not changed, f"a refused tool still changed grants for {sorted(changed)}"
    assert approvals.kinds() == before_kinds


def test_a_tool_in_its_own_namespace_loads(throwaway_tool: ToolMaker) -> None:
    """Control: the probe below is refused for its rule break, not for being malformed."""
    throwaway_tool("g7probe", permissions=OWN)
    main.create_app()
    assert policy.roles_for("g7probe.item.read") == {"g7_role"}


@pytest.mark.parametrize("action", TOOL_ACTIONS)
def test_granting_another_tools_action_fails(action: str, throwaway_tool: ToolMaker) -> None:
    permissions = (
        f'NAMESPACE = "g7probe"\n'
        f'PERMISSIONS = {{"g7probe.item.read": {{"r"}}, "{action}": {{"g7_intruder"}}}}\n'
    )
    _refused(throwaway_tool, permissions=permissions)


@pytest.mark.parametrize("tool", TOOLS)
@pytest.mark.parametrize("same_grants", [False, True], ids=["new-grants", "identical-grants"])
def test_claiming_another_tools_namespace_fails(
    tool: str, same_grants: bool, throwaway_tool: ToolMaker
) -> None:
    ns = discover.tool_namespace(tool)
    grants = (
        {a: sorted(r) for a, r in discover.tool_grants(tool).items()}
        if same_grants
        else {f"{ns}.probe.read": ["g7_intruder"]}
    )
    _refused(throwaway_tool, permissions=f'NAMESPACE = "{ns}"\nPERMISSIONS = {grants!r}\n')


@pytest.mark.parametrize("ns", CORE_NAMESPACES)
def test_claiming_a_core_namespace_fails(ns: str, throwaway_tool: ToolMaker) -> None:
    actions = sorted(a for a in policy.all_actions() if discover.namespace(a) == ns)
    grants = {a: ["g7_intruder"] for a in actions} or {f"{ns}.probe.read": ["g7_intruder"]}
    _refused(throwaway_tool, permissions=f'NAMESPACE = "{ns}"\nPERMISSIONS = {grants!r}\n')


def _kind_routes(tool: str, action: str, propose_action: str) -> str:
    return f"""
from core import approvals
from core.approvals import ApprovalKind
from core.policy import PolicyRouter

router = PolicyRouter()

approvals.register(
    ApprovalKind(
        tool={tool!r},
        action={action!r},
        propose_action={propose_action!r},
        on_approve=lambda conn, request, user: None,
    )
)
"""


@pytest.mark.parametrize("action", TOOL_ACTIONS + [f"{n}.probe.x" for n in CORE_NAMESPACES])
@pytest.mark.parametrize("role", ["action", "propose_action"])
def test_registering_an_approval_kind_with_a_foreign_action_fails(
    action: str, role: str, throwaway_tool: ToolMaker
) -> None:
    own = "g7probe.item.read"
    decide, propose = (action, own) if role == "action" else (own, action)
    _refused(throwaway_tool, permissions=OWN, routes=_kind_routes("g7probe", decide, propose))


@pytest.mark.parametrize("kind", discover.approval_kinds(), ids=lambda k: k.action)
def test_registering_an_approval_kind_as_another_tool_fails(
    kind: approvals.ApprovalKind, throwaway_tool: ToolMaker
) -> None:
    routes = _kind_routes(kind.tool, kind.action, kind.propose_action)
    _refused(throwaway_tool, permissions=OWN, routes=routes)


def test_policy_is_frozen_after_startup() -> None:
    assert policy.is_frozen()
    with pytest.raises(RuntimeError):
        policy.register_permissions("tools.g7late", "g7late", {"g7late.x.read": {"r"}})
