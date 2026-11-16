"""G5: core imports no tool. No tool imports another tool.

Checked twice: statically over every source file (including function-level and importlib
imports), and at runtime by importing every module in a clean interpreter."""

import ast
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests import discover

BACKEND = Path(__file__).resolve().parent.parent


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(BACKEND).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path) -> Iterator[tuple[int, str]]:
    """(line, absolute module) for every import in a file, relative imports resolved."""
    name = _module_name(path)
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = importlib.util.resolve_name("." * node.level + base, package)
            if base != "tools":
                yield node.lineno, base
            for alias in node.names:
                yield node.lineno, f"{base}.{alias.name}"
        elif isinstance(node, ast.Call):
            func = node.func
            called = getattr(func, "attr", None) or getattr(func, "id", None)
            if called in {"import_module", "__import__"} and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    yield node.lineno, arg.value


def _tool_of(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != "tools":
        return None
    return parts[1] if len(parts) > 1 else ""


def _sources(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*.py"))


def test_core_source_imports_no_tool() -> None:
    bad = [
        f"{path.relative_to(BACKEND)}:{line} imports {module}"
        for path in _sources(BACKEND / "core")
        for line, module in _imports(path)
        if _tool_of(module) is not None
    ]
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("tool", discover.tool_names())
def test_tool_source_imports_no_other_tool(tool: str) -> None:
    bad = [
        f"{path.relative_to(BACKEND)}:{line} imports {module}"
        for path in _sources(BACKEND / "tools" / tool)
        for line, module in _imports(path)
        if _tool_of(module) not in (None, tool)
    ]
    assert not bad, "\n".join(bad)


_PROBE = """
import importlib, json, pkgutil, sys
from core import policy
root = importlib.import_module(sys.argv[1])
if root.__name__.startswith("tools."):
    # As main.load_tool does: a tool's grants are registered before its routes are imported.
    perms = importlib.import_module(root.__name__ + ".permissions")
    policy.register_permissions(root.__name__, perms.NAMESPACE, perms.PERMISSIONS)
for info in pkgutil.walk_packages(root.__path__, root.__name__ + "."):
    importlib.import_module(info.name)
print(json.dumps(sorted(m for m in sys.modules if m == "tools" or m.startswith("tools."))))
"""


def _loaded_tool_modules(package: str) -> list[str]:
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, package],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return list(json.loads(result.stdout.strip().splitlines()[-1]))


def test_importing_all_of_core_loads_no_tool() -> None:
    assert _loaded_tool_modules("core") == []


@pytest.mark.parametrize("tool", discover.tool_names())
def test_importing_a_tool_loads_no_other_tool(tool: str) -> None:
    others = [m for m in _loaded_tool_modules(f"tools.{tool}") if _tool_of(m) not in ("", tool)]
    assert not others, others
