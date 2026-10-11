"""Bounded synthetic asset inventory for report-time contextualization."""

import json
from pathlib import Path

from soc_triage.models import validate_identifier


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate inventory key.")
        result[key] = value
    return result


def load_inventory(path: Path) -> dict:
    with Path(path).open("rb") as source:
        raw = source.read(65_537)
    if len(raw) > 65_536:
        raise ValueError("Inventory exceeds the byte limit.")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(data, dict) or set(data) != {
        "schema_version",
        "data_kind",
        "assets",
    }:
        raise ValueError("Invalid inventory structure.")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ValueError("Unsupported inventory schema.")
    if data["data_kind"] != "synthetic":
        raise ValueError("This inventory adapter is for synthetic data.")
    if not isinstance(data["assets"], list) or len(data["assets"]) > 100:
        raise ValueError("Invalid asset collection.")

    inventory = {}
    for asset in data["assets"]:
        if not isinstance(asset, dict) or set(asset) != {
            "hostname",
            "criticality",
            "owner",
        }:
            raise ValueError("Invalid asset fields.")
        validate_identifier(asset["hostname"])
        validate_identifier(asset["owner"])
        if not isinstance(asset["criticality"], str) or asset["criticality"] not in {
            "LOW",
            "MEDIUM",
            "HIGH",
        }:
            raise ValueError("Invalid asset criticality.")
        if asset["hostname"] in inventory:
            raise ValueError("Duplicate asset hostname.")
        inventory[asset["hostname"]] = dict(asset)
    return inventory


def lookup_asset(inventory: dict, hostname: str) -> dict:
    asset = inventory.get(hostname)
    return {
        "status": "found" if asset is not None else "missing",
        "source": "synthetic_local_inventory",
        "asset": dict(asset) if asset is not None else None,
    }
