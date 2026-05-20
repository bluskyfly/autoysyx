"""TASK_CONTRACT JSON schema and extraction from worker stdout."""
from __future__ import annotations

import json
import re
from typing import Any

import jsonschema

CONTRACT_BEGIN = "====TASK_CONTRACT_BEGIN===="
CONTRACT_END = "====TASK_CONTRACT_END===="

# Worker MUST emit a JSON blob between the two markers conforming to this schema.
CONTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "task_id",
        "files_changed",
        "key_decisions",
        "run_commands",
        "artifacts",
        "known_risks",
        "open_issues",
        "self_test_passed",
        "self_test_output_tail",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "files_changed": {"type": "array", "items": {"type": "string"}},
        "key_decisions": {"type": "array"},
        "run_commands": {"type": "array", "items": {"type": "string"}},
        "artifacts": {"type": "array", "items": {"type": "string"}},
        "known_risks": {"type": "array"},
        "open_issues": {"type": "array"},
        "self_test_passed": {"type": "boolean"},
        "self_test_output_tail": {"type": "string"},
    },
    "additionalProperties": True,
}

_PATTERN = re.compile(
    re.escape(CONTRACT_BEGIN) + r"\s*(.+?)\s*" + re.escape(CONTRACT_END),
    re.DOTALL,
)


class ContractError(Exception):
    """Raised when worker output cannot be parsed as a valid TASK_CONTRACT."""


def extract_contract(worker_output: str) -> dict[str, Any]:
    match = _PATTERN.search(worker_output)
    if not match:
        raise ContractError("TASK_CONTRACT markers not found in worker output")
    raw = match.group(1).strip()
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ContractError(f"contract body is not valid JSON: {e}") from e
    try:
        jsonschema.validate(contract, CONTRACT_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ContractError(f"contract failed schema validation: {e.message}") from e
    return contract
