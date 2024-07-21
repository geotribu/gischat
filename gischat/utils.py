from pathlib import Path

import toml


def get_version() -> str:
    v = "unknown"
    pyproject_toml_file = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
        data = toml.load(pyproject_toml_file)
        # check tool.poetry.version
        if (
            "tool" in data
            and "poetry" in data["tool"]
            and "version" in data["tool"]["poetry"]
        ):
            v = data["tool"]["poetry"]["version"]
    return v
