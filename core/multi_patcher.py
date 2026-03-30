"""
core/multi_patcher.py

Handles tasks that require patching more than one file.
The LLM is asked to identify all affected files and generate
a patch for each one. Each patch is validated independently.
"""

from pathlib import Path
import json

from core.llm_client import get_client
from core.unity_scanner import find_relevant_files
from core.proposal_validator import validate_patch_for_file as _default_validator
from core.risk_classifier import classify_risk
from core.llm_client import extract_json, ANTHROPIC_MODEL as OPENAI_MODEL

# All known script names (without .cs) for named-file extraction
KNOWN_SCRIPTS = [
    "GameManager", "RoundManager", "MainMenuManager",
    "HumanTurnUI", "RevealUI", "FieldUI", "ResultsUI",
    "TurnTransitionUI", "PauseMenuUI", "PlayerAreaUI", "CardUIButton",
    "PlayerState", "GameState", "GameSettings", "CardData",
    "CardEffectResolver", "ScoringSystem", "AIPlayerController",
]

# Keywords that strongly suggest a multi-file task
MULTI_FILE_SIGNALS = [
    "rename",
    "refactor",
    "move",
    "interface",
    "all players",
    "all ui",
    "every",
    "across",
    "propagate",
    "sync",
    "scoring",
    "gamemanager and",
    "roundmanager and",
    "playerstate and",
]

MAX_FILES_PER_TASK = 4


def is_multi_file_task(task_title: str) -> bool:
    lower = task_title.lower()
    # Signal keyword match
    if any(signal in lower for signal in MULTI_FILE_SIGNALS):
        return True
    # Two or more named scripts mentioned in the title
    mentioned = [s for s in KNOWN_SCRIPTS if s.lower() in lower]
    return len(mentioned) >= 2


def extract_named_files(task_title: str, project_scripts: list[str]) -> list[str]:
    """
    Returns paths from project_scripts whose filename matches
    a script name mentioned in the task title.
    """
    lower = task_title.lower()
    matched = []
    for path in project_scripts:
        name = Path(path).stem.lower()
        if name in lower:
            matched.append(path)
    return matched


def generate_multi_file_proposal(
    task_title: str,
    file_contents: dict[str, str],
    filtered_log: str = "",
    attempt: int = 1,
) -> list[dict]:
    """
    Ask the LLM to generate patches for multiple files at once.

    Returns a list of dicts:
    [
        { "file_path": str, "new_content": str, "diagnosis": str, "summary": str },
        ...
    ]
    """
    client = get_client()

    files_block = "\n\n".join(
        f"--- FILE: {path} ---\n{content}"
        for path, content in file_contents.items()
    )

    retry_note = ""
    if attempt == 2:
        retry_note = "\nCRITICAL: Previous attempt returned incomplete files. Every file in patches must contain its COMPLETE content — no truncation, no placeholders."
    elif attempt == 3:
        retry_note = "\nFINAL ATTEMPT: Return every file verbatim with only the minimal required changes. Do not omit any methods, fields, or using directives."

    system_prompt = f"""
You are a senior Unity engineer.

You are generating SAFE patch proposals for multiple Unity C# files.

Rules:
- Return VALID JSON only. No markdown wrapping.
- Return a JSON object with a single key "patches" containing an array.
- Each patch must have: file_path, new_content, diagnosis, summary.
- ALWAYS return the COMPLETE file content for each patched file.
- Never truncate, summarize, or use placeholder comments like "// ... rest unchanged".
- Only include files that actually need changes. Skip files that are fine.
- Make the smallest safe change possible in each file.
- Do not invent APIs that don't exist.{retry_note}

Return format:
{{
  "patches": [
    {{
      "file_path": "...",
      "new_content": "...",
      "diagnosis": "...",
      "summary": "..."
    }}
  ]
}}
"""

    user_prompt = f"""
Task:
{task_title}

Files to consider:
{files_block}

Relevant Unity logs:
{filtered_log[:2000]}

Return a JSON object with a "patches" array. Only include files that need changes.
"""

    response = client.messages.create(
        model=OPENAI_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ]
    )

    raw_text = response.content[0].text.strip()
    json_text = extract_json(raw_text)
    data = json.loads(json_text)

    patches = data.get("patches", [])
    if not isinstance(patches, list):
        raise ValueError("LLM returned patches field that is not a list.")

    return patches


def validate_multi_file_patches(
    patches: list[dict],
    original_contents: dict[str, str],
) -> tuple[list[dict], list[str]]:
    """
    Validate each patch independently.
    Returns (valid_patches, errors).
    valid_patches only contains patches that passed validation.
    """
    valid = []
    all_errors = []

    for patch in patches:
        file_path = patch.get("file_path", "")
        new_content = patch.get("new_content", "").strip()

        if not new_content:
            all_errors.append(f"{Path(file_path).name}: LLM returned empty content.")
            continue

        original = original_contents.get(file_path, "")

        # Use project-specific validator if injected
        try:
            import agents.code_agent as _ca
            validator_fn = (
                _ca._project_validator.validate_patch_for_file
                if _ca._project_validator and hasattr(_ca._project_validator, 'validate_patch_for_file')
                else _default_validator
            )
        except Exception:
            validator_fn = _default_validator

        result = validator_fn(
            file_path=file_path,
            original_text=original,
            proposed_text=new_content,
        )

        if result.is_valid:
            patch["validation"] = result
            valid.append(patch)
        else:
            all_errors.append(
                f"{Path(file_path).name}: " + "; ".join(result.errors)
            )

    return valid, all_errors


def classify_multi_file_risk(
    patches: list[dict],
    original_contents: dict[str, str],
) -> tuple[str, list[str]]:
    """
    Returns the highest risk level across all patches and combined reasons.
    If any file is high risk, the whole set is high risk.
    """
    all_reasons = []
    highest = "low"

    for patch in patches:
        file_path = patch.get("file_path", "")
        new_content = patch.get("new_content", "")
        original = original_contents.get(file_path, "")

        risk = classify_risk(
            original_text=original,
            proposed_text=new_content,
            file_path=file_path,
        )

        if risk.level == "high":
            highest = "high"
            for r in risk.reasons:
                all_reasons.append(f"{Path(file_path).name}: {r}")

    return highest, all_reasons
