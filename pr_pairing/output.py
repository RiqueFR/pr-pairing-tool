import json
from datetime import datetime, timezone
from typing import Any


def format_output_json(
    developers: list,
    params: dict
) -> str:
    """Format assignments as JSON."""
    from .models import KnowledgeMode
    
    assignments = []
    for dev in developers:
        assignments.append({
            "developer": dev.name,
            "reviewers": dev.reviewers
        })
    
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "parameters": {
            "input": params.get("input", ""),
            "reviewers": params.get("reviewers", 0),
            "team_mode": params.get("team_mode", False),
            "knowledge_mode": params.get("knowledge_mode", KnowledgeMode.ANYONE.value)
        },
        "assignments": assignments
    }
    
    return json.dumps(output, indent=2)


def format_output_yaml(
    developers: list,
    params: dict
) -> str:
    """Format assignments as YAML."""
    from .models import KnowledgeMode
    
    lines = []
    lines.append(f"generated_at: \"{datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}\"")
    lines.append("parameters:")
    lines.append(f"  input: {params.get('input', '')}")
    lines.append(f"  reviewers: {params.get('reviewers', 0)}")
    lines.append(f"  team_mode: {str(params.get('team_mode', False)).lower()}")
    lines.append(f"  knowledge_mode: {params.get('knowledge_mode', KnowledgeMode.ANYONE.value)}")
    lines.append("assignments:")
    
    for dev in developers:
        lines.append(f"  - developer: {dev.name}")
        if dev.reviewers:
            lines.append("    reviewers:")
            for reviewer in dev.reviewers:
                lines.append(f"      - {reviewer}")
        else:
            lines.append("    reviewers: []")
    
    return "\n".join(lines)


def get_output_format(output_path: str | None, output_format_arg: str | None) -> str:
    """Determine output format based on file extension and explicit format argument.
    
    Priority:
    1. If output_format_arg is explicitly provided, use it
    2. If output_path ends with .json, use json
    3. If output_path ends with .yaml or .yml, use yaml
    4. Default to csv
    """
    if output_format_arg:
        return output_format_arg
    
    if output_path:
        if output_path.endswith(".json"):
            return "json"
        elif output_path.endswith(".yaml") or output_path.endswith(".yml"):
            return "yaml"
    
    return "csv"


def write_output(content: str, filepath: str) -> None:
    """Write content to file."""
    from .models import FileError
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise FileError(f"Error writing output file: {e}")
