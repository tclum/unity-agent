import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _extract_class_names(text: str) -> List[str]:
    pattern = r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b"
    return re.findall(pattern, text)


def _contains_method(text: str, method_name: str) -> bool:
    pattern = rf"\b{re.escape(method_name)}\s*\("
    return re.search(pattern, text) is not None


def _contains_field(text: str, field_name: str) -> bool:
    pattern = rf"\b{re.escape(field_name)}\b"
    return re.search(pattern, text) is not None


def _is_balanced(text: str, open_char: str, close_char: str) -> bool:
    depth = 0
    for ch in text:
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _line_count(text: str) -> int:
    return len(text.splitlines())


def get_validation_profile(file_path: str) -> dict:
    normalized = file_path.replace("\\", "/")

    if normalized.endswith("ResultsUI.cs"):
        return {
            "required_methods": [
                "Awake",
                "ShowResults",
                "Hide",
                "PlayAgain",
                "ReturnToMainMenu",
            ],
            "required_fields": [
                "ResultsPanel",
                "TitleText",
                "ScoreSummaryText",
                "PlayAgainButton",
                "MainMenuButton",
            ],
            "max_size_change_ratio": 0.60,
        }

    return {
        "required_methods": [],
        "required_fields": [],
        "max_size_change_ratio": 0.80,
    }


def validate_patch(
    original_text: str,
    proposed_text: str,
    required_methods: Optional[List[str]] = None,
    required_fields: Optional[List[str]] = None,
    max_size_change_ratio: float = 0.80,
) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    required_methods = required_methods or []
    required_fields = required_fields or []

    original_text = original_text or ""
    proposed_text = proposed_text or ""

    if not proposed_text.strip():
        return ValidationResult(
            is_valid=False,
            errors=["Proposed file is empty."],
            warnings=[],
        )

    if proposed_text.strip() == original_text.strip():
        warnings.append("Proposed patch is identical to the original file.")

    original_classes = _extract_class_names(original_text)
    proposed_classes = _extract_class_names(proposed_text)

    for class_name in original_classes:
        if class_name not in proposed_classes:
            errors.append(f"Missing class definition: {class_name}")

    for method_name in required_methods:
        if not _contains_method(proposed_text, method_name):
            errors.append(f"Missing required method: {method_name}()")

    for field_name in required_fields:
        if not _contains_field(proposed_text, field_name):
            errors.append(f"Missing required field/reference: {field_name}")

    if not _is_balanced(proposed_text, "{", "}"):
        errors.append("Unbalanced curly braces detected.")

    if not _is_balanced(proposed_text, "(", ")"):
        errors.append("Unbalanced parentheses detected.")

    if not _is_balanced(proposed_text, "[", "]"):
        warnings.append("Unbalanced square brackets detected.")

    if "MonoBehaviour" in original_text and "MonoBehaviour" not in proposed_text:
        errors.append("MonoBehaviour inheritance appears to have been removed.")

    if "using UnityEngine;" in original_text and "using UnityEngine;" not in proposed_text:
        warnings.append("using UnityEngine; was removed.")

    if "using TMPro;" in original_text and "using TMPro;" not in proposed_text:
        warnings.append("using TMPro; was removed.")

    if "using UnityEngine.UI;" in original_text and "using UnityEngine.UI;" not in proposed_text:
        warnings.append("using UnityEngine.UI; was removed.")

    original_len = len(original_text.strip())
    proposed_len = len(proposed_text.strip())

    if original_len > 0:
        size_change_ratio = abs(proposed_len - original_len) / original_len
        if size_change_ratio > max_size_change_ratio:
            warnings.append(
                f"Large file size change detected: {size_change_ratio:.2%}"
            )

    original_lines = _line_count(original_text)
    proposed_lines = _line_count(proposed_text)

    if original_lines > 0:
        line_change_ratio = abs(proposed_lines - original_lines) / original_lines
        if line_change_ratio > max_size_change_ratio:
            warnings.append(
                f"Large line count change detected: {line_change_ratio:.2%}"
            )

    return ValidationResult(
        is_valid=(len(errors) == 0),
        errors=errors,
        warnings=warnings,
    )


def validate_patch_for_file(file_path: str, original_text: str, proposed_text: str) -> ValidationResult:
    profile = get_validation_profile(file_path)
    return validate_patch(
        original_text=original_text,
        proposed_text=proposed_text,
        required_methods=profile.get("required_methods", []),
        required_fields=profile.get("required_fields", []),
        max_size_change_ratio=profile.get("max_size_change_ratio", 0.80),
    )