"""Tests for orchestrator.contract."""
import pytest

from orchestrator.contract import (
    CONTRACT_BEGIN,
    CONTRACT_END,
    ContractError,
    extract_contract,
)


def test_extract_valid_contract_returns_dict():
    text = f"""... preamble ...
{CONTRACT_BEGIN}
{{
  "task_id": "F1",
  "files_changed": [],
  "key_decisions": [],
  "run_commands": ["ls"],
  "artifacts": [],
  "known_risks": [],
  "open_issues": [],
  "self_test_passed": true,
  "self_test_output_tail": "ok"
}}
{CONTRACT_END}
"""
    contract = extract_contract(text)
    assert contract["task_id"] == "F1"
    assert contract["self_test_passed"] is True


def test_extract_missing_markers_raises():
    with pytest.raises(ContractError, match="markers not found"):
        extract_contract("no markers here")


def test_extract_invalid_json_raises():
    text = f"{CONTRACT_BEGIN}\nnot json\n{CONTRACT_END}"
    with pytest.raises(ContractError, match="not valid JSON"):
        extract_contract(text)


def test_extract_missing_required_field_raises():
    text = f'{CONTRACT_BEGIN}\n{{"task_id": "F1"}}\n{CONTRACT_END}'
    with pytest.raises(ContractError, match="schema"):
        extract_contract(text)


def test_extract_wrong_type_raises():
    bad = f"""{CONTRACT_BEGIN}
{{
  "task_id": "F1",
  "files_changed": "should be array",
  "key_decisions": [],
  "run_commands": [],
  "artifacts": [],
  "known_risks": [],
  "open_issues": [],
  "self_test_passed": true,
  "self_test_output_tail": "ok"
}}
{CONTRACT_END}"""
    with pytest.raises(ContractError, match="schema"):
        extract_contract(bad)
