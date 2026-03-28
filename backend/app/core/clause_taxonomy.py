"""Clause taxonomy loaded from config/clause_types.yaml (ADR-006).

Single source of truth for clause types, descriptions, risk weights,
and LLM prompt generation. Adding a new type requires only a YAML change.
"""
import logging
from pathlib import Path
from typing import Dict, List

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "clause_types.yaml"

# Loaded once at module import
_config: Dict = {}
_clause_types: Dict[str, Dict] = {}


def _load_config():
    global _config, _clause_types
    with open(CONFIG_PATH) as f:
        _config = yaml.safe_load(f)
    _clause_types = _config.get("clause_types", {})
    logger.info(f"Loaded {len(_clause_types)} clause types from {CONFIG_PATH.name}")


_load_config()


def get_clause_types() -> Dict[str, Dict]:
    """Get all clause type definitions."""
    return _clause_types


def get_valid_type_keys() -> List[str]:
    """Get list of valid clause type keys."""
    return list(_clause_types.keys())


def get_risk_weights() -> Dict[str, float]:
    """Get risk weight mapping for all clause types."""
    return {key: cfg["risk_weight"] for key, cfg in _clause_types.items()}


def build_clause_types_prompt_section() -> str:
    """Build the clause types section of the classification prompt."""
    lines = []
    for key, cfg in _clause_types.items():
        lines.append(f"- {key}: {cfg['description']}")
    return "\n".join(lines)


def build_literal_type_values() -> tuple:
    """Get clause type keys as a tuple for Literal type hint."""
    return tuple(_clause_types.keys())
