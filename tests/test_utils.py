from typing import Any


def is_subdict(small: dict[str, Any], big: dict[str, Any]) -> bool:
    return big | small == big


def is_in_dicts(message: dict[str, Any], dict_lists: list[dict[str, Any]]) -> bool:
    return any(is_subdict(message, item) for item in dict_lists)
