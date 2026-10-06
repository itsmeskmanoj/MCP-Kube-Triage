import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]
BANNED_IMPORTS = {"kubernetes", "paramiko", "subprocess"}


def test_runtime_has_no_command_or_kubernetes_client_imports() -> None:
    violations: list[str] = []
    for path in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", maxsplit=1)[0] in BANNED_IMPORTS:
                        violations.append(f"{path}:{node.lineno}:{alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module.split(".", maxsplit=1)[0] in BANNED_IMPORTS:
                    violations.append(f"{path}:{node.lineno}:{node.module}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr in {"popen", "system"}
            ):
                violations.append(f"{path}:{node.lineno}:os.{node.func.attr}")

    assert violations == []