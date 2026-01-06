from pathlib import Path

import toml

QCHAT_CHEATCODES = [
    "givemesomecheese",
    "lookattheflickofqgis",
    "iamarobot",
    "its10oclock",
    "qgisprolicense",
]


def get_uv_version() -> str:
    v = "unknown"
    pyproject_toml_file = Path(__file__).parent.parent / "pyproject.toml"

    if pyproject_toml_file.exists() and pyproject_toml_file.is_file():
        data = toml.load(pyproject_toml_file)

        if "project" in data and "version" in data["project"]:
            v = data["project"]["version"]

    return v
