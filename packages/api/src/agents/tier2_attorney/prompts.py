"""Prompts for the Motion Drafter Agent: versioned files in src/prompts/motion_drafter/."""

import json

from src.prompts import load_prompt

SYSTEM = load_prompt("motion_drafter.system", "v1")
DRAFT = load_prompt("motion_drafter.draft", "v1")


def build_motion_user_prompt(
    motion_type: str,
    template: dict,
    case_data: dict,
) -> str:
    """Build the user prompt for a specific motion type with case data."""
    return DRAFT.text.format(
        title_template=template["title_template"],
        sections_desc=json.dumps(template["sections"], indent=2),
        georgia_notes="\n".join(f"- {n}" for n in template.get("georgia_specific_notes", [])),
        case_data=json.dumps(case_data, indent=2, default=str),
    )
