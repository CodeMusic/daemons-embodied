"""The rules the design fixes, held by reading the code itself (CLAUDE.md, "Rules the design fixes")."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}


def code_files(*under: str) -> list[Path]:
    roots = [ROOT / u for u in under] if under else [ROOT]
    return sorted(p for r in roots for p in r.rglob("*.py") if not SKIP & set(p.relative_to(ROOT).parts))


def text_files() -> list[Path]:
    kinds = {".py", ".md", ".yaml", ".yml", ".toml", ".txt", ".html", ".js", ".css", ".json", ".sh", ".service"}
    return sorted(
        p for p in ROOT.rglob("*") if p.is_file() and p.suffix in kinds and not SKIP & set(p.relative_to(ROOT).parts)
    )


def _called_names(tree: ast.AST, bare: bool = True, dotted: bool = True):
    """Every call's name: `name(...)` when bare, `something.name(...)` when dotted."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if bare and isinstance(f, ast.Name):
                yield f.id, node
            elif dotted and isinstance(f, ast.Attribute):
                yield f.attr, node


def test_no_eval_and_no_shell_anywhere():
    """Rule 1: nothing a model wrote ever reaches a driver. There is no eval and no shell for it to reach."""
    builtins = {"eval", "exec", "compile", "__import__"}  # as bare calls; re.compile is not one
    shells = {"system", "popen", "spawnl", "spawnv", "execv", "execl", "startfile"}  # as os.something
    banned_modules = {"subprocess", "pty", "commands", "pickle", "marshal", "shelve"}
    found = []
    for file in code_files("embodied", "wrappers", "tools"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for name, node in _called_names(tree, dotted=False):
            if name in builtins:
                found.append(f"{file.relative_to(ROOT)}:{node.lineno} calls {name}()")
        for name, node in _called_names(tree, bare=False):
            if name in shells:
                found.append(f"{file.relative_to(ROOT)}:{node.lineno} calls .{name}()")
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n in banned_modules:
                    found.append(f"{file.relative_to(ROOT)}:{node.lineno} imports {n}")
    assert found == []


def test_yaml_is_only_ever_read_as_data():
    found = []
    for file in code_files():
        for name, node in _called_names(ast.parse(file.read_text(encoding="utf-8"))):
            if name in {"load", "load_all", "unsafe_load", "full_load"} and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "yaml":
                    found.append(f"{file.relative_to(ROOT)}:{node.lineno} calls yaml.{name}()")
    assert found == []


def test_command_is_reachable_from_no_action():
    """`command(raw)` is for a developer's own code. Nothing in the repository calls it."""
    found = []
    for file in code_files("embodied", "wrappers", "tools"):
        for name, node in _called_names(ast.parse(file.read_text(encoding="utf-8"))):
            if name == "command":
                found.append(f"{file.relative_to(ROOT)}:{node.lineno}")
    assert found == []


def test_the_word_is_spelled_one_way():
    """DAEMONS is said DAY-mons, and the other spelling of the word is never written."""
    other = "de" + "mon"
    found = [str(f.relative_to(ROOT)) for f in text_files() if other in f.read_text(encoding="utf-8").lower()]
    assert found == []
