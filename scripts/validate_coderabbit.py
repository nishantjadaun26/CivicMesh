"""Validate YAML against the official schema; download it explicitly before running."""

import json
import sys
from pathlib import Path

import jsonschema
import yaml

root = Path(__file__).resolve().parents[1]
schema_path = (
    Path(sys.argv[1]) if len(sys.argv) > 1 else root / ".cache/coderabbit-schema.json"
)
schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
config = yaml.safe_load((root / ".coderabbit.yaml").read_text(encoding="utf-8"))
jsonschema.validators.validator_for(schema)(schema).validate(config)
print("CodeRabbit configuration validates against the official schema.")
