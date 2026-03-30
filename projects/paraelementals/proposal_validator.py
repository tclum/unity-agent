import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _extract_class_names(text: str) -> List[str]:
    return re.findall(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)


def _contains_method(text: str, method_name: str) -> bool:
    return re.search(rf"\b{re.escape(method_name)}\s*\(", text) is not None


def _contains_field(text: str, field_name: str) -> bool:
    return re.search(rf"\b{re.escape(field_name)}\b", text) is not None


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


def _check_public_methods_indented(text: str) -> List[str]:
    unindented = []
    pattern = re.compile(
        r"^(public|private|protected|internal)\s+(?!class\s)(?!static\s+class\s)",
        re.MULTILINE
    )
    for match in pattern.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        col = match.start() - line_start
        if col == 0:
            snippet = text[match.start():match.start() + 80].split("\n")[0]
            unindented.append(snippet.strip()[:60])
    return unindented


def _check_coroutine_yield(text: str, method_name: str) -> bool:
    pattern = rf"\bIEnumerator\s+{re.escape(method_name)}\s*\("
    match = re.search(pattern, text)
    if not match:
        return False
    body_start = text.find("{", match.start())
    if body_start == -1:
        return False
    depth = 0
    for i, ch in enumerate(text[body_start:], start=body_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = text[body_start:i + 1]
                return "yield" not in body
    return False


def get_validation_profile(file_path: str) -> dict:
    normalized = file_path.replace("\\", "/")

    # ── Player ──────────────────────────────────────────────────────────────

    if normalized.endswith("SideScrollPlayerController.cs"):
        return {
            "required_methods": ["Awake", "Update", "FixedUpdate",
                                  "UpdateGroundedState", "UpdateFacing", "SetFacing"],
            "required_fields": ["_moveSpeed", "_jumpForce", "_groundCheck",
                                 "_groundLayer", "_rb"],
            "max_size_change_ratio": 0.50,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("SideScrollPlayerCombat.cs"):
        return {
            "required_methods": ["Awake"],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("SideScrollPlayerRespawn.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("PlayerController.cs"):
        return {
            "required_methods": ["Awake", "Update", "FixedUpdate"],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("PlayerCombat.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("PlayerInteractor.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Combat ───────────────────────────────────────────────────────────────

    if normalized.endswith("Health.cs"):
        return {
            "required_methods": ["Awake", "TakeDamage", "Heal"],
            "required_fields": ["_maxHealth", "_currentHealth",
                                 "HealthChanged", "Died"],
            "max_size_change_ratio": 0.50,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("AttackHitbox.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("DamageFlash.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Enemies ──────────────────────────────────────────────────────────────

    if normalized.endswith("SideScrollEnemyController.cs"):
        return {
            "required_methods": ["Awake", "Start", "FixedUpdate",
                                  "HandleDeath", "TryAttackPlayer"],
            "required_fields": ["_moveSpeed", "_detectionRange",
                                 "_attackRange", "_contactDamage", "_rb", "_health"],
            "max_size_change_ratio": 0.50,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("EnemyController.cs"):
        return {
            "required_methods": ["Awake", "Start"],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("EnemySpawner.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("LootDropper.cs"):
        return {
            "required_methods": ["DropLoot"],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Core ─────────────────────────────────────────────────────────────────

    if normalized.endswith("SideScrollCameraFollow.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("SimpleCameraFollow.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Inventory ────────────────────────────────────────────────────────────

    if normalized.endswith("InventoryManager.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("InventorySlot.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Items ────────────────────────────────────────────────────────────────

    if normalized.endswith("ItemData.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.50,
            "check_indentation": False,
            "protected_coroutines": [],
        }

    if normalized.endswith("WorldItemPickup.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Gathering ────────────────────────────────────────────────────────────

    if normalized.endswith("ResourceNode.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── UI ───────────────────────────────────────────────────────────────────

    if normalized.endswith("HealthBarUI.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    if normalized.endswith("DebugHUD.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── World ────────────────────────────────────────────────────────────────

    if normalized.endswith("RoomGenerator.cs"):
        return {
            "required_methods": [],
            "required_fields": [],
            "max_size_change_ratio": 0.60,
            "check_indentation": True,
            "protected_coroutines": [],
        }

    # ── Default ──────────────────────────────────────────────────────────────
    return {
        "required_methods": [],
        "required_fields": [],
        "max_size_change_ratio": 0.80,
        "check_indentation": False,
        "protected_coroutines": [],
    }


def validate_patch(
    original_text: str,
    proposed_text: str,
    required_methods: Optional[List[str]] = None,
    required_fields: Optional[List[str]] = None,
    max_size_change_ratio: float = 0.80,
    check_indentation: bool = False,
    protected_coroutines: Optional[List[str]] = None,
) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    required_methods = required_methods or []
    required_fields = required_fields or []
    protected_coroutines = protected_coroutines or []
    original_text = original_text or ""
    proposed_text = proposed_text or ""

    if not proposed_text.strip():
        return ValidationResult(is_valid=False, errors=["Proposed file is empty."])

    if proposed_text.strip() == original_text.strip():
        warnings.append("Proposed patch is identical to the original file.")

    for class_name in _extract_class_names(original_text):
        if class_name not in _extract_class_names(proposed_text):
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

    for using in ["using UnityEngine;", "using System;", "using System.Collections;",
                  "using System.Collections.Generic;", "using UnityEngine.InputSystem;"]:
        if using in original_text and using not in proposed_text:
            warnings.append(f"{using} was removed.")

    for coroutine in protected_coroutines:
        if _check_coroutine_yield(proposed_text, coroutine):
            errors.append(
                f"Coroutine {coroutine}() appears to have lost its yield statements."
            )

    if check_indentation:
        unindented = _check_public_methods_indented(proposed_text)
        if unindented:
            errors.append(
                "Unindented method(s) detected: " + "; ".join(unindented)
            )

    original_len = len(original_text.strip())
    proposed_len = len(proposed_text.strip())
    if original_len > 0:
        size_change_ratio = abs(proposed_len - original_len) / original_len
        if size_change_ratio > max_size_change_ratio:
            warnings.append(f"Large file size change detected: {size_change_ratio:.2%}")

    original_lines = _line_count(original_text)
    proposed_lines = _line_count(proposed_text)
    if original_lines > 0:
        line_change_ratio = abs(proposed_lines - original_lines) / original_lines
        if line_change_ratio > max_size_change_ratio:
            warnings.append(f"Large line count change detected: {line_change_ratio:.2%}")

    return ValidationResult(is_valid=(len(errors) == 0), errors=errors, warnings=warnings)


def validate_patch_for_file(
    file_path: str, original_text: str, proposed_text: str
) -> ValidationResult:
    profile = get_validation_profile(file_path)
    return validate_patch(
        original_text=original_text,
        proposed_text=proposed_text,
        required_methods=profile.get("required_methods", []),
        required_fields=profile.get("required_fields", []),
        max_size_change_ratio=profile.get("max_size_change_ratio", 0.80),
        check_indentation=profile.get("check_indentation", False),
        protected_coroutines=profile.get("protected_coroutines", []),
    )
